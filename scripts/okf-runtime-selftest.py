#!/usr/bin/env python3
"""Offline regressions for gate/recall process boundaries, paths and JSON transport.

Run with python3 scripts/okf-runtime-selftest.py. Fixtures replace only okf/drift;
real shell and Perl execute the scripts under test. No network or shared cache.
"""
from __future__ import annotations

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
            "drift": '#!/bin/sh\ncat "$FIXTURE/drift.json"\nexit "${DRIFT_EXIT:-0}"\n',
        }.items():
            path = self.stub / name
            path.write_text(text)
            path.chmod(0o755)
        self.env = dict(os.environ, FIXTURE=str(self.root), TMPDIR=str(self.root),
                        PATH=str(self.stub) + os.pathsep + os.environ["PATH"])
        self.payload("validate", {"gate_passed": True, "is_conformant": True})
        self.payload("search", [{"concept_id": "project/state", "description": "Fixture state.", "score": 1}])
        self.verdict("fresh")

    def payload(self, name: str, value: object) -> None:
        (self.root / f"{name}.json").write_text(json.dumps(value))

    def verdict(self, result: str) -> None:
        self.payload("drift", {"docs": [{"path": "knowledge/project/state.md", "result": result, "anchors": [], "links": []}]})

    def run_script(self, script: str, bundle: str = "knowledge") -> subprocess.CompletedProcess[str]:
        args = [str(SCRIPTS / script)]
        if script == "okf-recall.sh":
            args.append("fixture")
        return subprocess.run(args + [bundle], cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def assert_unusable(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("1 fresh hit", result.stdout)
        self.assertNotIn("okf gate passed", result.stdout)
        self.assertNotIn("no concept", result.stdout)

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
                self.assert_unusable(self.run_script("okf-check.sh"))

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

    def test_recall_withholds_stale_for_equivalent_paths(self) -> None:
        self.verdict("stale")
        self.env["DRIFT_EXIT"] = "1"
        for bundle in ("knowledge", "./knowledge", "knowledge/", str(self.bundle)):
            with self.subTest(bundle=bundle):
                result = self.run_script("okf-recall.sh", bundle)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("WITHHELD", result.stdout)
                self.assertNotIn("1 fresh hit", result.stdout)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
