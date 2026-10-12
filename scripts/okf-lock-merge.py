#!/usr/bin/env python3
"""Resolve a conflicted drift.lock after `git merge main` or during `git rebase main`.
Python 3.11+, no third-party imports.

Run it from inside the repository while git is stopped on the conflict. It merges
bindings by (doc, target): start from main's lock, then apply what the branch changed
against the merge base. In a merge the branch is stage 2 and main stage 3. In a rebase
(or `git pull --rebase`) each stop is a commit replay: the result rebased so far is
stage 2 and the replayed commit stage 3, so the rules apply per commit, and the script
runs once per stop.

- added on the branch     -> copy the branch's block
- removed on the branch   -> drop the block
- modified on the branch  -> take the branch's block (any byte: sig or other metadata)
- unchanged on the branch -> keep main's block
- removed on one side and modified on the other -> drop it and say so

Blocks are kept exactly as drift wrote them and sorted by their bytes, as drift v0.10.1
does, so the next `drift link` produces no unrelated diff. Signatures are never judged
here: `drift check` judges them against the merged tree afterwards, so a re-stamp that
main has since invalidated comes out stale instead of silently fresh.

Refuses, writing nothing: any state but a merge or a replay (a merge recreated by
`--rebase-merges`, `git am`, a stash or autostash conflict, cherry-pick, revert),
no conflicted drift.lock, a side that deleted the lock, a lock that is not
`version = 1`, a duplicate (doc, target), drift missing. A drift crash or unreadable `drift check` JSON restores the working lock.
It never calls `drift link` or `drift unlink`.

Exit: 0 resolved (even with stale bindings: staleness belongs to the Work Loop);
2 refused; 3 `drift check` failed and the working lock was restored.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

LOCK = "drift.lock"
MEASURED_DRIFT = "v0.10.1"
EXIT_REFUSED = 2
EXIT_CHECK_FAILED = 3


class Refusal(Exception):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if check and result.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result


# --- state ------------------------------------------------------------------------------

@dataclass(frozen=True)
class State:
    """Which index stage holds which side of the conflict.

    `base` is always stage 1. `main` is the side the result starts from; `branch` is the
    side whose changes are replayed on top of it. The labels name the sides in messages.
    """
    name: str
    main_stage: int
    branch_stage: int
    main_label: str = "main"
    branch_label: str = "branch"
    note: str | None = None


def git_path(root: Path, name: str) -> Path:
    raw = git("rev-parse", "--git-path", name, cwd=root).stdout.decode().strip()
    path = Path(raw)
    return path if path.is_absolute() else root / path


SUPPORTED = "okf-lock-merge.py resolves only a `git merge` or a `git rebase` commit replay"


def replayed_commit(root: Path) -> str:
    shown = git("show", "-s", "--format=%h %s", "REBASE_HEAD", cwd=root, check=False)
    return shown.stdout.decode(errors="replace").strip() if shown.returncode == 0 else "this commit"


def detect_state(root: Path) -> State:
    """Recognize the operation git stopped in: a merge, or a commit replay during a rebase.
    Every other state is refused, so a stage is never read with the wrong meaning."""
    exists = {name: git_path(root, name).exists()
              for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "rebase-apply/rebasing",
                           "CHERRY_PICK_HEAD", "REVERT_HEAD")}
    if exists["CHERRY_PICK_HEAD"]:
        raise Refusal(f"a cherry-pick is in progress; {SUPPORTED}")
    if exists["REVERT_HEAD"]:
        raise Refusal(f"a revert is in progress; {SUPPORTED}")
    if exists["rebase-merge"] and exists["MERGE_HEAD"]:
        raise Refusal("a merge recreated by `git rebase --rebase-merges` is in progress; "
                      f"{SUPPORTED} — resolve this merge by hand")
    if exists["rebase-apply"] and not exists["rebase-apply/rebasing"]:
        raise Refusal(f"`git am` is in progress; {SUPPORTED}")
    if exists["rebase-merge"] or exists["rebase-apply"]:
        commit = replayed_commit(root)
        return State(name="replay", main_stage=2, branch_stage=3,
                     main_label="the rebased result", branch_label="the replayed commit",
                     note=f"per commit: this result covers only {commit}, replayed onto the "
                          "result rebased so far; if a later commit stops on drift.lock, "
                          "run okf-lock-merge.py again")
    if exists["MERGE_HEAD"]:
        return State(name="merge", main_stage=3, branch_stage=2)
    raise Refusal("no merge or rebase in progress; run it after `git merge main` or "
                  "`git rebase main` stops on drift.lock (a conflict left by a stash or "
                  "autostash apply is not supported: resolve it by hand)")


# --- lock -------------------------------------------------------------------------------

STRING = r'"(?:[^"\\]|\\.)*"'
FIELD = re.compile(rf"^([A-Za-z0-9_-]+) = ({STRING})$")
VERSION = re.compile(r"^version = (.*)$")


def unquote(token: str) -> str:
    return json.loads(token) if "\\" in token else token[1:-1]


def parse_lock(text: str, side: str) -> dict[tuple[str, str], str]:
    """Split a v1 lock into its blocks, keyed by (doc, target), byte-for-byte as written."""
    first, _, rest = text.partition("\n")
    version = VERSION.match(first)
    if not version:
        raise Refusal(f"{side}'s drift.lock does not start with `version = 1`; resolve it by hand")
    if version.group(1) != "1":
        raise Refusal(f"{side}'s drift.lock is `version = {version.group(1)}`; "
                      "okf-lock-merge.py reads only version 1")
    blocks: dict[tuple[str, str], str] = {}
    if rest == "":
        return blocks
    if not rest.startswith("\n[[bindings]]\n") or not rest.endswith("\n"):
        raise Refusal(f"{side}'s drift.lock is not laid out as drift writes it; resolve it by hand")
    for chunk in rest[1:-1].split("\n\n"):
        lines = chunk.split("\n")
        fields = [FIELD.match(line) for line in lines[1:]]
        if (lines[0] != "[[bindings]]" or len(fields) < 2 or not all(fields)
                or fields[0].group(1) != "doc" or fields[1].group(1) != "target"):
            raise Refusal(f"{side}'s drift.lock has a binding drift would not write:\n{chunk}")
        key = (unquote(fields[0].group(2)), unquote(fields[1].group(2)))
        if key in blocks:
            raise Refusal(f"{side}'s drift.lock binds {key[0]} -> {key[1]} twice; resolve it by hand")
        blocks[key] = chunk + "\n"
    return blocks


def serialize(blocks: list[str]) -> str:
    ordered = sorted(blocks, key=lambda block: block.encode())
    return "version = 1\n" + ("\n" + "\n".join(ordered) if ordered else "")


@dataclass
class Merge:
    blocks: dict[tuple[str, str], str]
    added: list[tuple[str, str]]
    removed: list[tuple[str, str]]
    modified: list[tuple[str, str]]
    dropped: list[str]


def merge(base: dict, main: dict, branch: dict, state: State) -> Merge:
    result = dict(main)
    out = Merge(result, [], [], [], [])
    for key in sorted(base.keys() | branch.keys()):
        was, now, theirs = base.get(key), branch.get(key), main.get(key)
        if was == now:
            continue
        if was is None:
            result[key] = now
            out.added.append(key)
        elif now is None:
            if theirs is None:
                continue
            if theirs != was:
                del result[key]
                out.dropped.append(f"{key[0]} -> {key[1]}: removed on {state.branch_label}, "
                                   f"changed on {state.main_label}: dropped")
            else:
                del result[key]
                out.removed.append(key)
        elif theirs is None:
            out.dropped.append(f"{key[0]} -> {key[1]}: removed on {state.main_label}, "
                               f"changed on {state.branch_label}: dropped")
        else:
            result[key] = now
            out.modified.append(key)
    return out


# --- run --------------------------------------------------------------------------------

def stages(root: Path) -> set[int]:
    listing = git("ls-files", "-u", "-z", "--", LOCK, cwd=root).stdout.decode()
    return {int(entry.split(" ")[2].split("\t")[0]) for entry in listing.split("\0") if entry}


def read_stage(root: Path, stage: int, side: str) -> dict:
    raw = git("show", f":{stage}:{LOCK}", cwd=root).stdout
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal(f"{side}'s drift.lock is not UTF-8; resolve it by hand") from None
    return parse_lock(text, side)


def drift_check(root: Path) -> dict | None:
    try:
        result = subprocess.run(["drift", "check", "--format", "json"], cwd=root, capture_output=True)
    except OSError:
        return None
    if result.returncode not in (0, 1):
        return None
    try:
        report = json.loads(result.stdout)
    except ValueError:
        return None
    if not isinstance(report, dict) or report.get("schema_version") != "drift.check.v1" \
            or not isinstance(report.get("docs"), list):
        return None
    return report


def stale_lines(report: dict) -> list[str]:
    lines = []
    for doc in report["docs"]:
        if doc.get("result") == "fresh":
            continue
        anchors = [a.get("identity", "?") for a in doc.get("anchors", []) if a.get("result") != "fresh"]
        lines.append(f"  stale     {doc.get('path')} -> {', '.join(anchors) or doc.get('result')}")
    return lines


def resolve(root: Path) -> int:
    state = detect_state(root)
    present = stages(root)
    if not present:
        raise Refusal("drift.lock has no conflict; nothing to resolve")
    for stage, label in ((state.main_stage, state.main_label), (state.branch_stage, state.branch_label)):
        if stage not in present:
            raise Refusal(f"drift.lock was deleted on {label}; keep or delete it by hand "
                          "(`git add drift.lock` or `git rm drift.lock`)")
    if shutil.which("drift") is None:
        raise Refusal("drift is not on PATH; install the pinned drift — the merged lock "
                      "must be checked before it is staged")

    base = read_stage(root, 1, "the merge base") if 1 in present else {}
    main = read_stage(root, state.main_stage, state.main_label)
    branch = read_stage(root, state.branch_stage, state.branch_label)
    result = merge(base, main, branch, state)

    lock = root / LOCK
    original = lock.read_bytes() if lock.exists() else None
    lock.write_bytes(serialize(list(result.blocks.values())).encode())
    report = drift_check(root)
    if report is None:
        if original is None:
            lock.unlink()
        else:
            lock.write_bytes(original)
        print("FAIL  `drift check` crashed or printed unreadable JSON; drift.lock restored "
              "with its conflict, nothing staged", file=sys.stderr)
        return EXIT_CHECK_FAILED
    git("add", "--", LOCK, cwd=root)

    print(f"drift.lock resolved ({state.name}: started from {state.main_label}'s lock, "
          f"applied {state.branch_label}'s changes)")
    if state.note:
        print(state.note)
    for word, keys in (("added", result.added), ("removed", result.removed),
                       ("modified", result.modified)):
        for doc, target in keys:
            print(f"  {word:<9} {doc} -> {target}")
    for line in result.dropped:
        print(f"  {line}")
    stale = stale_lines(report)
    print(*(stale or ["  no stale binding"]), sep="\n")
    version = report.get("tool_version")
    if version and version != MEASURED_DRIFT:
        print(f"warn  drift {version}: the lock layout was measured on drift {MEASURED_DRIFT}")
    others = [p for p in git("diff", "--name-only", "--diff-filter=U", "-z", cwd=root)
              .stdout.decode().split("\0") if p and p != LOCK]
    if others:
        print("still unmerged:", *(f"  {p}" for p in others), sep="\n")
    print("next: review the stale bindings, then run the gate (okf-check.sh) before committing")
    return 0


def main() -> int:
    try:
        top = git("rev-parse", "--show-toplevel").stdout.decode().strip()
        return resolve(Path(top))
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
