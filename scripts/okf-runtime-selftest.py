#!/usr/bin/env python3
"""Offline regressions for gate/recall process boundaries, paths and JSON transport.

Run with python3 scripts/okf-runtime-selftest.py. Fixtures replace only okf/drift;
real shell and Perl execute the scripts under test. No network or shared cache.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent


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
            "okf": '#!/bin/sh\ncase "$1" in\nversion) echo "okf v0.3.0";;\nvalidate) cat "$FIXTURE/validate.json"; exit "${VALIDATE_EXIT:-0}";;\nsearch) cat "$FIXTURE/search.json"; exit "${SEARCH_EXIT:-0}";;\nesac\n',
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
            "      - name: okf v0.3.0 and drift, pinned\n"
            "        run: |\n"
            "          go install github.com/okf-memory/okf-agent-memory/cmd/okf@v0.3.0\n"
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
            'version) echo "okf v0.3.0" ;;\n'
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
        )
        self.env.pop("OKF_DRIFT_ROOT", None)
        if os.environ.get("OKF_SELFTEST_PINNED") == "1":
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

    def stale_anchor(self) -> None:
        self.drift_check_json.write_text(json.dumps({"docs": [{
            "path": "knowledge/concept.md", "result": "stale", "links": [],
            "anchors": [{"identity": "src/lib.rs#fixture", "path": "src/lib.rs", "result": "stale",
                         "reason": {"code": "changed_after_baseline", "message": "m"},
                         "blame": {"commit": "0123456789abcdef", "subject": "tighten it"}}],
        }]}))
        (self.root / "knowledge/log.md").write_text("# Log\n\n## 2026-01-01\n* older entry\n")
        (self.root / "drift.lock").write_text('version = 1\n\n[[bindings]]\ndoc = "knowledge/concept.md"\n'
                                              'target = "src/lib.rs#fixture"\nsig = "fixture"\n')

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
        self.assertNotIn("re-stamped", (self.root / "knowledge/log.md").read_text())

    def test_restamp_links_and_writes_one_line_under_today(self) -> None:
        self.stale_anchor()
        result = self.run_script("okf-restamp.sh", "knowledge/concept.md", "src/lib.rs#fixture",
                                 "read fixture(): the guard the concept names is unchanged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.link_log.read_text().splitlines(),
                         ["knowledge/concept.md src/lib.rs#fixture --doc-is-still-accurate"])
        log = (self.root / "knowledge/log.md").read_text()
        today = subprocess.run(["date", "+%F"], text=True, capture_output=True).stdout.strip()
        self.assertTrue(log.startswith(f"# Log\n\n## {today}\n* STILL ACCURATE, re-stamped "
                                       "`concept.md` <- `src/lib.rs#fixture` (last commit on the file: "
                                       '01234567 "tighten it"): read fixture(): the guard'), log)
        self.assertIn("\n\n## 2026-01-01\n* older entry\n", log)

    def test_restamp_of_a_fresh_anchor_changes_nothing(self) -> None:
        # Value: protects=no link and no log line for a fresh anchor; fails_when=the fresh branch falls through to drift link; why_new=only stale anchors were tested; seam=none
        self.stale_anchor()
        data = json.loads(self.drift_check_json.read_text())
        data["docs"][0]["result"] = "fresh"
        data["docs"][0]["anchors"][0]["result"] = "fresh"
        self.drift_check_json.write_text(json.dumps(data))
        result = self.run_script("okf-restamp.sh", "knowledge/concept.md", "src/lib.rs#fixture",
                                 "read fixture(): nothing moved at all")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is fresh; nothing to re-stamp, nothing logged", result.stdout)
        self.assertEqual(self.link_log.read_text(), "")
        self.assertNotIn("re-stamped", (self.root / "knowledge/log.md").read_text())

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
