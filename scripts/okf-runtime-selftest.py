#!/usr/bin/env python3
"""Offline regressions for gate/recall process boundaries, paths and JSON transport.

Run with python3 scripts/okf-runtime-selftest.py. Fixtures replace only okf;
real shell and Perl execute the scripts under test. No network or shared cache.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent

GIT_ID = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
          "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
TODAY = datetime.date.today().isoformat()
ENTRY_RE = r"knowledge/log/(\d{4}-\d{2}-\d{2})-([a-z0-9-]+)-([0-9a-f]{4})/log\.md"
# The frozen log's marker, as the spec defines it: the split date and the sha256 of every
# byte above the marker line, line endings normalized to LF.
MARKER_RE = r"<!-- okf-log frozen (\d{4}-\d{2}-\d{2}) sha256:([0-9a-f]{64}) -->"


def frozen_parts(data: bytes) -> tuple[bytes, str, str]:
    """(the bytes above the marker line, its date, its hash) of a frozen log."""
    lines = data.splitlines(keepends=True)
    while lines and not lines[-1].strip():
        lines.pop()
    match = re.fullmatch(MARKER_RE, lines[-1].decode().rstrip("\r\n")) if lines else None
    assert match, f"the last non-blank line is not a marker: {data[-200:]!r}"
    return b"".join(lines[:-1]), match.group(1), match.group(2)


def pin_scripts(root: Path, names: tuple[str, ...], *, fill_cache: bool = True) -> Path:
    """A v0.7.0 lockfile in `root` pinning the working-tree bytes of `names`; the cache
    holds those bytes when `fill_cache`. Returns the XDG cache home."""
    cache = root / "cache/okf-drift/v0.7.0"
    cache.mkdir(parents=True, exist_ok=True)
    lines = ["v0.7.0"]
    for name in names:
        data = (SCRIPTS / name).read_bytes()
        if fill_cache:
            (cache / name).write_bytes(data)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    (root / ".okf-drift-version").write_text("\n".join(lines) + "\n")
    return root / "cache"


def split_log(root: Path, bundle: str = "knowledge") -> None:
    """Freeze `root/bundle/log.md`, as /okf-migrate does: fixture preparation, so the
    working-tree okf-log.sh runs directly in either selftest mode."""
    subprocess.run(["sh", str(SCRIPTS / "okf-log.sh"), "split", bundle], cwd=root, check=True,
                   capture_output=True)


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="okf-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "knowledge"
        (self.bundle / "project").mkdir(parents=True)
        (self.bundle / "index.md").write_text('---\nokf_version: "0.2"\n---\n')
        (self.bundle / "log.md").write_text("# Log\n")
        split_log(self.root)
        (self.bundle / "project/index.md").write_text(
            "- [State](/project/state.md) — Fixture state.\n"
        )
        (self.bundle / "project/state.md").write_text(
            "---\ntype: Reference\ntitle: State\ndescription: Fixture state.\n"
            "last_updated: 2026-09-16\ncode_refs: []\n---\n"
            "# State\n\n**Working:**\n- Fixture.\n\n"
            "**Not yet built:**\n- Nothing.\n\n**Known issues:**\n- None.\n"
        )
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.stub = self.root / "bin"
        self.stub.mkdir()
        for name, text in {
            "okf": '#!/bin/sh\ncase "$1" in\nversion) echo "okf v0.6.0";;\nvalidate) cat "$FIXTURE/validate.json"; exit "${VALIDATE_EXIT:-0}";;\nsearch) cat "$FIXTURE/search.json"; exit "${SEARCH_EXIT:-0}";;\nesac\n',
        }.items():
            path = self.stub / name
            path.write_text(text)
            path.chmod(0o755)
        self.env = dict(os.environ, FIXTURE=str(self.root), TMPDIR=str(self.root), **GIT_ID,
                        PATH=str(self.stub) + os.pathsep + os.environ["PATH"])
        self.env.pop("OKF_DRIFT_ROOT", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            # The exact unpublished runtime bytes, pinned in a fixture release cache.
            # No scripts live in the consumer; exercise all 13 contracts via the launcher.
            cache = self.root / "cache/okf-drift/v0.7.0"
            cache.mkdir(parents=True)
            self.env["XDG_CACHE_HOME"] = str(self.root / "cache")
            lines = ["v0.7.0"]
            for name in ("okf-check.sh", "okf-recall.sh", "okf-tidy.sh"):
                data = (SCRIPTS / name).read_bytes()
                (cache / name).write_bytes(data)
                lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
            (self.root / ".okf-drift-version").write_text("\n".join(lines) + "\n")
        self.payload("validate", {"gate_passed": True, "is_conformant": True})
        self.payload("search", [{"concept_id": "project/state", "description": "Fixture state.", "score": 1}])

    def payload(self, name: str, value: object) -> None:
        (self.root / f"{name}.json").write_text(json.dumps(value))

    def run_script(self, script: str, bundle: str = "knowledge") -> subprocess.CompletedProcess[str]:
        args = [str(SCRIPTS / script)]
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            args = ["sh", str(SCRIPTS / "okf-shim.sh"), "--repo-root", str(self.root), script]
        if script == "okf-recall.sh":
            args.append("fixture")
        return subprocess.run(args + [bundle], cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def assert_unusable(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("1 hit(s)", result.stdout)
        self.assertNotIn("okf gate passed", result.stdout)
        self.assertNotIn("no concept", result.stdout)

    def concept(self, rel: str, *, status: str | None = None,
                stale_after: str | None = None, code_refs: tuple[str, ...] = ()) -> None:
        """A second fixture concept, written only where a test needs one. It is deliberately
        NOT in setUp: the gate requires an index row for every concept,
        and recall requires neither."""
        path = self.bundle / f"{rel}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["type: Reference", "title: Second", "description: Second fixture.",
                 "last_updated: 2026-09-16"]
        if status is not None:
            lines.append(f"status: {status}")
        if stale_after is not None:
            lines.append(f"stale_after: {stale_after}")
        if code_refs:
            lines.append("code_refs:")
            lines.extend(f"  - {ref}" for ref in code_refs)
        path.write_text("---\n" + "\n".join(lines) + "\n---\n# Second\n\nBody.\n")

    def two_hits(self) -> None:
        self.payload("search", [
            {"concept_id": "project/state", "description": "Fixture state.", "score": 2},
            {"concept_id": "architecture/core", "description": "Second fixture.", "score": 1},
        ])

    def commit(self, message: str, files: dict[str, str]) -> str:
        """Write `files` (repo-relative path => text), commit everything, return the short sha."""
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, env=self.env)
        subprocess.run(["git", "commit", "-qm", message], cwd=self.root, check=True, env=self.env)
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self.root, env=self.env,
                              check=True, text=True, capture_output=True).stdout.strip()

    def hint_fixture(self, *code_refs: str) -> None:
        self.concept("architecture/core", status="stable", code_refs=code_refs)
        self.two_hits()
        self.commit("write the concept", {"src/lib/a.rs": "a\n", "src/lib/b.rs": "b\n"})

    def test_recall_shows_no_change_hint_when_the_code_did_not_move(self) -> None:
        self.hint_fixture("src/lib/a.rs")
        self.commit("unrelated", {"src/lib/b.rs": "b2\n"})
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("code changed since", result.stdout)
        self.assertNotIn("drift", result.stdout)

    def test_recall_counts_the_commits_on_code_refs_since_the_concepts_last_commit(self) -> None:
        self.hint_fixture("src/lib/a.rs")
        self.commit("first", {"src/lib/a.rs": "a2\n"})
        sha = self.commit("second change", {"src/lib/a.rs": "a3\n"})
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'code changed since this concept: 2 commit(s) on src/lib/a.rs (last {sha} '
                      f'{TODAY} "second change")', result.stdout)
        self.assertIn("1 hit(s) with a change hint", result.stdout)
        self.assertIn("the code wins", result.stdout)

    def test_recall_counts_commits_under_a_directory_code_ref(self) -> None:
        self.hint_fixture("src/lib/")
        sha = self.commit("touch b", {"src/lib/b.rs": "b2\n"})
        result = self.run_script("okf-recall.sh")
        self.assertIn(f'1 commit(s) on src/lib/ (last {sha}', result.stdout)

    def test_recall_reads_unindented_code_refs_items(self) -> None:
        """The setup templates write `code_refs:` items at column zero."""
        self.concept("architecture/core", status="stable")
        path = self.bundle / "architecture/core.md"
        path.write_text(path.read_text().replace("status: stable\n", "status: stable\ncode_refs:\n- src/lib/a.rs\n"))
        self.two_hits()
        self.commit("write the concept", {"src/lib/a.rs": "a\n"})
        sha = self.commit("touch a", {"src/lib/a.rs": "a2\n"})
        result = self.run_script("okf-recall.sh")
        self.assertIn(f"1 commit(s) on src/lib/a.rs (last {sha}", result.stdout)

    def test_recall_counts_a_code_ref_with_a_symbol_fragment_on_its_file(self) -> None:
        self.hint_fixture("src/lib/a.rs#run")
        sha = self.commit("touch a", {"src/lib/a.rs": "a2\n"})
        result = self.run_script("okf-recall.sh")
        self.assertIn(f"1 commit(s) on src/lib/a.rs (last {sha}", result.stdout)

    def test_recall_shows_no_change_hint_without_code_refs(self) -> None:
        self.hint_fixture()
        self.commit("touch a", {"src/lib/a.rs": "a2\n"})
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("code changed since", result.stdout)

    def test_recall_outside_git_still_searches(self) -> None:
        shutil.rmtree(self.root / ".git")
        self.concept("architecture/core", status="stable", code_refs=("src/lib/a.rs",))
        self.two_hits()
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 hit(s)", result.stdout)
        self.assertNotIn("code changed since", result.stdout)

    def days_from_today(self, days: int) -> str:
        # UTC, like okf and the scripts: a local date would disagree for part of every day.
        today = datetime.datetime.now(datetime.timezone.utc).date()
        return (today + datetime.timedelta(days=days)).isoformat()

    def test_recall_reads_review_due_and_today_as_expired(self) -> None:
        """okf --stale fails a concept ON its stale_after day, so recall must not call that
        day current; the days before it, within the window, are `due`."""
        for days, label in ((0, "review expired"), (10, "review due"), (40, "review current")):
            with self.subTest(days=days):
                date = self.days_from_today(days)
                self.concept("architecture/core", status="stable", stale_after=date)
                self.two_hits()
                result = self.run_script("okf-recall.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                expected = label if label == "review current" else f"{label} {date}"
                self.assertIn(f"stable · {expected}\n", result.stdout)

    def test_recall_names_an_invalid_review_date(self) -> None:
        # Value: protects=an impossible stale_after is named, not hidden as "no review date"; fails_when=day_number errors fall back silently; why_new=only valid dates were tested; seam=none
        for date in ("2026-13-01", "0999-01-01"):
            with self.subTest(date=date):
                self.concept("architecture/core", status="stable", stale_after=date)
                self.two_hits()
                result = self.run_script("okf-recall.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"review date invalid ({date})", result.stdout)

    def test_gate_fails_an_impossible_review_date_and_reads_an_empty_window_as_default(self) -> None:
        # Value: protects=okf never expires 2026-13-01, so the gate must; empty CI var keeps 30; fails_when=the timegm fallback or // default returns; why_new=new in this review; seam=none
        state = self.bundle / "project/state.md"
        base = state.read_text()
        state.write_text(base.replace("last_updated: 2026-09-16", "last_updated: 2026-09-16\nstale_after: 2026-13-01"))
        bad = self.run_script("okf-check.sh")
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("stale_after: 2026-13-01 is not a real date", bad.stdout)
        state.write_text(base.replace("last_updated: 2026-09-16", f"last_updated: 2026-09-16\nstale_after: {self.days_from_today(10)}"))
        self.env["OKF_REVIEW_WINDOW_DAYS"] = ""
        due = self.run_script("okf-check.sh")
        self.assertEqual(due.returncode, 0, due.stdout + due.stderr)
        self.assertIn("due for review within 30 days", due.stdout)

    def test_recall_searches_the_project_scope_only(self) -> None:
        """okf v0.5.0+ searches ~/.okf, /etc/okf and vendor bundles by default; their ids
        have no file in the bundle."""
        log = self.root / "okf-args.log"
        okf = self.stub / "okf"
        plain = okf.read_text()
        # A v0.5.0+ binary lists -scope in `search --help`; v0.3.0 rejects the flag outright.
        for help_text, scoped in (("  -scope string", True), ("  -json", False)):
            with self.subTest(scoped=scoped):
                log.write_text("")
                okf.write_text(plain.replace(
                    'search) cat',
                    f'search) echo "$*" >> "{log}"; [ "$2" = --help ] && {{ echo "{help_text}"; exit 0; }}; cat'))
                result = self.run_script("okf-recall.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                searched = [l for l in log.read_text().splitlines() if "--help" not in l]
                self.assertEqual(len(searched), 1, log.read_text())
                self.assertEqual("--scope project" in searched[0], scoped, searched[0])

    def test_gate_warns_on_a_review_due_within_the_window(self) -> None:
        state = self.bundle / "project/state.md"
        base = state.read_text()
        for days, window, warned in ((10, None, True), (40, None, False), (40, "60", True), (0, None, False)):
            with self.subTest(days=days, window=window):
                date = self.days_from_today(days)
                state.write_text(base.replace("code_refs: []\n", f"code_refs: []\nstale_after: {date}\n"))
                if window: self.env["OKF_REVIEW_WINDOW_DAYS"] = window
                else: self.env.pop("OKF_REVIEW_WINDOW_DAYS", None)
                result = self.run_script("okf-check.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                line = f"warn  1 concept(s) due for review within {window or 30} days"
                (self.assertIn if warned else self.assertNotIn)(line, result.stdout)
                if warned:
                    self.assertIn(f"project/state.md ({date})", result.stdout)
        self.env["OKF_REVIEW_WINDOW_DAYS"] = "a month"
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("okf gate passed", result.stdout)

    def test_gate_names_a_bundle_symlinked_outside_its_parent(self) -> None:
        """okf v0.6.0 refuses such a root with no JSON; v0.3.0 loaded it as an empty bundle.
        The gate fails before calling okf, with the cause named."""
        outside = Path(tempfile.mkdtemp(prefix="okf-outside-"))
        self.addCleanup(shutil.rmtree, outside, True)
        shutil.move(str(self.bundle), outside / "knowledge")
        self.bundle.symlink_to(outside / "knowledge", target_is_directory=True)
        for spelling in ("knowledge", "knowledge/"):
            with self.subTest(bundle=spelling):
                result = self.run_script("okf-check.sh", spelling)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("outside", result.stdout)
                self.assertIn("refuses a bundle root that leaves its parent directory", result.stdout)

    def test_gate_accepts_a_bundle_symlinked_inside_its_parent(self) -> None:
        shutil.move(str(self.bundle), self.root / "kb-real")
        self.bundle.symlink_to("kb-real", target_is_directory=True)
        result = self.run_script("okf-check.sh")
        self.assertNotIn("leaves its parent directory", result.stdout)

    def gate_bundle(self) -> None:
        """Three concepts with and without `code_refs`; `project/state` is exempt."""
        rows = {
            "architecture/core": ("Core fixture.", []),
            "playbooks/thing": ("Thing fixture.", ["src/lib.rs"]),
            "playbooks/bound": ("Bound fixture.", ["src/lib.rs"]),
        }
        for rel, (desc, refs) in rows.items():
            path = self.bundle / f"{rel}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            code_refs = "code_refs: []\n" if not refs else \
                "code_refs:\n" + "".join(f"  - {r}\n" for r in refs)
            path.write_text(
                f"---\ntype: Reference\ntitle: {rel}\ndescription: {desc}\n"
                f"last_updated: 2026-09-16\n{code_refs}---\n# {rel}\n\nBody.\n"
            )
        for directory in ("architecture", "playbooks"):
            (self.bundle / directory / "index.md").write_text("".join(
                f"- [{rel}](/{rel}.md) — {desc}\n"
                for rel, (desc, _) in rows.items() if rel.startswith(directory + "/")
            ))

    def test_gate_groups_empty_code_refs_in_one_line(self) -> None:
        self.gate_bundle()
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "warn  1 concept(s) with empty code_refs (okf search --for-path cannot find "
            "them): architecture/core.md",
            result.stdout,
        )
        # A concept with code_refs is not listed; neither is the exempt snapshot.
        self.assertNotIn("playbooks/bound.md", result.stdout)
        self.assertNotIn("project/state.md", result.stdout)
        # And the old per-concept line is gone.
        self.assertNotIn("code_refs is empty", result.stdout)

    def test_gate_exempts_state_evidence_like_the_snapshot(self) -> None:
        (self.bundle / "project/index.md").write_text(
            "- [State](/project/state.md) — Fixture state.\n"
            "- [Evidence](/project/state-evidence.md) — Fixture evidence.\n"
        )
        (self.bundle / "project/state-evidence.md").write_text(
            "---\ntype: Reference\ntitle: Evidence\ndescription: Fixture evidence.\n"
            "last_updated: 2026-09-16\ncode_refs: []\n---\n# Evidence\n\nBody.\n"
        )
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("state-evidence.md", result.stdout)

    def test_gate_warns_on_a_state_item_long_enough_to_be_evidence(self) -> None:
        state = self.bundle / "project/state.md"
        text = state.read_text()
        for length, warned in ((300, False), (301, True)):
            with self.subTest(length=length):
                state.write_text(text.replace("- Fixture.", "- " + "x" * length))
                result = self.run_script("okf-check.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                line = "project/state.md: 1 item(s) over 300 characters"
                (self.assertIn if warned else self.assertNotIn)(line, result.stdout)

    def wiki(self) -> None:
        """A wiki bundle: `.okf-profile` says wiki, no project snapshot, and one
        reference concept with no code_refs at all."""
        (self.root / ".okf-profile").write_text("wiki\n")
        shutil.rmtree(self.bundle / "project")
        (self.bundle / "reference").mkdir()
        (self.bundle / "reference/index.md").write_text(
            "- [Identity](/reference/identity.md) — Who I am.\n")
        (self.bundle / "reference/identity.md").write_text(
            "---\ntype: Reference\ntitle: Identity\ndescription: Who I am.\n"
            "last_updated: 2026-09-29\nstale_after: 2099-01-01\n---\n# Identity\n\nBody.\n")
        self.payload("search", [{"concept_id": "reference/identity",
                                 "description": "Who I am.", "score": 1}])

    def test_wiki_gate_needs_no_snapshot_or_code_refs(self) -> None:
        self.wiki()
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("warn  ", result.stdout)
        self.assertIn("passed with no warnings", result.stdout)

    def test_wiki_recall_serves_hits_with_status_and_review(self) -> None:
        self.wiki()
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 hit(s)", result.stdout)
        self.assertIn("no status · review current", result.stdout)
        self.assertNotIn("commit(s) on", result.stdout)

    def test_unknown_profile_fails_closed(self) -> None:
        (self.root / ".okf-profile").write_text("wikki\n")
        for script in ("okf-check.sh", "okf-recall.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("expected 'code' or 'wiki'", result.stderr)

    def test_open_question_is_a_warning_and_the_pass_line_counts_it(self) -> None:
        state = self.bundle / "project/state.md"
        state.write_text(state.read_text().replace("- Fixture.", "- Fixture [DA VERIFICARE]."))
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warn  1 concept(s) with an open question", result.stdout)
        self.assertIn("passed with 1 warning(s) above", result.stdout)

    def test_a_bundle_with_no_concept_fails(self) -> None:
        self.wiki()
        shutil.rmtree(self.bundle / "reference")
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  no concept in knowledge yet", result.stdout)

    def test_open_question_inside_a_fence_is_an_example_not_a_question(self) -> None:
        state = self.bundle / "project/state.md"
        state.write_text(state.read_text() + "\n## Example\n\n```\n[DA VERIFICARE] sample\n```\n")
        result = self.run_script("okf-check.sh")
        self.assertNotIn("open question", result.stdout)

    def test_a_code_bundle_with_no_concept_fails(self) -> None:
        shutil.rmtree(self.bundle / "project")
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  no concept in knowledge yet", result.stdout)

    def scaffold(self, target: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["sh", str(SCRIPTS / "okf-scaffold.sh"), *args, str(target)],
                              env=self.env, text=True, capture_output=True)

    def freeze(self, history: bytes) -> bytes:
        (self.bundle / "log.md").write_bytes(history)
        split_log(self.root)
        return (self.bundle / "log.md").read_bytes()

    def assert_gate_fails(self, *needles: str) -> str:
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stdout)
        return result.stdout

    def assert_gate_passes(self) -> None:
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_leftover_drift_lock_fails_naming_okf_migrate_in_both_profiles(self) -> None:
        for profile in ("code", "wiki"):
            with self.subTest(profile=profile):
                if profile == "wiki":
                    self.wiki()
                (self.root / "drift.lock").write_text("version = 1\n")
                out = self.assert_gate_fails("FAIL  drift.lock found: drift is no longer used, run /okf-migrate")
                self.assertNotIn("okf gate passed", out)

    def test_a_leftover_drift_lock_at_the_root_fails_a_nested_bundle(self) -> None:
        (self.root / "docs").mkdir()
        shutil.move(str(self.bundle), self.root / "docs/knowledge")
        (self.root / "drift.lock").write_text("version = 1\n")
        result = self.run_script("okf-check.sh", "docs/knowledge")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("drift.lock found", result.stdout)

    def test_a_gate_without_drift_lock_passes_with_no_drift_on_path(self) -> None:
        self.env["PATH"] = os.pathsep.join([str(self.stub), "/usr/bin", "/bin",
                                            "/usr/sbin", "/sbin"])
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("drift", result.stdout)

    def test_an_unmigrated_bundle_fails_naming_okf_migrate_in_both_profiles(self) -> None:
        for profile in ("code", "wiki"):
            with self.subTest(profile=profile):
                if profile == "wiki":
                    self.wiki()
                (self.bundle / "log.md").write_text("# Log\n")
                self.assert_gate_fails("log.md", "/okf-migrate")

    def test_a_change_to_the_frozen_history_fails_naming_the_log_entry(self) -> None:
        history = f"# Log\n\n## {TODAY}\n* split today\n\n## 2026-01-01\n* older\n".encode()
        frozen = self.freeze(history)
        self.assert_gate_passes()
        cases = {
            "a line under the split-day heading": frozen.replace(b"* split today\n", b"* split today\n* new\n"),
            "a line under an old heading": frozen.replace(b"* older\n", b"* older\n* new\n"),
        }
        for label, data in cases.items():
            with self.subTest(label):
                (self.bundle / "log.md").write_bytes(data)
                self.assert_gate_fails("log.md", "frozen", "knowledge/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md",
                                       "okf-log.sh add")

    def test_text_below_the_marker_fails_and_a_trailing_newline_passes(self) -> None:
        frozen = self.freeze(b"# Log\n\n## 2026-01-01\n* older\n")
        (self.bundle / "log.md").write_bytes(frozen + b"\n\n")
        self.assert_gate_passes()
        (self.bundle / "log.md").write_bytes(frozen + b"\n## 2026-10-12\n* new\n")
        self.assert_gate_fails("below the marker", "knowledge/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md")

    def test_a_crlf_checkout_of_unchanged_history_passes(self) -> None:
        frozen = self.freeze(b"# Log\n\n## 2026-01-01\n* older\n")
        (self.bundle / "log.md").write_bytes(frozen.replace(b"\n", b"\r\n"))
        self.assert_gate_passes()

    def test_refreeze_turns_the_gate_green_again(self) -> None:
        frozen = self.freeze(b"# Log\n\n## 2026-01-01\n* a typo\n")
        (self.bundle / "log.md").write_bytes(frozen.replace(b"a typo", b"the fix"))
        self.assert_gate_fails("frozen")
        subprocess.run(["sh", str(SCRIPTS / "okf-log.sh"), "split", "--refreeze", "knowledge"],
                       cwd=self.root, check=True, capture_output=True)
        self.assert_gate_passes()

    def entry(self, text: str) -> None:
        path = self.bundle / "log/2026-10-12-fix-abcd/log.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_a_log_entry_with_iso_headings_passes(self) -> None:
        self.entry("<!-- okf-log branch: alice/fix -->\n"
                   "## 2026-10-12\n* two\n\n```\n## not a heading\n```\n\n## 2026-10-11\n* one\n")
        self.assert_gate_passes()

    def test_a_log_entry_heading_that_is_not_a_bare_iso_date_fails_in_both_profiles(self) -> None:
        for profile in ("code", "wiki"):
            if profile == "wiki":
                self.wiki()
            for heading in ("## 2026-10-12 — the fix", "## Today", "## 2026-1-2"):
                with self.subTest(profile=profile, heading=heading):
                    self.entry(f"{heading}\n* x\n")
                    self.assert_gate_fails("knowledge/log/2026-10-12-fix-abcd/log.md", heading)

    def test_scaffold_refusals_write_nothing(self) -> None:
        cases = {
            "wiki over a code profile": (("--profile", "wiki"), {".okf-profile": "code\n"}),
            "code over a wiki profile": ((), {".okf-profile": "wiki\n"}),
            "wiki into a repo with a pin": (("--profile", "wiki"), {".okf-drift-version": "v0.7.0\n"}),
        }
        for label, (args, files) in cases.items():
            with self.subTest(label):
                target = Path(tempfile.mkdtemp(dir=self.root))
                for name, text in files.items():
                    (target / name).write_text(text)
                result = self.scaffold(target, *args)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("refusing", result.stderr)
                self.assertFalse((target / "knowledge").exists(), label)
                if ".okf-profile" in files:
                    self.assertEqual((target / ".okf-profile").read_text(), files[".okf-profile"])

    def test_scaffold_rejects_a_bad_or_missing_profile_value(self) -> None:
        target = Path(tempfile.mkdtemp(dir=self.root))
        for args in (("--profile", "wikki"), ("--profile",)):
            with self.subTest(args=args):
                result = self.scaffold(target, *args) if args != ("--profile",) else \
                    subprocess.run(["sh", str(SCRIPTS / "okf-scaffold.sh"), "--profile"],
                                   env=self.env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse((target / "knowledge").exists())

    def test_scaffold_wiki_writes_the_profile_and_its_templates(self) -> None:
        target = Path(tempfile.mkdtemp(dir=self.root))
        result = self.scaffold(target, "--profile", "wiki", "--name", "W")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((target / ".okf-profile").read_text(), "wiki\n")
        for rel in ("index.md", "log.md", "reference/index.md", "playbooks/index.md", "decisions/index.md"):
            self.assertTrue((target / "knowledge" / rel).is_file(), rel)
        self.assertFalse((target / "knowledge/project").exists())

    def setup_entries(self, target: Path) -> list[Path]:
        return sorted((target / "knowledge/log").glob("*/log.md"))

    def test_scaffold_starts_split_with_the_created_line_in_the_setup_entry(self) -> None:
        """Outside any git repository, both profiles lay down a frozen root log.md and
        put the "Created" line in the first log entry, not under a dated heading."""
        for profile in ("code", "wiki"):
            with self.subTest(profile=profile):
                target = Path(tempfile.mkdtemp(dir=self.root))
                result = self.scaffold(target, "--profile", profile, "--name", "S")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("fatal", result.stderr)
                above, date, _ = frozen_parts((target / "knowledge/log.md").read_bytes())
                self.assertEqual(date, TODAY)
                self.assertNotRegex(above.decode(), r"(?m)^## ")
                self.assertNotIn("Created", above.decode())
                entries = self.setup_entries(target)
                self.assertEqual(len(entries), 1, entries)
                self.assertRegex(str(entries[0].relative_to(target)),
                                 rf"\Aknowledge/log/{TODAY}-setup-[0-9a-f]{{4}}/log\.md\Z")
                text = entries[0].read_text()
                self.assertTrue(text.startswith(f"## {TODAY}\n"), text)
                self.assertEqual(text.count("**Created**"), 1, text)

    def test_a_forced_scaffold_rerun_adds_no_second_created_line(self) -> None:
        for profile in ("code", "wiki"):
            with self.subTest(profile=profile):
                target = Path(tempfile.mkdtemp(dir=self.root))
                self.assertEqual(self.scaffold(target, "--profile", profile).returncode, 0)
                before = {p: p.read_bytes() for p in (target / "knowledge").rglob("*.md")}
                result = self.scaffold(target, "--profile", profile, "--force")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                after = {p: p.read_bytes() for p in (target / "knowledge").rglob("*.md")}
                self.assertEqual(after, before)

    def test_gate_rejects_a_nonzero_okf_validate(self) -> None:
        self.env["VALIDATE_EXIT"] = "7"
        self.assert_unusable(self.run_script("okf-check.sh"))

    def test_gate_caps_a_long_warning_list_unless_verbose(self) -> None:
        # Value: protects=a grouped list stays 8 names + a count; fails_when=the cap or OKF_VERBOSE breaks; why_new=no test had >8 concepts; seam=none
        rows = []
        for i in range(10):
            self.concept(f"architecture/c{i:02d}")
            rows.append(f"- [Second](/architecture/c{i:02d}.md) — Second fixture.")
        (self.bundle / "architecture/index.md").write_text("\n".join(rows) + "\n")
        capped = self.run_script("okf-check.sh")
        self.assertIn("10 concept(s) with empty code_refs", capped.stdout)
        self.assertIn("… and 2 more (OKF_VERBOSE=1 lists them)", capped.stdout)
        self.assertNotIn("architecture/c09.md", capped.stdout)
        self.env["OKF_VERBOSE"] = "1"
        full = self.run_script("okf-check.sh")
        self.assertIn("architecture/c09.md", full.stdout)
        self.assertNotIn("more (OKF_VERBOSE=1", full.stdout)

    def test_recall_rejects_search_failure_even_with_valid_results(self) -> None:
        self.env["SEARCH_EXIT"] = "3"
        self.assert_unusable(self.run_script("okf-recall.sh"))
        (self.root / "search.json").write_text("")
        self.assert_unusable(self.run_script("okf-recall.sh"))

    def test_recall_rejects_malformed_search(self) -> None:
        path = self.root / "search.json"
        for blob in ("", "garbage", "null", "{}", "42"):
            with self.subTest(blob=blob):
                path.write_text(blob)
                self.assert_unusable(self.run_script("okf-recall.sh"))

    def test_recall_accepts_genuine_empty_search(self) -> None:
        self.payload("search", [])
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no concept", result.stdout)

    def test_large_json_stays_out_of_argv_and_temp_files_are_cleaned(self) -> None:
        # Model Linux's argument limit even on macOS, where the old implementation
        # otherwise passes. On Linux the kernel enforces it before this wrapper runs.
        perl = shutil.which("perl")
        self.assertIsNotNone(perl)
        guard = self.stub / "perl"
        guard.write_text('#!/bin/sh\nfor arg do\n[ "${#arg}" -lt 131072 ] || exit 126\ndone\nexec ' + shlex.quote(perl) + ' "$@"\n')
        guard.chmod(0o755)
        self.payload("search", [{"concept_id": "project/state", "description": "x" * 300000, "score": 1}])
        for script in ("okf-check.sh", "okf-recall.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(list(self.root.glob("okf-check.*")), [])
                self.assertEqual(list(self.root.glob("okf-recall.*")), [])


class TidyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="okf-tidy-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        bundle = self.root / "knowledge"
        bundle.mkdir()
        (bundle / "index.md").write_text(
            '---\nokf_version: "0.2"\n---\n'
            "- [Fixture](/concept.md) — Fixture concept.\n"
        )
        (bundle / "log.md").write_text("# Log\n")
        split_log(self.root)
        (bundle / "concept.md").write_text(
            "---\n"
            "type: Reference\n"
            "title: Fixture\n"
            "description: Fixture concept.\n"
            "last_updated: 2026-09-16\n"
            "code_refs:\n"
            "  - src/lib.rs\n"
            "---\n"
            "# Fixture\n\nA fixture concept.\n"
        )
        (self.root / "src").mkdir()
        (self.root / "src/lib.rs").write_text("pub fn fixture() {}\n")

        self.stub = self.root / "bin"
        self.stub.mkdir()
        (self.stub / "okf").write_text(
            '#!/bin/sh\n'
            'case "$1" in\n'
            'version) echo "okf v0.6.0" ;;\n'
            'validate) cat "$OKF_VALIDATE_JSON" ;;\n'
            '*) exit 2 ;;\n'
            'esac\n'
        )
        (self.stub / "okf").chmod(0o755)

        self.validate_json = self.root / "validate.json"
        self.validate_json.write_text(json.dumps({"gate_passed": True, "is_conformant": True}))
        self.env = dict(
            os.environ,
            OKF_VALIDATE_JSON=str(self.validate_json),
            PATH=str(self.stub) + os.pathsep + os.environ["PATH"],
            TMPDIR=str(self.root),
            **GIT_ID,
        )
        self.env.pop("OKF_DRIFT_ROOT", None)
        self.env.pop("OKF_DRIFT_SHIM", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            self.env["XDG_CACHE_HOME"] = str(pin_scripts(self.root, (
                "okf-check.sh", "okf-recall.sh", "okf-tidy.sh", "okf-log.sh")))
        subprocess.run(["git", "add", "."], cwd=self.root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            command = ["sh", str(SCRIPTS / "okf-shim.sh"), "--repo-root", str(self.root), script]
        else:
            command = [str(SCRIPTS / script)]
        return subprocess.run(command + list(args), cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def test_tidy_handles_spaces_and_non_ascii_names(self) -> None:
        # Value: protects=dates and rows for café.md, no repeated row for a spaced name; fails_when=git status quoting or byte paths return; why_new=fixture names were ASCII; seam=none
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
                       cwd=self.root, check=True)
        bundle = self.root / "knowledge"
        for name, title in (("café.md", "Café"), ("my note.md", "Note")):
            (bundle / name).write_text(f"---\ntype: Reference\ntitle: {title}\ndescription: {title} d.\n"
                                       "last_updated: 2026-01-01\n---\n# T\n")
        today = subprocess.run(["date", "+%F"], text=True, capture_output=True).stdout.strip()
        first = self.run_script("okf-tidy.sh", "./knowledge")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn(f"last_updated: {today}", (bundle / "café.md").read_text())
        self.assertIn(f"last_updated: {today}", (bundle / "my note.md").read_text())
        self.assertIn("- [Café](/café.md) — Café d.", (bundle / "index.md").read_text())
        self.assertIn("skipped       my note.md", first.stdout)
        before = (bundle / "index.md").read_text()
        again = self.run_script("okf-tidy.sh", "knowledge")
        self.assertEqual((bundle / "index.md").read_text(), before)
        self.assertIn("nothing to do", again.stdout)

    def test_tidy_syncs_index_rows_and_dates_what_changed(self) -> None:
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
                       cwd=self.root, check=True)
        bundle = self.root / "knowledge"
        index = bundle / "index.md"
        index.write_text(index.read_text().replace("— Fixture concept.", "— an old description"))
        (bundle / "second.md").write_text("---\ntype: Reference\ntitle: Second one\n"
                                          "description: The second.\nlast_updated: 2026-01-01\n---\n# Second\n")
        result = self.run_script("okf-tidy.sh", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        today = subprocess.run(["date", "+%F"], text=True, capture_output=True).stdout.strip()
        text = index.read_text()
        self.assertIn("- [Fixture](/concept.md) — Fixture concept.\n- [Second one](/second.md) — The second.", text)
        self.assertIn(f"last_updated: {today}", (bundle / "second.md").read_text())
        self.assertIn("last_updated: 2026-09-16", (bundle / "concept.md").read_text())
        again = self.run_script("okf-tidy.sh", "knowledge")
        self.assertIn("nothing to do", again.stdout)
        gate = self.run_script("okf-check.sh", "knowledge")
        self.assertNotIn("carries a description", gate.stdout)
        self.assertNotIn("not listed in", gate.stdout)


ALICE = "<!-- okf-log branch: alice/fix -->\n"   # the comment a discovered entry records


class LogEntryTests(unittest.TestCase):
    """`okf-log.sh add`: the one writer of a branch's log entry, driven through its CLI in
    a throwaway repository whose `origin/HEAD` is `main`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="okf-log-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.bundle = self.root / "knowledge"
        self.bundle.mkdir(parents=True)
        self.history = "# Log\n\n## 2026-01-01\n* history before the split\n"
        (self.bundle / "log.md").write_text(self.history)
        (self.bundle / "index.md").write_text('---\nokf_version: "0.2"\n---\n')
        self.env = dict(os.environ, **GIT_ID, TMPDIR=str(Path(self.tmp.name)))
        self.env.pop("OKF_DRIFT_ROOT", None)
        self.env.pop("OKF_DRIFT_SHIM", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            self.env["XDG_CACHE_HOME"] = str(pin_scripts(self.root, ("okf-log.sh",)))
            (self.root / ".gitignore").write_text("cache/\n")
        split = self.log("split", "knowledge")
        self.assertEqual(split.returncode, 0, split.stdout + split.stderr)
        self.history = (self.bundle / "log.md").read_text()
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.publish()
        self.git("checkout", "-qb", "alice/fix")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, check=True,
                              text=True, capture_output=True).stdout

    def publish(self) -> None:
        """Make the current commit what `origin/HEAD` points at."""
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    def log(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        cwd = cwd or self.root
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            command = ["sh", str(SCRIPTS / "okf-shim.sh"), "--repo-root", str(cwd), "okf-log.sh"]
        else:
            command = ["sh", str(SCRIPTS / "okf-log.sh")]
        return subprocess.run(command + list(args), cwd=cwd, env=self.env, text=True, capture_output=True)

    def entries(self) -> list[str]:
        return sorted(str(p.relative_to(self.root)) for p in self.bundle.glob("log/*/log.md"))

    def add(self, line: str, *opts: str) -> str:
        result = self.log("add", *opts, "knowledge", line)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def assert_refused(self, result: subprocess.CompletedProcess[str], *needles: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        self.assertEqual(self.entries(), [])
        self.assertEqual((self.bundle / "log.md").read_text(), self.history)

    def test_first_write_creates_the_branch_entry_and_names_the_base(self) -> None:
        out = self.add("* one")
        [entry] = self.entries()
        date, slug, _ = re.fullmatch(ENTRY_RE, entry).groups()
        self.assertEqual((date, slug), (TODAY, "fix"))
        self.assertEqual((self.root / entry).read_text(), f"{ALICE}## {TODAY}\n* one\n")
        self.assertIn("origin/HEAD", out)
        self.assertIn(entry, out)
        self.assertEqual((self.bundle / "log.md").read_text(), self.history)

    def test_a_second_write_reuses_the_untracked_entry_newest_first(self) -> None:
        self.add("* one")
        self.add("* two")
        [entry] = self.entries()
        self.assertEqual((self.root / entry).read_text(), f"{ALICE}## {TODAY}\n* two\n* one\n")

    def test_a_staged_entry_is_reused(self) -> None:
        self.add("* one")
        self.git("add", ".")
        self.add("* two")
        [entry] = self.entries()
        self.assertEqual((self.root / entry).read_text(), f"{ALICE}## {TODAY}\n* two\n* one\n")

    def test_a_committed_entry_from_an_earlier_day_is_reused_under_a_new_heading(self) -> None:
        self.add("* one")
        [entry] = self.entries()
        old = self.bundle / "log/2026-01-02-fix-abcd/log.md"
        (self.root / entry).parent.rename(old.parent)
        old.write_text("## 2026-01-02\n* one\n")
        self.git("add", ".")
        self.git("commit", "-qm", "entry")
        self.add("* later")
        self.assertEqual(self.entries(), ["knowledge/log/2026-01-02-fix-abcd/log.md"])
        self.assertEqual(old.read_text(), f"## {TODAY}\n* later\n\n## 2026-01-02\n* one\n")

    def test_a_stacked_branch_does_not_reuse_its_parents_entry(self) -> None:
        self.git("checkout", "-qb", "feat/parser")
        self.add("* parent")
        self.git("add", ".")
        self.git("commit", "-qm", "parent entry")
        self.git("checkout", "-qb", "feat/parser-tests")
        self.add("* child")
        slugs = sorted(re.fullmatch(ENTRY_RE, e).group(2) for e in self.entries())
        self.assertEqual(slugs, ["parser", "parser-tests"])

    def test_a_stacked_branch_with_the_same_slug_gets_its_own_entry(self) -> None:
        self.add("* alice")
        self.git("add", ".")
        self.git("commit", "-qm", "alice entry")
        [alice] = self.entries()
        self.git("checkout", "-qb", "bob/fix")
        self.add("* bob one")
        self.add("* bob two")
        [bob] = [e for e in self.entries() if e != alice]
        self.assertEqual((self.root / alice).read_text(),
                         f"<!-- okf-log branch: alice/fix -->\n## {TODAY}\n* alice\n")
        self.assertEqual((self.root / bob).read_text(),
                         f"<!-- okf-log branch: bob/fix -->\n## {TODAY}\n* bob two\n* bob one\n")

    def test_an_entry_without_a_branch_comment_is_matched_by_slug(self) -> None:
        self.add("* one", "--slug", "fix")
        [entry] = self.entries()
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* one\n")
        self.add("* two")
        self.assertEqual(self.entries(), [entry])
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* two\n* one\n")

    def test_an_entry_already_on_the_base_is_not_reused(self) -> None:
        self.add("* merged earlier")
        self.git("add", ".")
        self.git("commit", "-qm", "entry")
        self.publish()
        self.add("* new work")
        self.assertEqual(len(self.entries()), 2)

    def test_two_branches_with_the_same_last_segment_get_two_folders(self) -> None:
        self.add("* alice")
        self.git("add", ".")
        self.git("commit", "-qm", "alice entry")
        self.git("checkout", "-q", "main")
        self.git("checkout", "-qb", "bob/fix")
        self.add("* bob")
        self.git("add", ".")
        self.git("commit", "-qm", "bob entry")
        self.git("checkout", "-q", "alice/fix")
        self.git("merge", "-q", "--no-edit", "bob/fix")
        entries = self.entries()
        self.assertEqual(len(entries), 2, entries)
        for e in entries:
            self.assertEqual(re.fullmatch(ENTRY_RE, e).groups()[:2], (TODAY, "fix"))

    def test_more_than_one_candidate_refuses_and_asks_for_entry(self) -> None:
        for suffix in ("aaaa", "bbbb"):
            path = self.bundle / f"log/2026-01-02-fix-{suffix}/log.md"
            path.parent.mkdir(parents=True)
            path.write_text("## 2026-01-02\n* x\n")
        result = self.log("add", "knowledge", "* three")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("--entry", result.stderr)
        self.assertNotIn("three", "".join(p.read_text() for p in self.bundle.glob("log/*/log.md")))

    def test_entry_wins_and_skips_headings_inside_fences_and_comments(self) -> None:
        self.add("* mine")
        other = self.bundle / "log/2026-01-02-other-abcd/log.md"
        other.parent.mkdir(parents=True)
        head = "Intro.\n\n```\n## 2026-01-03\n```\n<!--\n## 2026-01-04\n-->\n\n"
        other.write_text(head + "## 2026-01-02\n* x\n")
        self.add("* chosen", "--entry", "knowledge/log/2026-01-02-other-abcd/log.md")
        self.assertEqual(other.read_text(), head + f"## {TODAY}\n* chosen\n\n## 2026-01-02\n* x\n")
        mine = [e for e in self.entries() if "-other-" not in e]
        self.assertEqual((self.root / mine[0]).read_text(), f"{ALICE}## {TODAY}\n* mine\n")

    def test_entry_outside_the_bundles_log_is_refused(self) -> None:
        self.assert_refused(self.log("add", "--entry", "knowledge/log.md", "knowledge", "* x"), "--entry")

    def test_detached_head_refuses_without_slug_and_writes_with_one(self) -> None:
        self.git("checkout", "-q", "--detach")
        self.assert_refused(self.log("add", "knowledge", "* x"), "detached", "--slug")
        self.add("* x", "--slug", "Hot Fix")
        [entry] = self.entries()
        self.assertEqual(re.fullmatch(ENTRY_RE, entry).group(2), "hot-fix")

    def test_the_default_branch_refuses_without_slug(self) -> None:
        self.git("checkout", "-q", "main")
        self.assert_refused(self.log("add", "knowledge", "* x"), "main", "--slug")

    def test_a_missing_base_ref_refuses(self) -> None:
        self.assert_refused(self.log("add", "--base", "origin/nope", "knowledge", "* x"), "origin/nope")
        self.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        self.assert_refused(self.log("add", "knowledge", "* x"), "origin/HEAD", "--base")

    def test_the_base_flag_is_used_and_printed(self) -> None:
        self.git("branch", "trunk", "main")
        out = self.add("* x", "--base", "trunk")
        self.assertIn("trunk", out)
        self.assertEqual(len(self.entries()), 1)

    def test_a_shallow_clone_refuses(self) -> None:
        self.git("commit", "-q", "--allow-empty", "-m", "second")
        self.git("commit", "-q", "--allow-empty", "-m", "third")
        shallow = Path(self.tmp.name) / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--no-single-branch",
                        f"file://{self.root}", str(shallow)], env=self.env, check=True)
        for args in (["remote", "set-head", "origin", "main"], ["checkout", "-qb", "carol/work"]):
            subprocess.run(["git", *args], cwd=shallow, env=self.env, check=True, capture_output=True)
        result = self.log("add", "knowledge", "* x", cwd=shallow)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("shallow", result.stderr)
        self.assertEqual(list((shallow / "knowledge").glob("log/*/log.md")), [])

    def test_an_explicit_slug_needs_no_git_history(self) -> None:
        plain = Path(self.tmp.name) / "plain"
        (plain / "knowledge").mkdir(parents=True)
        result = subprocess.run(["sh", str(SCRIPTS / "okf-log.sh"), "add", "--slug", "setup",
                                 "knowledge", "* Created"], cwd=plain, env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        [entry] = list((plain / "knowledge").glob("log/*/log.md"))
        self.assertRegex(str(entry.relative_to(plain)), ENTRY_RE)
        self.assertEqual(entry.read_text(), f"## {TODAY}\n* Created\n")

    def test_an_explicit_slug_without_git_reuses_its_entry(self) -> None:
        plain = Path(self.tmp.name) / "plain"
        (plain / "knowledge").mkdir(parents=True)
        for line in ("* one", "* two"):
            result = subprocess.run(["sh", str(SCRIPTS / "okf-log.sh"), "add", "--slug", "x",
                                     "knowledge", line], cwd=plain, env=self.env,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        [entry] = list((plain / "knowledge").glob("log/*/log.md"))
        self.assertEqual(entry.read_text(), f"## {TODAY}\n* two\n* one\n")

    def test_todays_heading_as_the_last_line_without_a_newline(self) -> None:
        self.add("* one")
        [entry] = self.entries()
        (self.root / entry).write_text(f"## {TODAY}")
        self.add("* two")
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* two\n")

    def unsplit(self, history: bytes) -> None:
        (self.bundle / "log.md").write_bytes(history)

    def test_split_freezes_the_root_log_with_a_marker_hashing_the_history(self) -> None:
        history = b"# Log\n\n## 2026-01-01\n* history before the split\n"
        self.unsplit(history)
        result = self.log("split", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = (self.bundle / "log.md").read_bytes()
        self.assertTrue(data.startswith(history), data)
        above, date, digest = frozen_parts(data)
        self.assertEqual(date, TODAY)
        self.assertEqual(digest, hashlib.sha256(above).hexdigest())
        self.assertIn(b"log/", above[len(history):])
        self.assertTrue((self.bundle / "log").is_dir())

    def test_split_twice_changes_nothing(self) -> None:
        frozen = (self.bundle / "log.md").read_bytes()
        result = self.log("split", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("already frozen", result.stdout)
        self.assertEqual((self.bundle / "log.md").read_bytes(), frozen)

    def test_refreeze_rehashes_a_deliberate_fix_and_keeps_the_split_date(self) -> None:
        self.unsplit(b"# Log\n\n## 2026-01-01\n* a typo\n")
        self.log("split", "knowledge")
        text = (self.bundle / "log.md").read_bytes()
        _, date, old = frozen_parts(text)
        (self.bundle / "log.md").write_bytes(text.replace(b"a typo", b"the fix"))
        result = self.log("split", "--refreeze", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        above, new_date, new = frozen_parts((self.bundle / "log.md").read_bytes())
        self.assertEqual(new_date, date)
        self.assertNotEqual(new, old)
        self.assertEqual(new, hashlib.sha256(above).hexdigest())
        self.assertIn(b"the fix", above)

    def test_refreeze_of_an_unfrozen_log_refuses(self) -> None:
        self.unsplit(b"# Log\n")
        result = self.log("split", "--refreeze", "knowledge")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual((self.bundle / "log.md").read_bytes(), b"# Log\n")

    def test_split_of_a_crlf_log_hashes_the_history_as_lf(self) -> None:
        history = b"# Log\r\n\r\n## 2026-01-01\r\n* history before the split\r\n"
        self.unsplit(history)
        self.log("split", "knowledge")
        data = (self.bundle / "log.md").read_bytes()
        self.assertTrue(data.startswith(history))
        above, _, digest = frozen_parts(data)
        self.assertEqual(digest, hashlib.sha256(above.replace(b"\r\n", b"\n")).hexdigest())

    def test_text_below_the_marker_refuses_split_and_refreeze(self) -> None:
        log = self.bundle / "log.md"
        log.write_text(self.history + "* added below\n")
        for args in (["split"], ["split", "--refreeze"]):
            with self.subTest(args=args):
                result = self.log(*args, "knowledge")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("below the marker", result.stderr)
                self.assertEqual(log.read_text(), self.history + "* added below\n")

    def test_add_refuses_an_unmigrated_bundle_and_names_okf_migrate(self) -> None:
        self.unsplit(b"# Log\n")
        self.history = "# Log\n"
        self.assert_refused(self.log("add", "knowledge", "* x"), "/okf-migrate")



if __name__ == "__main__":
    unittest.main(verbosity=2)
