#!/usr/bin/env python3
"""Install/convert only OKF integration. Python 3.11+, no third-party imports; plugin-local, never copied.

No scaffold, binding or bundle writes. Preflight all candidates before staging a pin or
changing anything. Unknown integrations require a human merge, not a guessed migration.
"""
import argparse
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib

PLUGIN = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN / "skills/okf-setup/templates"
MINIMUM = (0, 7, 0)
# Measured from official source tags, NOT from the consumer's possibly upgraded pin.
# v0.5.0/v0.5.1, then v0.6.0/v0.6.1/v0.6.2 respectively.
SHIMS = {
    "8d97f7a7a70341f346a32cde9b319258fb81baa95c5c666c70501b1509c1c185",
    "6767117dcfb9e1bc5096f102af3edac1f5ac246bdbc9097084dad1d4a43ece79",
}
WORKFLOWS = {
    "84c2669a3da9249431771f8a861074161ce7edca73430c534eee546c87d16260",
    "c9cfd3865f4886360e6c3b0259c4a6906f9d616606fcc16016a0e63c9da333a3",
}
# Accepted official template digests; the current template text is compared separately.
# Each entry names the releases whose template body digests to it, measured from the
# source tags. The OUTGOING release's digests must be here BEFORE the template changes,
# or every consumer still carrying the previous official body is refused as customized.
SECTIONS = {
    "Knowledge Bundle": {
        "0c641e5e55c92165a85e76920416b1676906c7c24db4cf33c4a5d044f3d6b485",  # v0.4.0-v0.6.2
        "372e7ee23c7fe542a3808c6724fd590df150a9d4c77037739a8da4303edefe8d",  # v0.7.0-v0.8.2
    },
    "Work Loop": {
        "c8ad36698d80128dae3b77e4f34b82d0c50ebddb50f54313cccf6fcb125ba214",  # v0.4.0-v0.6.2
        "0b46146628754f0316d682ae29210bd17a928076c174eef433236f41eee4849c",  # v0.7.0
        "dfacead5b7d2f4ad91889329fb157a59a13bf3edc1aedd2d5c492b027279f09f",  # v0.8.0-v0.8.2
    },
}
LEGACY = [f"scripts/{name}.sh" for name in ("okf-check", "okf-recall", "okf-shim")]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(root, relative):
    path = root / relative
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"{part}: symlink; no changes made")
    if path.exists() and not path.is_file():
        raise ValueError(f"{path}: not a regular file")
    return path.read_bytes() if path.exists() else None


def sections(text):
    found = {}
    for match in re.finditer(r"^## ([^\n]+)\n.*?(?=^## |\Z)", text, re.M | re.S):
        title = match[1]
        if title in found and title in (*SECTIONS, "Navigation"):
            raise ValueError(f"CLAUDE.md: duplicate {title} section")
        found[title] = match
    return found


def instructions(old):
    template = (TEMPLATES / "CLAUDE-knowledge-section.md").read_text()
    target = sections(template)
    text = old.decode() if old is not None else ""
    existing = sections(text)
    # Navigation is project-owned: preserve any existing read order byte-for-byte.
    for title in SECTIONS:
        if title in existing:
            body = existing[title][0].rstrip()
            if body != target[title][0].rstrip() and digest(body.encode()) not in SECTIONS[title]:
                raise ValueError(f"CLAUDE.md: customized {title} section; merge explicitly")
    for title in (*SECTIONS, "Navigation"):
        existing = sections(text)
        new = target[title][0].rstrip()
        if title in existing:
            if title == "Navigation":
                continue
            match = existing[title]
            end = match.start() + len(match[0].rstrip())
            text = text[:match.start()] + new + text[end:]
        else:
            text += ("\n\n" if text and not text.endswith("\n\n") else "") + new + "\n\n"
    return text.encode()


def validate_pin(data):
    lines = data.decode().splitlines()
    if not lines or not re.fullmatch(r"v\d+\.\d+\.\d+", lines[0]):
        raise ValueError(".okf-drift-version: invalid tag; use --tag with an explicit release")
    if tuple(map(int, lines[0][1:].split("."))) < MINIMUM:
        raise ValueError(".okf-drift-version: requires v0.7.0 or newer; use --tag v0.7.0 after publication")
    hashes = {}
    for line in lines[1:]:
        match = re.fullmatch(r"([0-9a-f]{64})  (okf-[a-z0-9-]+\.(?:sh|py))", line)
        if not match or match[2] in hashes:
            raise ValueError(".okf-drift-version: malformed or duplicate digest")
        hashes[match[2]] = match[1]
    for name in ("okf-shim.sh", "okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh"):
        if name not in hashes:
            raise ValueError(f".okf-drift-version: missing digest for {name}")


def protects(target, removed, root):
    if not isinstance(target, str):
        raise ValueError("non-string code_ref/binding target")
    path = target.split("#", 1)[0]
    # Includes directory code_refs, glob targets, dotted paths and absolute paths.
    # Resolve aliases too: deleting the real script would break a binding to its symlink.
    normalized = os.path.relpath((root / path).resolve(), root)
    return any(normalized == "." or name == normalized or name.startswith(normalized + "/")
               or fnmatch.fnmatchcase(name, normalized) for name in removed)


def code_refs(front):
    """Read code_refs from frontmatter text with the bundle's own line rule.

    The bootstrap and the gate parse frontmatter line by line, and okf accepts values a
    strict YAML parser rejects -- a description whose value starts with an unquoted
    backtick, for one, which 12 concepts on the reference consumer carry. Only code_refs
    is needed here, so read it the same way rather than parsing the whole mapping.
    """
    def unquote(value):
        return re.sub(r"""^(["'])(.*)\1$""", r"\2", value)

    refs, inside = [], False
    for line in front.split("\n"):
        opener = re.fullmatch(r"code_refs:\s*(.*?)\s*", line)
        if opener:
            # An inline sequence closes the block immediately; "code_refs: []" is empty.
            inside = not opener[1]
            if opener[1].startswith("[") and opener[1].endswith("]"):
                refs.extend(item for item in
                            (unquote(x.strip()) for x in opener[1][1:-1].split(",")) if item)
            continue
        if re.match(r"[A-Za-z_]+:", line):
            inside = False
            continue
        item = re.fullmatch(r"\s*-\s+(.+?)\s*", line) if inside else None
        if item:
            refs.append(unquote(item[1]))
    return refs


def check_bindings(root, removed):
    bundle = root / "knowledge"
    if bundle.is_symlink():
        raise ValueError(f"{bundle}: symlink; cannot verify deletion safety")
    for file in sorted(bundle.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"{file}: symlink; cannot verify deletion safety")
        if not file.is_file() or file.suffix != ".md":
            continue
        text = file.read_text()
        if text.startswith("---\n"):
            parts = text.split("\n---", 2)
            if len(parts) < 2:
                raise ValueError(f"{file}: malformed frontmatter")
            if any(protects(ref, removed, root) for ref in code_refs(parts[0][4:])):
                raise ValueError(f"{file}: code_refs binds a deletion candidate; migration refused")
        if any(name in text for name in LEGACY):
            print(f"okf-integrate: historical operational reference in {file}; left untouched, CLAUDE.md is authoritative", file=sys.stderr)
    lock = regular(root, "drift.lock")
    if lock is not None:
        bindings = tomllib.loads(lock.decode()).get("bindings", [])
        if not isinstance(bindings, list):
            raise ValueError("drift.lock: malformed bindings")
        for binding in bindings:
            if not isinstance(binding, dict) or "target" not in binding:
                raise ValueError("drift.lock: malformed binding target")
            if protects(binding["target"], removed, root):
                raise ValueError("drift.lock: binding targets a deletion candidate; migration refused")


def workflow_name(root):
    """The consumer's gate workflow. The template ships `.yml`, but a repository whose
    every other workflow is `.yaml` renames it; writing the template name regardless
    would install a SECOND gate beside the one already there."""
    renamed = ".github/workflows/knowledge.yaml"
    if (root / renamed).is_file() and not (root / ".github/workflows/knowledge.yml").is_file():
        return renamed
    return ".github/workflows/knowledge.yml"


def integrate(root, tag, dry_run):
    gate = workflow_name(root)
    candidates = [*LEGACY, "CLAUDE.md", gate, ".okf-drift-version"]
    before = {name: regular(root, name) for name in candidates}
    removed = []
    for name in LEGACY:
        data = before[name]
        if data is None:
            continue
        basename = Path(name).name
        if basename == "okf-shim.sh":
            recognized = digest(data) in SHIMS
        else:
            command = f'exec "$(dirname "$0")/okf-shim.sh" {basename} "$@"\n'
            comment = f"# {basename} from alvistar/okf-drift at the tag in .okf-drift-version — see scripts/okf-shim.sh.\n"
            recognized = data in [("#!/bin/sh\n" + command).encode(), ("#!/bin/sh\n" + comment + command).encode()]
        if not recognized:
            raise ValueError(f"{root / name}: unrecognized or customized legacy file")
        removed.append(name)
    changes = {"CLAUDE.md": instructions(before["CLAUDE.md"])}
    workflow = (TEMPLATES / "knowledge.yml").read_bytes()
    old_workflow = before[gate]
    if old_workflow is not None and old_workflow != workflow and digest(old_workflow) not in WORKFLOWS:
        raise ValueError(f"{root / gate}: customized workflow; merge explicitly")
    changes[gate] = workflow
    check_bindings(root, removed)
    # Pin generation is staged only AFTER every consumer candidate passed preflight.
    if tag:
        with tempfile.TemporaryDirectory(prefix="okf-pin-stage-") as stage:
            subprocess.run(["sh", str(PLUGIN / "scripts/okf-pin.sh"), tag, stage], check=True)
            changes[".okf-drift-version"] = (Path(stage) / ".okf-drift-version").read_bytes()
    pin = changes.get(".okf-drift-version", before[".okf-drift-version"])
    if pin is None:
        raise ValueError("missing .okf-drift-version; choose a released --tag v0.7.0 or newer")
    validate_pin(pin)
    changes = {name: data for name, data in changes.items() if data != before[name]}
    for name in changes:
        print(f"write {root / name}")
    for name in removed:
        print(f"remove {root / name}")
    if dry_run:
        return
    # Recheck candidates immediately before applying, catching edits during a download.
    for name, data in before.items():
        if regular(root, name) != data:
            raise ValueError(f"{root / name}: changed during preflight; retry")
    for name, data in changes.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".okf-integrate-", delete=False) as file:
            staged = Path(file.name)
            try:
                file.write(data)
                file.flush()
                os.chmod(staged, path.stat().st_mode & 0o777 if path.exists() else 0o644)
                os.replace(staged, path)
            finally:
                staged.unlink(missing_ok=True)
    for name in removed:
        (root / name).unlink()
    print("okf-integrate: integration current; knowledge/ and drift.lock untouched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--tag", help="explicit pin upgrade, using release SHA256SUMS; minimum v0.7.0")
    parser.add_argument("--dry-run", action="store_true", help="preflight and show changes without writing")
    args = parser.parse_args()
    try:
        root = args.repo_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"{root}: not a directory")
        integrate(root, args.tag, args.dry_run)
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"okf-integrate: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
