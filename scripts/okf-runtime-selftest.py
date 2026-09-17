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
            "drift": '#!/bin/sh\ncat "$FIXTURE/drift.json"\nexit "${DRIFT_EXIT:-0}"\n',
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
            for name in ("okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh"):
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
            for name in ("okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh"):
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
        self.assertIn("held-non-code knowledge/concept.md -> VERSION", held.stdout)
        self.assertIn("drift unlink knowledge/concept.md VERSION", held.stdout)

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



if __name__ == "__main__":
    unittest.main(verbosity=2)
