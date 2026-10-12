#!/usr/bin/env python3
"""Offline regressions for gate/recall process boundaries, paths and JSON transport.

Run with python3 scripts/okf-runtime-selftest.py. Fixtures replace only okf/drift;
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
        (self.bundle / "project/index.md").write_text(
            "- [State](/project/state.md) — Fixture state.\n"
        )
        (self.bundle / "project/state.md").write_text(
            "---\ntype: Reference\ntitle: State\ndescription: Fixture state.\n"
            "last_updated: 2026-09-16\ncode_refs: []\n---\n"
            "# State\n\n**Working:**\n- Fixture.\n\n"
            "**Not yet built:**\n- Nothing.\n\n**Known issues:**\n- None.\n"
        )
        (self.root / "drift.lock").write_text("{}")
        self.stub = self.root / "bin"
        self.stub.mkdir()
        for name, text in {
            "okf": '#!/bin/sh\ncase "$1" in\nversion) echo "okf v0.6.0";;\nvalidate) cat "$FIXTURE/validate.json"; exit "${VALIDATE_EXIT:-0}";;\nsearch) cat "$FIXTURE/search.json"; exit "${SEARCH_EXIT:-0}";;\nesac\n',
            "drift": '#!/bin/sh\ncase "$1" in\n--version) echo "drift ${DRIFT_VERSION:-v0.10.1}"; exit 0;;\nesac\ncat "$FIXTURE/drift.json"\nexit "${DRIFT_EXIT:-0}"\n',
        }.items():
            path = self.stub / name
            path.write_text(text)
            path.chmod(0o755)
        self.env = dict(os.environ, FIXTURE=str(self.root), TMPDIR=str(self.root),
                        PATH=str(self.stub) + os.pathsep + os.environ["PATH"])
        self.env.pop("OKF_DRIFT_ROOT", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            # The exact unpublished runtime bytes, pinned in a fixture release cache.
            # No scripts live in the consumer; exercise all 13 contracts via the launcher.
            cache = self.root / "cache/okf-drift/v0.7.0"
            cache.mkdir(parents=True)
            self.env["XDG_CACHE_HOME"] = str(self.root / "cache")
            lines = ["v0.7.0"]
            for name in ("okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh",
                         "okf-restamp.sh", "okf-tidy.sh"):
                data = (SCRIPTS / name).read_bytes()
                (cache / name).write_bytes(data)
                lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
            (self.root / ".okf-drift-version").write_text("\n".join(lines) + "\n")
        self.payload("validate", {"gate_passed": True, "is_conformant": True})
        self.payload("search", [{"concept_id": "project/state", "description": "Fixture state.", "score": 1}])
        self.verdict("fresh")

    def payload(self, name: str, value: object) -> None:
        (self.root / f"{name}.json").write_text(json.dumps(value))

    def verdict(self, result: str) -> None:
        self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": result, "anchors": [], "links": []}]})

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
                stale_after: str | None = None) -> None:
        """A second fixture concept, written only where a test needs one. It is deliberately
        NOT in setUp: the gate requires an index row and a drift verdict for every concept,
        and recall requires neither."""
        path = self.bundle / f"{rel}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["type: Reference", "title: Second", "description: Second fixture.",
                 "last_updated: 2026-09-16"]
        if status is not None:
            lines.append(f"status: {status}")
        if stale_after is not None:
            lines.append(f"stale_after: {stale_after}")
        path.write_text("---\n" + "\n".join(lines) + "\n---\n# Second\n\nBody.\n")

    def two_hits(self, anchors: list[object]) -> None:
        self.payload("search", [
            {"concept_id": "project/state", "description": "Fixture state.", "score": 2},
            {"concept_id": "architecture/core", "description": "Second fixture.", "score": 1},
        ])
        self.payload("drift", {"docs": [
            {"path": "knowledge/project/state.md", "result": "fresh",
             "anchors": anchors, "links": []},
            {"path": "knowledge/architecture/core.md", "result": "fresh",
             "anchors": [], "links": []},
        ]})

    def anchor(self, symbol: str) -> dict:
        return {"identity": f"src/lib.rs#{symbol}", "kind": "symbol", "path": "src/lib.rs",
                "symbol": symbol, "result": "fresh", "reason": None, "blame": None}

    def test_recall_prints_tracking_lifecycle_and_review_per_hit(self) -> None:
        self.concept("architecture/core", status="deprecated", stale_after="2026-01-01")
        self.two_hits([self.anchor("a"), self.anchor("b")])
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('2 hit(s) for "fixture" in knowledge', result.stdout)
        self.assertIn("2 targets unchanged · no status · no review date", result.stdout)
        self.assertIn("no tracked target · deprecated · review expired 2026-01-01",
                      result.stdout)
        self.assertIn('"targets unchanged" means the code under the anchors did not move.',
                      result.stdout)

    def test_recall_counts_one_anchor_in_the_singular_and_reads_a_future_review(self) -> None:
        self.concept("architecture/core", status="stable", stale_after="2099-01-01")
        self.two_hits([self.anchor("a")])
        result = self.run_script("okf-recall.sh")
        self.assertIn("1 target unchanged · no status · no review date", result.stdout)
        self.assertIn("no tracked target · stable · review current", result.stdout)

    def test_recall_marks_a_deprecated_concept_whose_code_moved_stale(self) -> None:
        """Staleness takes the tracking signal's place; the lifecycle signal still shows."""
        self.concept("architecture/core", status="deprecated")
        self.payload("search", [
            {"concept_id": "architecture/core", "description": "Second fixture.", "score": 1},
        ])
        self.payload("drift", {"docs": [{
            "path": "knowledge/architecture/core.md", "result": "stale",
            "anchors": [{"identity": "src/lib.rs#a", "kind": "symbol", "path": "src/lib.rs",
                         "symbol": "a", "result": "stale",
                         "reason": {"code": "changed_after_baseline", "message": "m"},
                         "blame": {}}],
            "links": []}]})
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 hit(s)", result.stdout)
        self.assertIn("— 1 STALE", result.stdout)
        self.assertIn("STALE: code moved after it was written · deprecated ·", result.stdout)
        self.assertIn("src/lib.rs#a  [changed_after_baseline]", result.stdout)
        self.assertNotIn("WITHHELD", result.stdout)
        self.assertNotIn('"targets unchanged" means', result.stdout)

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
                self.two_hits([self.anchor("a")])
                result = self.run_script("okf-recall.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                expected = label if label == "review current" else f"{label} {date}"
                self.assertIn(f"no tracked target · stable · {expected}\n", result.stdout)

    def test_recall_names_an_invalid_review_date(self) -> None:
        # Value: protects=an impossible stale_after is named, not hidden as "no review date"; fails_when=day_number errors fall back silently; why_new=only valid dates were tested; seam=none
        for date in ("2026-13-01", "0999-01-01"):
            with self.subTest(date=date):
                self.concept("architecture/core", status="stable", stale_after=date)
                self.two_hits([self.anchor("a")])
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
        have no file in the bundle and no drift verdict."""
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
        """Four concepts that separate the two diagnostics. Coverage comes from drift's
        report, discoverability from `code_refs`, and the pairs deliberately disagree:
        `architecture/core` has neither, `playbooks/thing` has code_refs but no anchor,
        `playbooks/bound` has both, and `project/state` is exempt from both."""
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
        anchor = {"identity": "src/lib.rs#a", "kind": "symbol", "path": "src/lib.rs",
                  "symbol": "a", "result": "fresh", "reason": None, "blame": None}
        self.payload("drift", {"docs": [
            {"path": "knowledge/project/state.md", "result": "fresh",
             "anchors": [anchor], "links": []},
            {"path": "knowledge/architecture/core.md", "result": "fresh",
             "anchors": [], "links": []},
            {"path": "knowledge/playbooks/thing.md", "result": "fresh",
             "anchors": [], "links": []},
            {"path": "knowledge/playbooks/bound.md", "result": "fresh",
             "anchors": [anchor], "links": []},
        ]})

    def test_gate_groups_coverage_and_discoverability_separately(self) -> None:
        self.gate_bundle()
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # One line per diagnostic, wrapped at ~100 chars with a continuation indent.
        self.assertIn(
            "warn  2 concept(s) with no tracked target (no drift anchor; nothing checks "
            "them): architecture/core.md,\n        playbooks/thing.md\n",
            result.stdout,
        )
        self.assertIn(
            "warn  1 concept(s) with empty code_refs (okf search --for-path cannot find "
            "them): architecture/core.md",
            result.stdout,
        )
        # A concept that has both is in neither list; the exempt snapshot is in neither.
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
        self.payload("drift", {"docs": [
            {"path": f"knowledge/project/{name}.md", "result": "fresh", "anchors": [], "links": []}
            for name in ("state", "state-evidence")
        ]})
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

    def test_require_tracking_is_fatal_only_for_the_matching_glob(self) -> None:
        self.gate_bundle()
        self.env["OKF_REQUIRE_TRACKING"] = "architecture/*"
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "FAIL  architecture/core.md: no tracked target, and "
            "OKF_REQUIRE_TRACKING='architecture/*' makes that fatal for this path",
            result.stdout,
        )
        self.assertNotIn("FAIL  playbooks/thing.md", result.stdout)
        self.assertIn("2 concept(s) with no tracked target", result.stdout)
        # `*` stops at a `/`, as it does in the shell: a bare `*` matches no concept in a
        # bundle whose concepts all live in a category directory.
        self.env["OKF_REQUIRE_TRACKING"] = "*"
        bare = self.run_script("okf-check.sh")
        self.assertEqual(bare.returncode, 0, bare.stdout + bare.stderr)
        # `**` does cross one.
        self.env["OKF_REQUIRE_TRACKING"] = "**"
        deep = self.run_script("okf-check.sh")
        self.assertEqual(deep.returncode, 1, deep.stdout + deep.stderr)

    def test_require_tracking_unset_leaves_coverage_a_warning(self) -> None:
        self.gate_bundle()
        self.env.pop("OKF_REQUIRE_TRACKING", None)
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("no tracked target, and OKF_REQUIRE_TRACKING", result.stdout)

    @unittest.skipIf(os.environ.get("OKF_SELFTEST_PINNED") == "1",
                     ".okf-drift-version is the launcher's own input in pinned mode")
    def test_a_repo_that_adopted_drift_fails_when_drift_is_absent(self) -> None:
        """A green gate must mean the detector ran. Without this the worker who has no
        drift gets two green local runs and a red CI."""
        pin = self.root / ".okf-drift-version"
        if not pin.exists():
            pin.write_text("v0.9.0\n")
        (self.stub / "drift").unlink()
        # Keep the system tools the scripts need; drop every directory that could hold a
        # real drift (~/.local/bin, GOPATH/bin).
        self.env["PATH"] = os.pathsep.join([str(self.stub), "/usr/bin", "/bin",
                                            "/usr/sbin", "/sbin"])
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  this repository adopted drift", result.stdout)
        self.assertNotIn("okf gate passed", result.stdout)

    @unittest.skipIf(os.environ.get("OKF_SELFTEST_PINNED") == "1",
                     ".okf-drift-version is the launcher's own input in pinned mode")
    def test_a_repo_that_never_adopted_drift_still_only_warns(self) -> None:
        (self.root / ".okf-drift-version").unlink(missing_ok=True)
        (self.stub / "drift").unlink()
        self.env["PATH"] = os.pathsep.join([str(self.stub), "/usr/bin", "/bin",
                                            "/usr/sbin", "/sbin"])
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warn  drift not on PATH", result.stdout)
        self.assertNotIn("FAIL", result.stdout)
        # Coverage is unknowable without the report, so it is not guessed at.
        self.assertNotIn("no tracked target", result.stdout)

    def wiki(self) -> None:
        """A wiki bundle: `.okf-profile` says wiki, no drift.lock, no drift binary, no
        project snapshot, and one reference concept with no code_refs at all."""
        (self.root / ".okf-profile").write_text("wiki\n")
        (self.root / "drift.lock").unlink()
        (self.stub / "drift").unlink()
        self.env["PATH"] = os.pathsep.join([str(self.stub), "/usr/bin", "/bin",
                                            "/usr/sbin", "/sbin"])
        shutil.rmtree(self.bundle / "project")
        (self.bundle / "reference").mkdir()
        (self.bundle / "reference/index.md").write_text(
            "- [Identity](/reference/identity.md) — Who I am.\n")
        (self.bundle / "reference/identity.md").write_text(
            "---\ntype: Reference\ntitle: Identity\ndescription: Who I am.\n"
            "last_updated: 2026-09-29\nstale_after: 2099-01-01\n---\n# Identity\n\nBody.\n")
        self.payload("search", [{"concept_id": "reference/identity",
                                 "description": "Who I am.", "score": 1}])

    def test_wiki_gate_needs_no_drift_snapshot_or_code_refs(self) -> None:
        self.wiki()
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("warn  ", result.stdout)
        self.assertIn("passed with no warnings", result.stdout)
        self.assertIn("step 6 not applicable (wiki profile, no drift.lock)", result.stdout)

    def test_wiki_recall_serves_hits_as_not_drift_tracked(self) -> None:
        self.wiki()
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 hit(s)", result.stdout)
        self.assertIn("not drift-tracked (wiki) · no status · review current", result.stdout)
        self.assertNotIn("targets unchanged", result.stdout)

    def test_wiki_with_a_drift_lock_still_marks_stale(self) -> None:
        # A wiki that hand-linked a concept adopted drift for it: the join comes back.
        (self.root / ".okf-profile").write_text("wiki\n")
        self.verdict("stale")
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STALE: code moved after it was written", result.stdout)
        self.assertNotIn("not drift-tracked", result.stdout)

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

    def test_wiki_gate_with_a_drift_lock_fails_on_stale(self) -> None:
        (self.root / ".okf-profile").write_text("wiki\n")
        self.verdict("stale")
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("not applicable", result.stdout)

    @unittest.skipIf(os.environ.get("OKF_SELFTEST_PINNED") == "1",
                     "removes the pin the launcher needs; the unpinned run covers it")
    def test_wiki_with_a_lock_but_no_drift_does_not_claim_not_applicable(self) -> None:
        (self.root / ".okf-profile").write_text("wiki\n")
        (self.root / ".okf-drift-version").unlink(missing_ok=True)
        (self.stub / "drift").unlink()
        self.env["PATH"] = os.pathsep.join([str(self.stub), "/usr/bin", "/bin",
                                            "/usr/sbin", "/sbin"])
        result = self.run_script("okf-check.sh")
        self.assertIn("step 6 did not run (drift not on PATH)", result.stdout)
        self.assertNotIn("not applicable", result.stdout)

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

    def test_scaffold_refusals_write_nothing(self) -> None:
        cases = {
            "wiki over a code profile": (("--profile", "wiki"), {".okf-profile": "code\n"}),
            "code over a wiki profile": ((), {".okf-profile": "wiki\n"}),
            "wiki into a repo with a drift.lock": (("--profile", "wiki"), {"drift.lock": ""}),
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

    def workflow(self, name: str, drift_version: str) -> None:
        """The consumer's own gate workflow, as /okf-setup installs it (`.yml`) or as a
        repository whose every other workflow is `.yaml` renames it."""
        path = self.root / ".github/workflows" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "      - name: okf v0.6.0 and drift, pinned\n"
            "        run: |\n"
            "          go install github.com/okf-memory/okf-agent-memory/cmd/okf@v0.6.0\n"
            f"          curl -fsSL https://drift.fp.dev/install.sh | sh -s -- --version {drift_version}\n"
        )

    def test_drift_version_mismatch_is_fatal_under_either_workflow_extension(self) -> None:
        """The pin is read from `knowledge.yml` OR `knowledge.yaml`. With a single
        hardcoded name, renaming the workflow to the repository's own convention disabled
        this check in silence — the gate stayed green with the two detectors disagreeing."""
        for name in ("knowledge.yml", "knowledge.yaml"):
            with self.subTest(workflow=name):
                self.setUp()
                self.workflow(name, "v0.10.1")
                self.env["DRIFT_VERSION"] = "v0.9.9"
                result = self.run_script("okf-check.sh")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("FAIL  drift on PATH is 'v0.9.9'", result.stdout)
                # The message names the file that was actually read, not a guess.
                self.assertIn(f".github/workflows/{name} pins 'v0.10.1'", result.stdout)
                self.assertNotIn("okf gate passed", result.stdout)

    def test_drift_version_agreement_leaves_the_gate_green(self) -> None:
        for name in ("knowledge.yml", "knowledge.yaml"):
            with self.subTest(workflow=name):
                self.setUp()
                self.workflow(name, "v0.10.1")
                self.env["DRIFT_VERSION"] = "v0.10.1"
                result = self.run_script("okf-check.sh")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("different detectors", result.stdout)

    def test_gate_and_recall_accept_fresh_verdict(self) -> None:
        for script in ("okf-check.sh", "okf-recall.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_gate_rejects_empty_drift_after_success_or_failure(self) -> None:
        (self.root / "drift.json").write_text("")
        for code in ("0", "7"):
            self.env["DRIFT_EXIT"] = code
            with self.subTest(code=code):
                result = self.run_script("okf-check.sh")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_gate_rejects_malformed_drift_json(self) -> None:
        (self.root / "drift.json").write_text("garbage")
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("drift check produced no JSON", result.stdout)

    def test_gate_rejects_nonzero_tools_even_with_fresh_json(self) -> None:
        for variable in ("DRIFT_EXIT", "VALIDATE_EXIT"):
            self.env[variable] = "7"
            with self.subTest(variable=variable):
                self.assert_unusable(self.run_script("okf-check.sh"))
            del self.env[variable]

    def test_gate_reports_stale_json_even_with_nonzero_status(self) -> None:
        self.verdict("stale")
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-check.sh")
        self.assert_unusable(result)
        self.assertIn("drift result 'stale'", result.stdout)

    def test_gate_accepts_nonfresh_drift_outside_bundle(self) -> None:
        self.payload("drift", {"docs": [
            {"path": "knowledge/project/state.md", "result": "fresh", "anchors": [], "links": []},
            {"path": "docs/outside.md", "result": "broken", "anchors": [], "links": []},
        ]})
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "note  drift reports 1 non-fresh doc(s) outside knowledge; not gated here",
            result.stdout,
        )

    def test_gate_rejects_nonzero_drift_with_all_fresh_docs(self) -> None:
        self.verdict("fresh")
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-check.sh")
        self.assert_unusable(result)
        self.assertIn("drift check exited 1", result.stdout)

    def test_recall_marks_stale_for_equivalent_paths(self) -> None:
        self.verdict("stale")
        self.env["DRIFT_EXIT"] = "1"
        for bundle in ("knowledge", "./knowledge", "knowledge/", str(self.bundle)):
            with self.subTest(bundle=bundle):
                result = self.run_script("okf-recall.sh", bundle)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("1 hit(s) for \"fixture\" in", result.stdout)
                self.assertIn("— 1 STALE", result.stdout)
                self.assertNotIn("targets unchanged", result.stdout)

    def test_recall_labels_a_dead_link_broken_not_stale(self) -> None:
        self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": "broken",
                                         "anchors": [], "links": [{"target": "gone.md", "line": 3,
                                                                    "result": "broken"}]}]})
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BROKEN LINK: it points at a file that does not exist", result.stdout)
        self.assertIn("broken link at line 3: gone.md", result.stdout)
        self.assertNotIn("STALE: code moved", result.stdout)

    def test_gate_caps_a_long_warning_list_unless_verbose(self) -> None:
        # Value: protects=the coverage list stays 8 names + a count; fails_when=the cap or OKF_VERBOSE breaks; why_new=no test had >8 concepts; seam=none
        rows = []
        docs = [{"path": "knowledge/project/state.md", "result": "fresh", "anchors": [], "links": []}]
        for i in range(10):
            self.concept(f"architecture/c{i:02d}")
            rows.append(f"- [Second](/architecture/c{i:02d}.md) — Second fixture.")
            docs.append({"path": f"knowledge/architecture/c{i:02d}.md", "result": "fresh", "anchors": [], "links": []})
        (self.bundle / "architecture/index.md").write_text("\n".join(rows) + "\n")
        self.payload("drift", {"docs": docs})
        capped = self.run_script("okf-check.sh")
        self.assertIn("10 concept(s) with no tracked target", capped.stdout)
        self.assertIn("… and 2 more (OKF_VERBOSE=1 lists them)", capped.stdout)
        self.assertNotIn("architecture/c09.md", capped.stdout)
        self.env["OKF_VERBOSE"] = "1"
        full = self.run_script("okf-check.sh")
        self.assertIn("architecture/c09.md", full.stdout)
        self.assertNotIn("more (OKF_VERBOSE=1", full.stdout)

    def test_gate_suggests_the_sweep_once_for_several_drifted_anchors(self) -> None:
        # Value: protects=one sweep hint when >1 anchor drifted; fails_when=the count or threshold breaks; why_new=only the single-anchor case was tested; seam=none
        stale = lambda name: {"identity": f"src/{name}.c", "path": f"src/{name}.c", "result": "stale",
                              "reason": {"code": "changed_after_baseline", "message": "m"}, "blame": {}}
        self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": "stale",
                                         "anchors": [stale("a"), stale("b")], "links": []}]})
        self.env["DRIFT_EXIT"] = "1"
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("okf-restamp.sh --format-only"), 1)
        self.assertIn("note  2 anchor(s) drifted", result.stdout)

    def test_recall_without_drift_searches_and_says_so(self) -> None:
        """No binary, or no lock: a warning and a labelled search, not exit 2."""
        no_drift = self.root / "nodrift"
        no_drift.mkdir()
        os.symlink(self.stub / "okf", no_drift / "okf")
        for case in ("binary", "lock"):
            with self.subTest(case=case):
                env = dict(self.env)
                if case == "binary":
                    env["PATH"] = str(no_drift) + os.pathsep + "/usr/bin:/bin"
                else:
                    (self.root / "drift.lock").rename(self.root / "drift.lock.off")
                saved, self.env = self.env, env
                try:
                    result = self.run_script("okf-recall.sh")
                finally:
                    self.env = saved
                    if case == "lock":
                        (self.root / "drift.lock.off").rename(self.root / "drift.lock")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("warn  drift did not run (", result.stdout)
                self.assertIn("1 hit(s)", result.stdout)
                self.assertIn("drift not run · no status", result.stdout)

    def test_recall_with_a_failing_drift_is_still_unusable(self) -> None:
        self.env["DRIFT_EXIT"] = "3"
        self.assert_unusable(self.run_script("okf-recall.sh"))

    def stale_symbol(self, blame: object = None) -> None:
        """A doc whose ONLY stale anchor is a symbol binding. `path` and `identity` differ
        here on purpose: a repair printed from `path` binds the whole file and leaves the
        symbol anchor exactly as stale as it was."""
        self.payload("drift", {"docs": [{
            "path": "knowledge/project/state.md",
            "result": "stale",
            "anchors": [{
                "identity": "src/lib.rs#admit_reusable",
                "raw": "src/lib.rs#admit_reusable@sig:1d22599b721b091a",
                "kind": "symbol",
                "path": "src/lib.rs",
                "symbol": "admit_reusable",
                "provenance": {"kind": "sig", "value": "1d22599b721b091a"},
                "result": "stale",
                "reason": {"code": "changed_after_baseline", "message": "content changed"},
                "blame": blame if blame is not None else {
                    "author": "Alessandro Viganò",
                    "commit": "0123456789abcdef0123456789abcdef01234567",
                    "date": "2026-09-16T20:18:31+02:00",
                    "subject": "chore: reformat, unrelated",
                },
            }],
            "links": [],
        }]})
        self.env["DRIFT_EXIT"] = "1"

    def test_gate_restamp_command_names_the_symbol_binding_not_the_file(self) -> None:
        self.stale_symbol()
        result = self.run_script("okf-check.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "okf-restamp.sh 'knowledge/project/state.md' 'src/lib.rs#admit_reusable' "
            "'<what you read>'",
            result.stdout,
        )
        self.assertNotIn("okf-restamp.sh 'knowledge/project/state.md' 'src/lib.rs' ", result.stdout)
        # One drifted anchor needs no sweep hint; it is for a reformat's many.
        self.assertNotIn("--format-only", result.stdout)
        self.assertIn("drifted from src/lib.rs#admit_reusable", result.stdout)

    def test_gate_labels_blame_as_the_last_commit_touching_the_file(self) -> None:
        self.stale_symbol()
        result = self.run_script("okf-check.sh")
        self.assertIn(
            "last commit touching this file (not necessarily the cause): 01234567 "
            "2026-09-16 chore: reformat, unrelated (Alessandro Viganò)",
            result.stdout,
        )
        self.assertNotIn("blame: 01234567", result.stdout)

    def test_recall_withheld_names_the_identity_and_labels_blame(self) -> None:
        self.stale_symbol()
        result = self.run_script("okf-recall.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("src/lib.rs#admit_reusable  [changed_after_baseline]", result.stdout)
        self.assertIn(
            "last commit touching this file (not necessarily the cause): 01234567 "
            "2026-09-16 chore: reformat, unrelated (Alessandro Viganò)",
            result.stdout,
        )

    def test_uncommitted_change_keeps_its_own_wording_in_both_scripts(self) -> None:
        self.stale_symbol(blame={})
        for script in ("okf-check.sh", "okf-recall.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertIn("(uncommitted change — nothing to blame yet)", result.stdout)

    def test_gate_rejects_partial_report_even_when_an_index_matched(self) -> None:
        self.payload("drift", {"docs": [{"path": "knowledge/index.md", "result": "fresh"}]})
        result = self.run_script("okf-check.sh")
        self.assert_unusable(result)
        self.assertIn("no drift verdict", result.stdout)

    def test_gate_rejects_missing_or_unknown_verdict(self) -> None:
        for result in (None, "surprise"):
            self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": result}]})
            with self.subTest(result=result):
                self.assert_unusable(self.run_script("okf-check.sh"))

    def test_recall_rejects_missing_or_unknown_verdict(self) -> None:
        for docs in ([], [{"path": "knowledge/project/state.md"}],
                     [{"path": "knowledge/project/state.md", "result": "surprise"}]):
            with self.subTest(docs=docs):
                self.payload("drift", {"docs": docs})
                self.assert_unusable(self.run_script("okf-recall.sh"))

    def test_recall_rejects_search_failure_even_with_valid_results(self) -> None:
        self.env["SEARCH_EXIT"] = "3"
        self.assert_unusable(self.run_script("okf-recall.sh"))
        (self.root / "search.json").write_text("")
        self.assert_unusable(self.run_script("okf-recall.sh"))

    def test_recall_rejects_malformed_search_and_drift(self) -> None:
        for name in ("search", "drift"):
            path = self.root / f"{name}.json"
            original = path.read_text()
            for blob in ("", "garbage", "null", "{}", "42"):
                with self.subTest(name=name, blob=blob):
                    path.write_text(blob)
                    self.assert_unusable(self.run_script("okf-recall.sh"))
            path.write_text(original)

    def test_recall_rejects_failed_drift_with_fresh_json(self) -> None:
        self.env["DRIFT_EXIT"] = "7"
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
        self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": "fresh", "padding": "x" * 300000}]})
        self.payload("search", [{"concept_id": "project/state", "description": "x" * 300000, "score": 1}])
        for script in ("okf-check.sh", "okf-recall.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(list(self.root.glob("okf-check.*")), [])
                self.assertEqual(list(self.root.glob("okf-recall.*")), [])


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="okf-bootstrap-")
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
        (bundle / "concept.md").write_text(
            "---\n"
            "type: Reference\n"
            "title: Fixture\n"
            "description: Fixture concept.\n"
            "last_updated: 2026-09-16\n"
            "code_refs:\n"
            "  - src/lib.rs\n"
            "  - scripts/build.mjs\n"
            "  - VERSION\n"
            "  - package.json\n"
            "  - .github/workflows/ci.yml\n"
            "  - README.md\n"
            "  - docs/\n"
            "---\n"
            "# Fixture\n\nA fixture concept.\n"
        )
        for relative, content in {
            "src/lib.rs": "pub fn fixture() {}\n",
            "scripts/build.mjs": "export const fixture = true;\n",
            "VERSION": "0.7.0\n",
            "package.json": "{}\n",
            ".github/workflows/ci.yml": "name: fixture\n",
            "README.md": "# Fixture\n",
            "docs/notes.md": "# Notes\n",
        }.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

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
        (self.stub / "drift").write_text(
            '#!/bin/sh\n'
            'set -eu\n'
            'case "${1:-}" in\n'
            'link)\n'
            '  shift\n'
            '  if [ -n "${DRIFT_LINK_FAIL:-}" ]; then echo "link refused by the stub" >&2; exit 1; fi\n'
            '  printf "%s\\n" "$*" >> "$DRIFT_LINK_LOG"\n'
            '  if [ ! -f "$DRIFT_LOCK" ]; then printf "version = 1\\n" > "$DRIFT_LOCK"; fi\n'
            '  {\n'
            '    printf "\\n[[bindings]]\\ndoc = \\"%s\\"\\ntarget = \\"%s\\"\\nsig = \\"fixture\\"\\n" "$1" "$2"\n'
            '  } >> "$DRIFT_LOCK"\n'
            '  ;;\n'
            'check) cat "$DRIFT_CHECK_JSON" ;;\n'
            '*) exit 2 ;;\n'
            'esac\n'
        )
        for path in (self.stub / "okf", self.stub / "drift"):
            path.chmod(0o755)

        self.validate_json = self.root / "validate.json"
        self.validate_json.write_text(json.dumps({"gate_passed": True, "is_conformant": True}))
        self.drift_check_json = self.root / "drift-check.json"
        self.drift_check_json.write_text(json.dumps({
            "docs": [{
                "path": "knowledge/concept.md",
                "result": "fresh",
                "anchors": [],
                "links": [],
            }]
        }))
        self.link_log = self.root / "drift-links.log"
        self.link_log.write_text("")
        self.env = dict(
            os.environ,
            OKF_VALIDATE_JSON=str(self.validate_json),
            DRIFT_CHECK_JSON=str(self.drift_check_json),
            DRIFT_LINK_LOG=str(self.link_log),
            DRIFT_LOCK=str(self.root / "drift.lock"),
            PATH=str(self.stub) + os.pathsep + os.environ["PATH"],
            TMPDIR=str(self.root),
            **GIT_ID,
        )
        self.env.pop("OKF_DRIFT_ROOT", None)
        self.env.pop("OKF_DRIFT_SHIM", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            self.env["XDG_CACHE_HOME"] = str(pin_scripts(self.root, (
                "okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh",
                "okf-restamp.sh", "okf-tidy.sh", "okf-log.sh")))
        subprocess.run(["git", "add", "."], cwd=self.root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
            command = ["sh", str(SCRIPTS / "okf-shim.sh"), "--repo-root", str(self.root), script]
        else:
            command = [str(SCRIPTS / script)]
        return subprocess.run(command + list(args), cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def test_bootstrap_binds_code_only_and_gate_accepts_unbound_paths(self) -> None:
        """The gate half runs against a stub `drift check` that answers `fresh`: it proves
        okf-check.sh never cross-checks code_refs against drift.lock, not that real drift
        reports an unbound doc as fresh (measured in okf-quirks.md, and by hand)."""
        result = self.run_script("okf-drift-bootstrap.sh", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.link_log.read_text().splitlines(),
            ["knowledge/concept.md src/lib.rs", "knowledge/concept.md scripts/build.mjs"],
        )
        lock = (self.root / "drift.lock").read_text()
        self.assertNotIn('target = "VERSION"', lock)
        self.assertIn("not-code knowledge/concept.md -> VERSION", result.stdout)
        self.assertIn("skip  knowledge/concept.md -> docs/", result.stdout)
        self.assertNotIn("FAIL  knowledge/concept.md -> docs/", result.stdout)
        self.assertIn("5 not-code", result.stdout)

        gate = self.run_script("okf-check.sh", "knowledge")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("ok    knowledge:", gate.stdout)

        lock_path = self.root / "drift.lock"
        lock_path.write_text(
            lock_path.read_text()
            + '\n[[bindings]]\n'
            'doc = "knowledge/concept.md"\n'
            'target = "VERSION"\n'
            'sig = "fixture"\n'
        )
        held = self.run_script("okf-drift-bootstrap.sh", "knowledge")
        self.assertEqual(held.returncode, 0, held.stdout + held.stderr)
        # A hand binding on a non-code path is a deliberate content anchor: the bootstrap
        # reports it and keeps it, and no longer prints an unlink command beside it.
        self.assertIn("held-non-code knowledge/concept.md -> VERSION (deliberate content anchor — kept)",
                      held.stdout)
        self.assertNotIn("drift unlink", held.stdout)

    def test_bootstrap_treats_symbol_binding_as_covering_file(self) -> None:
        (self.root / "drift.lock").write_text(
            'version = 1\n\n[[bindings]]\n'
            'doc = "knowledge/concept.md"\n'
            'target = "src/lib.rs#fixture"\n'
            'sig = "fixture"\n'
        )
        result = self.run_script("okf-drift-bootstrap.sh", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("knowledge/concept.md src/lib.rs", self.link_log.read_text())
        self.assertIn(
            "skip  knowledge/concept.md -> src/lib.rs "
            "(symbol binding(s) present in drift.lock)",
            result.stdout,
        )

    def test_bootstrap_rejects_symbol_code_ref(self) -> None:
        concept = self.root / "knowledge/concept.md"
        concept.write_text(concept.read_text().replace("  - src/lib.rs\n", "  - src/lib.rs#fixture\n"))
        result = self.run_script("okf-drift-bootstrap.sh", "knowledge")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "FAIL  knowledge/concept.md -> src/lib.rs#fixture "
            "(#Symbol belongs in drift.lock via drift link, not in code_refs — list the file here)",
            result.stdout,
        )
        self.assertNotIn("knowledge/concept.md src/lib.rs#fixture", self.link_log.read_text())


    def test_bootstrap_leaves_shell_scripts_unbound(self) -> None:
        concept = self.root / "knowledge/concept.md"
        concept.write_text(concept.read_text().replace("  - VERSION\n", "  - VERSION\n  - scripts/build.sh\n"))
        (self.root / "scripts/build.sh").write_text("#!/bin/sh\necho build\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        result = self.run_script("okf-drift-bootstrap.sh", "knowledge")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("scripts/build.sh", self.link_log.read_text())
        self.assertIn("not-code knowledge/concept.md -> scripts/build.sh (high-churn script: "
                      "hand-link only if the concept describes its logic)", result.stdout)

    HISTORY = "# Log\n\n## 2026-01-01\n* older entry\n"
    STILL = ("* STILL ACCURATE, re-stamped `concept.md` <- `src/lib.rs#fixture` (last commit on the file: "
             '01234567 "tighten it"): ')

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, env=self.env, check=True, capture_output=True)

    def stale_anchor(self, branch: str = "alice/restamp") -> None:
        """A stale symbol anchor, committed on `main` (= origin/HEAD), on a work branch."""
        self.drift_check_json.write_text(json.dumps({"docs": [{
            "path": "knowledge/concept.md", "result": "stale", "links": [],
            "anchors": [{"identity": "src/lib.rs#fixture", "path": "src/lib.rs", "result": "stale",
                         "reason": {"code": "changed_after_baseline", "message": "m"},
                         "blame": {"commit": "0123456789abcdef", "subject": "tighten it"}}],
        }]}))
        (self.root / "knowledge/log.md").write_text(self.HISTORY)
        split_log(self.root)
        self.frozen = (self.root / "knowledge/log.md").read_text()
        (self.root / "drift.lock").write_text('version = 1\n\n[[bindings]]\ndoc = "knowledge/concept.md"\n'
                                              'target = "src/lib.rs#fixture"\nsig = "fixture"\n')
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.git("branch", "-M", "main")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.git("checkout", "-qb", branch)

    def entries(self) -> dict[str, str]:
        return {str(p.relative_to(self.root)): p.read_text()
                for p in sorted((self.root / "knowledge").glob("log/*/log.md"))}

    def restamp(self, note: str, *opts: str) -> subprocess.CompletedProcess[str]:
        return self.run_script("okf-restamp.sh", *opts, "knowledge/concept.md", "src/lib.rs#fixture", note)

    def assert_nothing_logged(self) -> None:
        self.assertEqual(self.entries(), {})
        self.assertEqual((self.root / "knowledge/log.md").read_text(), self.frozen)

    def test_restamp_refuses_an_unmigrated_bundle_and_names_okf_migrate(self) -> None:
        self.stale_anchor()
        (self.root / "knowledge/log.md").write_text(self.HISTORY)
        self.frozen = self.HISTORY
        result = self.restamp("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("/okf-migrate", result.stderr)
        self.assert_nothing_logged()
        self.assertFalse(self.link_log.exists() and self.link_log.read_text().strip())
        sweep = self.run_script("okf-restamp.sh", "--format-only")
        self.assertEqual(sweep.returncode, 1, sweep.stdout + sweep.stderr)
        self.assertIn("/okf-migrate", sweep.stderr)
        self.assert_nothing_logged()

    def test_restamp_refuses_an_empty_note_and_an_unknown_binding(self) -> None:
        self.stale_anchor()
        short = self.run_script("okf-restamp.sh", "knowledge/concept.md", "src/lib.rs#fixture", "ok")
        self.assertEqual(short.returncode, 1, short.stdout + short.stderr)
        self.assertIn("say what you read", short.stderr)
        unknown = self.run_script("okf-restamp.sh", "knowledge/concept.md", "src/lib.rs",
                                  "read the whole file against the concept")
        self.assertEqual(unknown.returncode, 1, unknown.stdout + unknown.stderr)
        self.assertIn("path#symbol for a symbol anchor", unknown.stderr)
        self.assertEqual(self.link_log.read_text(), "")
        self.assert_nothing_logged()

    def test_restamp_links_and_writes_its_line_into_the_branch_entry(self) -> None:
        self.stale_anchor()
        result = self.restamp("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.link_log.read_text().splitlines(),
                         ["knowledge/concept.md src/lib.rs#fixture --doc-is-still-accurate"])
        [(entry, text)] = self.entries().items()
        self.assertEqual(re.fullmatch(ENTRY_RE, entry).groups()[:2], (TODAY, "restamp"))
        self.assertEqual(text, f"## {TODAY}\n{self.STILL}read fixture(): the guard the concept names is unchanged\n")
        self.assertIn(entry, result.stdout)
        self.assertEqual((self.root / "knowledge/log.md").read_text(), self.frozen)
        again = self.restamp("read fixture() a second time: still the same guard")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.entries(), {entry: f"## {TODAY}\n{self.STILL}read fixture() a second time: "
                                                 f"still the same guard\n{self.STILL}read fixture(): the guard "
                                                 "the concept names is unchanged\n"})
        self.assertEqual((self.root / "knowledge/log.md").read_text(), self.frozen)

    def test_restamp_of_a_fresh_anchor_changes_nothing(self) -> None:
        # Value: protects=no link and no log line for a fresh anchor; fails_when=the fresh branch falls through to drift link; why_new=only stale anchors were tested; seam=none
        self.stale_anchor()
        data = json.loads(self.drift_check_json.read_text())
        data["docs"][0]["result"] = "fresh"
        data["docs"][0]["anchors"][0]["result"] = "fresh"
        self.drift_check_json.write_text(json.dumps(data))
        result = self.restamp("read fixture(): nothing moved at all")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is fresh; nothing to re-stamp, nothing logged", result.stdout)
        self.assertEqual(self.link_log.read_text(), "")
        self.assert_nothing_logged()

    def test_restamp_passes_entry_and_slug_through(self) -> None:
        self.stale_anchor()
        chosen = self.root / "knowledge/log/2026-01-02-other-abcd/log.md"
        chosen.parent.mkdir(parents=True)
        chosen.write_text("## 2026-01-02\n* x\n")
        result = self.restamp("read fixture(): the guard still holds",
                              "--entry", str(chosen.relative_to(self.root)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(chosen.read_text(), f"## {TODAY}\n{self.STILL}read fixture(): the guard still holds\n\n"
                                             "## 2026-01-02\n* x\n")
        self.assertEqual(list(self.entries()), ["knowledge/log/2026-01-02-other-abcd/log.md"])
        self.git("checkout", "-q", "--detach")
        slugged = self.restamp("read fixture(): the guard holds on a detached head", "--slug", "hotfix")
        self.assertEqual(slugged.returncode, 0, slugged.stdout + slugged.stderr)
        [new] = [e for e in self.entries() if "-other-" not in e]
        self.assertEqual(re.fullmatch(ENTRY_RE, new).group(2), "hotfix")

    def test_restamp_on_a_detached_head_without_slug_refuses_and_writes_nothing(self) -> None:
        self.stale_anchor()
        self.git("checkout", "-q", "--detach")
        result = self.restamp("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("detached", result.stderr)
        self.assertIn("--slug", result.stderr)
        self.assertEqual(self.link_log.read_text(), "")
        self.assert_nothing_logged()

    def test_a_failed_link_restores_the_entry_or_removes_the_new_folder(self) -> None:
        self.stale_anchor()
        self.env["DRIFT_LINK_FAIL"] = "1"
        first = self.restamp("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        self.assertIn("drift link failed", first.stderr)
        self.assertEqual([p.name for p in (self.root / "knowledge").glob("log/*")], [])
        self.assert_nothing_logged()
        del self.env["DRIFT_LINK_FAIL"]
        ok = self.restamp("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        before = {p: (self.root / p).read_bytes() for p in self.entries()}
        self.assertEqual(len(before), 1)
        self.env["DRIFT_LINK_FAIL"] = "1"
        failed = self.restamp("read fixture() again: still unchanged, but the link fails")
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertEqual({p: (self.root / p).read_bytes() for p in self.entries()}, before)

    def test_restamp_through_the_launcher_fetches_and_verifies_okf_log(self) -> None:
        """An empty cache: the pinned launcher fetches okf-restamp.sh and, for its log
        line, okf-log.sh, each checked against the pin; a damaged cached okf-log.sh fails."""
        self.stale_anchor()
        cache = Path(self.tmp.name) / "empty-cache"
        pin_root = Path(tempfile.mkdtemp(prefix="pin-", dir=self.tmp.name))
        pin_scripts(pin_root, ("okf-restamp.sh", "okf-log.sh"), fill_cache=False)
        shutil.copy(pin_root / ".okf-drift-version", self.root / ".okf-drift-version")
        (self.stub / "curl").write_text(
            '#!/bin/sh\n'
            'out=; url=\n'
            'while [ "$#" -gt 0 ]; do case "$1" in -o) out=$2; shift 2;; -*) shift;; *) url=$1; shift;; esac; done\n'
            f'cp "{SCRIPTS}/$(basename "$url")" "$out"\n'
        )
        (self.stub / "curl").chmod(0o755)
        env = dict(self.env, XDG_CACHE_HOME=str(cache))
        shim = ["sh", str(SCRIPTS / "okf-shim.sh"), "--repo-root", str(self.root), "okf-restamp.sh",
                "knowledge/concept.md", "src/lib.rs#fixture"]

        def run(note: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(shim + [note], cwd=self.root, env=env, text=True, capture_output=True)

        result = run("read fixture(): the guard the concept names is unchanged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cached = cache / "okf-drift/v0.7.0/okf-log.sh"
        self.assertEqual(cached.read_bytes(), (SCRIPTS / "okf-log.sh").read_bytes())
        [(entry, before)] = self.entries().items()
        cached.write_bytes(cached.read_bytes() + b"# damaged\n")
        damaged = run("read fixture() again: the cached writer is damaged")
        self.assertNotEqual(damaged.returncode, 0, damaged.stdout + damaged.stderr)
        self.assertIn("is damaged", damaged.stderr)
        self.assertEqual(self.entries(), {entry: before})
        self.assertEqual(len(self.link_log.read_text().splitlines()), 1)

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
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* one\n")
        self.assertIn("origin/HEAD", out)
        self.assertIn(entry, out)
        self.assertEqual((self.bundle / "log.md").read_text(), self.history)

    def test_a_second_write_reuses_the_untracked_entry_newest_first(self) -> None:
        self.add("* one")
        self.add("* two")
        [entry] = self.entries()
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* two\n* one\n")

    def test_a_staged_entry_is_reused(self) -> None:
        self.add("* one")
        self.git("add", ".")
        self.add("* two")
        [entry] = self.entries()
        self.assertEqual((self.root / entry).read_text(), f"## {TODAY}\n* two\n* one\n")

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
        self.assertEqual((self.root / mine[0]).read_text(), f"## {TODAY}\n* mine\n")

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


class FormatOnlyTests(unittest.TestCase):
    """The sweep's verdict, through `okf-restamp.sh --compare`: no repository, no drift.
    Every MUST_DIFFER pair changes meaning while looking like formatting, and an earlier
    draft that normalised whitespace, trailing commas and import order re-stamped each one
    without anyone reading it (an independent review built them against real drift)."""

    MUST_DIFFER = [
        ('c1', 'x.c', 'int f(int x, int y) {\n  return x-- - y;\n}\n', 'int f(int x, int y) {\n  return x - --y;\n}\n'),
        ('c2', 'x.c', 'void h(void) {\n  // TODO\n  free(p);\n}\n', 'void h(void) {\n  // TODO free(p);\n}\n'),
        ('c3', 'x.c', 'const char *s = "a,)";\n', 'const char *s = "a)";\n'),
        ('c4', 'x.c', '#define FOO 1\n#include "cfg.h"\n', '#include "cfg.h"\n#define FOO 1\n'),
        ('c5', 'x.c', '#ifdef _WIN32\n#include <windows.h>\n#endif\n', '#include <windows.h>\n#ifdef _WIN32\n#endif\n'),
        ('c6', 'x.c', '#define F(x) (x)\n', '#define F (x) (x)\n'),
        ('c7', 'x.c', '#define A 1\nint b = A;\n', '#define A 1 int b = A;\n'),
        ('j1', 'x.js', 'function f(a, b) {\n  return a + ++b;\n}\n', 'function f(a, b) {\n  return a++ + b;\n}\n'),
        ('j2', 'x.js', 'function f(x) {\n  return x;\n}\n', 'function f(x) {\n  return\n  x;\n}\n'),
        ('j3', 'x.js', 'const a = [1,];\n', 'const a = [1];\n'),
        ('j4', 'x.js', 'const a = [,];\n', 'const a = [];\n'),
        ('j5', 'x.js', 'let s = `a ${b}  c`;\n', 'let s = `a ${b} c`;\n'),
        ('j6', 'x.js', 'let s = `${ "`" }  c`;\n', 'let s = `${ "`" } c`;\n'),
        ('p1', 'x.py', 'def f(x):\n    return (x,)\n', 'def f(x):\n    return (x)\n'),
        ('p2', 'x.py', 'from a import x\nfrom b import x\n\ndef f():\n    return x\n', 'from b import x\nfrom a import x\n\ndef f():\n    return x\n'),
        ('p3', 'x.py', 'import os\nos = 3\n', 'os = 3\nimport os\n'),
        ('p4', 'x.py', 'def f(a, b):\n    return g(a,  # c\n             b,\n    )\n', 'def f(a, b):\n    return g(a,  # c b,\n    )\n'),
        ('r1', 'x.rs', 'fn g(s: &\'static str) { h("it\'s  here") }\n', 'fn g(s: &\'static str) { h("it\'s here") }\n'),
        ('r2', 'x.rs', 'use x::{p::{a, b, c}, d};\nfn f() {}\n', 'use x::{p::{a, c}, b, d};\nfn f() {}\n'),
        ('r3', 'x.rs', 'fn f(x: u32) -> (u32,) {\n    (x,)\n}\n', 'fn f(x: u32) -> (u32,) {\n    (x)\n}\n'),
        ('r4', 'x.rs', 'fn f() -> &\'static str {\n    r#"a " b  c"#\n}\n', 'fn f() -> &\'static str {\n    r#"a " b c"#\n}\n'),
        ('t1', 'x.ts', 'import Foo = Bar.Baz\nexport const r = sub(a, b)\nexport const s = "x"\n', 'import Foo = Bar.Baz\nexport const r = sub(b, a)\nexport const s = "x"\n'),
        ('t2', 'x.js', 'import.meta.hot\nexport const r = sub(a, b)\nexport const s = "x"\n', 'import.meta.hot\nexport const r = sub(b, a)\nexport const s = "x"\n'),
        ("c-intra-line", "x.c", "int f() {\n\treturn 1;\n}\n", "int f()   {\n\treturn 1;\n}\n"),
        ("c-continuation", "x.c", "#define S \"a\\\n  b\"\n", "#define S \"a\\\n    b\"\n"),
        ("swift-multiline-string", "x.swift", 'let s = """\n  a\n  """\n', 'let s = """\n    a\n  """\n'),
        ("cpp-raw-string", "x.cpp", 'auto s = R"(\n  a\n)";\n', 'auto s = R"(\n    a\n)";\n'),
        ("shell-indentation", "x.sh", "if true; then\n  echo a\nfi\n", "if true; then\n    echo a\nfi\n"),
        ("yaml-indentation", "x.yml", "a:\n  b: 1\n", "a:\nb: 1\n"),
        ("rust-reindent-is-not-ours", "x.rs", "fn f() {\n  g();\n}\n", "fn f() {\n    g();\n}\n"),
        ("csharp-interpolated-verbatim", "x.cs", 'var s = @$"a\n  {b}\n";\n', 'var s = @$"a\n    {b}\n";\n'),
        ("csharp-verbatim-interpolated", "x.cs", 'var s = $@"a\n  {b}\n";\n', 'var s = $@"a\n    {b}\n";\n'),
        ("scala-braceless-indentation", "x.scala", "def f =\n  g()\n  h()\n", "def f =\n  g()\nh()\n"),
        ("blank-line-before-block", "x.swift", "foo(x)\n{ y }\n", "foo(x)\n\n{ y }\n"),
        ("c-blank-line-added", "x.c", "int a;\nint b;\n", "int a;\n\nint b;\n"),
    ]
    MAY_SETTLE = [
        ("c-reindent", "x.c", "int f() {\n\treturn 1;\n}\n", "int f() {\n    return 1;\n}\n"),
        ("c-trailing-whitespace", "src/a.h", "int a;\n\nint b;\n", "int a;   \n\t\nint b;\t\n"),
        ("swift-reindent", "x.swift", "func f() {\n  g()\n}\n", "func f() {\n    g()\n}\n"),
    ]

    def compare(self, path: str, old: str, new: str) -> str:
        with tempfile.TemporaryDirectory(prefix="okf-compare-") as tmp:
            a, b = Path(tmp) / "old", Path(tmp) / "new"
            a.write_text(old)
            b.write_text(new)
            result = subprocess.run(["sh", str(SCRIPTS / "okf-restamp.sh"), "--compare", path, str(a), str(b)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

    def test_meaning_changes_are_never_settled(self) -> None:
        for name, path, old, new in self.MUST_DIFFER:
            with self.subTest(name=name):
                self.assertEqual(self.compare(path, old, new), "differs")

    def test_layout_changes_in_raw_hashed_languages_are_settled(self) -> None:
        for name, path, old, new in self.MAY_SETTLE:
            with self.subTest(name=name):
                self.assertEqual(self.compare(path, old, new),
                                 "format-only: indentation or trailing whitespace")


# Kept beside the one class that uses them, so the import block above stays untouched.
import re  # noqa: E402
import sys  # noqa: E402


@unittest.skipUnless(os.environ.get("OKF_SELFTEST_REAL_DRIFT") == "1",
                     "real-drift tests; set OKF_SELFTEST_REAL_DRIFT=1")
class LockMergeTests(unittest.TestCase):
    """okf-lock-merge.py against the REAL drift, each case a real conflicted `git merge main`.

    The oracle for "serialized as drift does" is drift itself: drift rewrites the whole
    lock on any link, so re-linking a fresh binding must leave the merged bytes unchanged.
    """

    def setUp(self) -> None:
        if shutil.which("drift") is None:
            self.fail("OKF_SELFTEST_REAL_DRIFT=1 but drift is not on PATH; install the pinned drift")
        self.tmp = tempfile.TemporaryDirectory(prefix="okf-lockmerge-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t", TMPDIR=str(self.root),
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "-q", "-b", "main")
        self.write("src/a.rs", "".join(f"fn a{i}() {{ {i} }}\n" for i in range(12)))
        self.write("src/b.rs", "fn b() {}\n")
        self.write("src/c.rs", "fn c() {}\n")
        self.write("src/m.rs", "fn m() {}\n")
        self.write("src/n.rs", "fn n() {}\n")
        for doc in ("docs/a.md", "docs/c.md", "docs/m.md", "docs/z.md"):
            self.write(doc, f"# {doc}\n")
        self.drift("link", "docs/a.md", "src/a.rs")
        self.drift("link", "docs/c.md", "src/c.rs")
        self.drift("link", "docs/z.md", "src/b.rs")
        self.commit("base")
        self.git("checkout", "-q", "-b", "feature")

    # --- fixture plumbing -------------------------------------------------------------
    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, text=True,
                              capture_output=True, check=check)

    def drift(self, *args: str) -> None:
        result = subprocess.run(["drift", *args], cwd=self.root, env=self.env, text=True,
                                capture_output=True)
        self.assertEqual(result.returncode, 0, f"drift {args}: {result.stdout}{result.stderr}")

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def lock(self) -> str:
        return (self.root / "drift.lock").read_text()

    def on_main(self) -> None:
        self.git("checkout", "-q", "main")

    def on_feature(self) -> None:
        self.git("checkout", "-q", "feature")

    def unmerged(self) -> str:
        return self.git("diff", "--name-only", "--diff-filter=U").stdout

    def merge_main(self) -> None:
        """From the branch, `git merge main`; the lock must come out conflicted."""
        self.on_feature()
        merged = self.git("merge", "-q", "--no-edit", "main", check=False)
        self.assertNotEqual(merged.returncode, 0, "the fixture did not conflict")
        self.assertIn("drift.lock", self.unmerged())

    def resolve(self, path: str | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(self.env)
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(SCRIPTS / "okf-lock-merge.py")], cwd=self.root,
                              env=env, text=True, capture_output=True)

    def blocks(self) -> dict[tuple[str, str], str]:
        found = {}
        for block in self.lock().split("\n\n")[1:]:
            doc = re.search(r'^doc = "(.*)"$', block, re.M).group(1)
            target = re.search(r'^target = "(.*)"$', block, re.M).group(1)
            found[(doc, target)] = block
        return found

    def assert_resolved(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("drift.lock", self.unmerged())
        self.assertNotIn("<<<<<<<", self.lock())

    def assert_drift_serialization(self, doc: str, target: str) -> None:
        before = self.lock()
        self.drift("link", doc, target, "--doc-is-still-accurate")
        self.assertEqual(self.lock(), before)

    def check(self) -> dict[str, str]:
        out = subprocess.run(["drift", "check", "--format", "json"], cwd=self.root, env=self.env,
                             text=True, capture_output=True)
        return {doc["path"]: doc["result"] for doc in json.loads(out.stdout)["docs"]}

    # --- scenarios --------------------------------------------------------------------
    def test_two_docs_added_at_the_same_sorted_position(self) -> None:
        self.on_main()
        self.drift("link", "docs/m.md", "src/m.rs")
        self.write("NOTES", "main\n")
        self.commit("main binds m")
        self.on_feature()
        self.write("docs/n.md", "# n\n")
        self.drift("link", "docs/n.md", "src/n.rs")
        self.write("NOTES", "feature\n")
        self.commit("feature binds n")
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(set(self.blocks()), {
            ("docs/a.md", "src/a.rs"), ("docs/c.md", "src/c.rs"), ("docs/m.md", "src/m.rs"),
            ("docs/n.md", "src/n.rs"), ("docs/z.md", "src/b.rs")})
        self.assertRegex(result.stdout, r"added\s+docs/n\.md -> src/n\.rs")
        self.assertRegex(result.stdout, r"still unmerged:\n\s+NOTES\n")
        self.assertIn("run the gate", result.stdout)
        self.assertEqual(self.unmerged(), "NOTES\n")
        self.assertEqual(set(self.check().values()), {"fresh"})
        self.assert_drift_serialization("docs/n.md", "src/n.rs")

    def edit_a(self, line: int) -> None:
        text = (self.root / "src/a.rs").read_text().splitlines(keepends=True)
        text[line] = f"fn a{line}() {{ {line} + 1 }}\n"
        self.write("src/a.rs", "".join(text))

    def restamp(self, doc: str, target: str) -> None:
        self.drift("link", doc, target, "--doc-is-still-accurate")

    MAIN_TAIL = ("docs/zm.md", "src/m.rs")
    BRANCH_TAIL = ("docs/zn.md", "src/n.rs")

    def main_appends(self, *, edit_a: bool = False, restamp_a: bool = False) -> None:
        """On main: bind a doc that sorts last, and optionally change src/a.rs on its last
        line (far from the branch's edit on line 0, so src/a.rs merges cleanly)."""
        self.on_main()
        self.write(self.MAIN_TAIL[0], "# zm\n")
        self.drift("link", *self.MAIN_TAIL)
        if edit_a:
            self.edit_a(11)
        if restamp_a:
            self.restamp("docs/a.md", "src/a.rs")
        self.commit("main")
        self.on_feature()

    def branch_appends(self) -> None:
        """On the branch: bind another doc that sorts last. Two appends at the end of the
        lock always conflict, far from the block the scenario changes, so git's alignment
        of that change cannot dissolve the conflict."""
        self.write(self.BRANCH_TAIL[0], "# zn\n")
        self.drift("link", *self.BRANCH_TAIL)

    def test_the_branch_removes_a_binding(self) -> None:
        self.main_appends()
        self.drift("unlink", "docs/c.md", "src/c.rs")
        self.branch_appends()
        self.commit("feature unbinds c")
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(set(self.blocks()), {
            ("docs/a.md", "src/a.rs"), ("docs/z.md", "src/b.rs"), self.MAIN_TAIL, self.BRANCH_TAIL})
        self.assertRegex(result.stdout, r"removed\s+docs/c\.md -> src/c\.rs")
        self.assert_drift_serialization(*self.MAIN_TAIL)

    def test_a_restamp_whose_target_main_left_alone_comes_out_fresh(self) -> None:
        self.main_appends()
        self.write("src/c.rs", "fn c() { 1 }\n")
        self.restamp("docs/c.md", "src/c.rs")
        self.branch_appends()
        self.commit("feature re-stamps c")
        branch_block = self.blocks()[("docs/c.md", "src/c.rs")]
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(self.blocks()[("docs/c.md", "src/c.rs")], branch_block)
        self.assertRegex(result.stdout, r"modified\s+docs/c\.md -> src/c\.rs")
        self.assertIn("no stale binding", result.stdout)
        self.assertEqual(set(self.check().values()), {"fresh"})

    def test_a_restamp_whose_target_main_changed_comes_out_stale(self) -> None:
        self.main_appends(edit_a=True)
        self.edit_a(0)
        self.restamp("docs/a.md", "src/a.rs")
        self.branch_appends()
        self.commit("feature re-stamps a")
        branch_block = self.blocks()[("docs/a.md", "src/a.rs")]
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(self.blocks()[("docs/a.md", "src/a.rs")], branch_block)
        self.assertRegex(result.stdout, r"stale\s+docs/a\.md -> src/a\.rs")
        self.assertEqual(self.check()["docs/a.md"], "stale")

    def test_both_sides_resign_the_same_binding(self) -> None:
        self.main_appends(edit_a=True, restamp_a=True)
        self.edit_a(0)
        self.restamp("docs/a.md", "src/a.rs")
        self.commit("feature re-stamps a")
        branch_block = self.blocks()[("docs/a.md", "src/a.rs")]
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(self.blocks()[("docs/a.md", "src/a.rs")], branch_block)
        self.assertIn(self.MAIN_TAIL, self.blocks())
        self.assertRegex(result.stdout, r"modified\s+docs/a\.md -> src/a\.rs")
        self.assertEqual(self.check()["docs/a.md"], "stale")

    def test_removed_on_the_branch_and_changed_on_main_is_dropped(self) -> None:
        self.main_appends(edit_a=True, restamp_a=True)
        self.drift("unlink", "docs/a.md", "src/a.rs")
        self.commit("feature unbinds a")
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertNotIn(("docs/a.md", "src/a.rs"), self.blocks())
        self.assertIn(self.MAIN_TAIL, self.blocks())
        self.assertIn("docs/a.md -> src/a.rs: removed on branch, changed on main: dropped",
                      result.stdout)

    def test_removed_on_main_and_changed_on_the_branch_is_dropped(self) -> None:
        self.on_main()
        self.drift("unlink", "docs/a.md", "src/a.rs")
        self.commit("main unbinds a")
        self.on_feature()
        self.edit_a(0)
        self.restamp("docs/a.md", "src/a.rs")
        self.commit("feature re-stamps a")
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(set(self.blocks()), {("docs/c.md", "src/c.rs"), ("docs/z.md", "src/b.rs")})
        self.assertIn("docs/a.md -> src/a.rs: removed on main, changed on branch: dropped",
                      result.stdout)

    def test_a_change_to_metadata_only(self) -> None:
        self.main_appends()
        self.branch_appends()
        lock = self.lock().replace('doc = "docs/c.md"\ntarget = "src/c.rs"\n',
                                   'doc = "docs/c.md"\ntarget = "src/c.rs"\nnote = "kept"\n')
        self.write("drift.lock", lock)
        self.commit("feature annotates c")
        branch_block = self.blocks()[("docs/c.md", "src/c.rs")]
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertEqual(self.blocks()[("docs/c.md", "src/c.rs")], branch_block)
        self.assertIn('note = "kept"', branch_block)
        self.assertRegex(result.stdout, r"modified\s+docs/c\.md -> src/c\.rs")
        self.assert_drift_serialization("docs/c.md", "src/c.rs")

    def test_a_lock_written_by_drift_round_trips_byte_identical(self) -> None:
        self.main_appends()
        self.branch_appends()
        self.write("docs/x y.md", "# x y\n")
        for target in ("src/a.rs", "src/b.rs", "src/c.rs"):
            self.drift("link", "docs/x y.md", target)
        self.drift("link", "docs/c.md", "src/b.rs")
        self.commit("feature binds x y")
        self.merge_main()
        result = self.resolve()
        self.assert_resolved(result)
        self.assertIn(("docs/x y.md", "src/b.rs"), self.blocks())
        self.assertEqual(len(self.blocks()), 9)
        self.assert_drift_serialization("docs/x y.md", "src/b.rs")
        self.assert_drift_serialization("docs/c.md", "src/b.rs")

    # --- refusals: nothing written, nothing staged ------------------------------------
    def assert_refused(self, result: subprocess.CompletedProcess[str], reason: str,
                       before: bytes, unmerged: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(reason, result.stderr)
        self.assertEqual((self.root / "drift.lock").read_bytes(), before)
        self.assertEqual(self.unmerged(), unmerged)

    def conflicted(self, edit_branch_lock=None) -> tuple[bytes, str]:
        self.main_appends()
        self.branch_appends()
        if edit_branch_lock is not None:
            self.write("drift.lock", edit_branch_lock(self.lock()))
        self.commit("feature")
        self.merge_main()
        return (self.root / "drift.lock").read_bytes(), self.unmerged()

    def test_refuses_outside_a_merge(self) -> None:
        before = (self.root / "drift.lock").read_bytes()
        self.assert_refused(self.resolve(), "no merge in progress", before, "")

    def test_refuses_a_merge_whose_lock_has_no_conflict(self) -> None:
        self.on_main()
        self.write("src/b.rs", "fn b() { 1 }\n")
        self.commit("main changes b")
        self.on_feature()
        self.write("src/b.rs", "fn b() { 2 }\n")
        self.commit("feature changes b")
        self.git("merge", "-q", "--no-edit", "main", check=False)
        self.assertEqual(self.unmerged(), "src/b.rs\n")
        before = (self.root / "drift.lock").read_bytes()
        self.assert_refused(self.resolve(), "drift.lock has no conflict", before, "src/b.rs\n")

    def test_refuses_a_lock_that_is_not_version_1(self) -> None:
        before, unmerged = self.conflicted(lambda lock: lock.replace("version = 1\n", "version = 2\n", 1))
        self.assert_refused(self.resolve(), "`version = 2`", before, unmerged)

    def test_refuses_a_duplicate_binding(self) -> None:
        def duplicate(lock: str) -> str:
            return lock + "\n" + self.blocks()[("docs/a.md", "src/a.rs")].rstrip("\n") + "\n"
        before, unmerged = self.conflicted(duplicate)
        self.assert_refused(self.resolve(), "binds docs/a.md -> src/a.rs twice", before, unmerged)

    def test_refuses_when_a_side_deleted_the_lock(self) -> None:
        self.main_appends()
        self.git("rm", "-q", "drift.lock")
        self.commit("feature deletes the lock")
        merged = self.git("merge", "-q", "--no-edit", "main", check=False)
        self.assertNotEqual(merged.returncode, 0)
        self.assertEqual(self.unmerged(), "drift.lock\n")
        before = (self.root / "drift.lock").read_bytes()
        self.assert_refused(self.resolve(), "drift.lock was deleted on branch", before, "drift.lock\n")

    def test_refuses_when_drift_is_missing(self) -> None:
        before, unmerged = self.conflicted()
        only_git = self.root / "only-git"
        only_git.mkdir()
        (only_git / "git").symlink_to(shutil.which("git"))
        self.assert_refused(self.resolve(path=str(only_git)), "drift is not on PATH", before, unmerged)

    def test_a_drift_crash_or_unreadable_json_restores_the_lock(self) -> None:
        before, unmerged = self.conflicted()
        self.assertIn(b"<<<<<<<", before)
        for name, behaviour in (("crash", "kill -SEGV $$"),
                                ("unreadable", "echo 'not json'; exit 1"),
                                ("other schema", "echo '{\"docs\": []}'")):
            with self.subTest(name=name):
                fake = self.root / f"fake-{name.replace(' ', '-')}"
                fake.mkdir()
                (fake / "drift").write_text(
                    '#!/bin/sh\n[ "$1" = "--version" ] && { echo "drift v0.10.1"; exit 0; }\n'
                    f"{behaviour}\n")
                (fake / "drift").chmod(0o755)
                result = self.resolve(path=str(fake) + os.pathsep + self.env["PATH"])
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("drift.lock restored", result.stderr)
                self.assertEqual((self.root / "drift.lock").read_bytes(), before)
                self.assertEqual(self.unmerged(), unmerged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
