#!/usr/bin/env python3
"""Offline launcher contracts; fixture releases exercise the public shell boundary."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent.parent


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="okf-launcher-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "consumer with spaces"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.release = self.base / "release"
        self.release.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, XDG_CACHE_HOME=str(self.base / "cache"),
                        FIXTURE_RELEASE=str(self.release), PATH=f"{self.bin}:{os.environ['PATH']}")
        self.env.pop("OKF_DRIFT_ROOT", None)
        self.script("curl", '''#!/bin/sh
while [ "$#" -gt 0 ]; do
 case "$1" in -o) out=$2; shift 2;; https:*) url=$1; shift;; *) shift;; esac
done
cp "$FIXTURE_RELEASE/${url##*/}" "$out"
''', self.bin)
        self.script("gh", "#!/bin/sh\nexit 1\n", self.bin)
        for name in ("okf-check.sh", "okf-recall.sh", "okf-drift-bootstrap.sh"):
            self.script(name, '#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\nexit "${FIXTURE_STATUS:-0}"\n')
        (self.release / "okf-shim.sh").write_bytes((SOURCE / "scripts/okf-shim.sh").read_bytes())
        self.pin()

    def script(self, name, text, directory=None):
        path = (directory or self.release) / name
        path.write_text(text)
        path.chmod(0o755)
        return path

    def pin(self, tag="v0.7.0"):
        sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                       for p in sorted(self.release.iterdir()) if p.name != "SHA256SUMS")
        (self.release / "SHA256SUMS").write_text(sums)
        (self.repo / ".okf-drift-version").write_text(tag + "\n" + sums)

    def run_shim(self, *args, cwd=None, env=None, launcher=None):
        return subprocess.run(["sh", str(launcher or SOURCE / "scripts/okf-shim.sh"), *args],
                              cwd=cwd or self.base, env=env or self.env, text=True, capture_output=True)


class Launcher(Fixture):
    def test_explicit_root_without_consumer_scripts(self):
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh", "knowledge", "two words")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo.resolve()), "knowledge", "two words"])
        self.assertFalse((self.repo / "scripts").exists())

    def test_git_subdirectory_and_explicit_root_precedence(self):
        sub = self.repo / "nested"
        sub.mkdir()
        result = self.run_shim("okf-recall.sh", "a phrase", cwd=sub)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo.resolve()), "a phrase"])
        other = self.base / "other"
        other.mkdir()
        (other / ".okf-drift-version").write_bytes((self.repo / ".okf-drift-version").read_bytes())
        result = self.run_shim("--repo-root", str(other), "okf-check.sh", cwd=sub)
        self.assertEqual(result.stdout.strip(), str(other.resolve()))

    def test_legacy_position_and_exit_status(self):
        scripts = self.repo / "scripts"
        scripts.mkdir()
        shim = scripts / "okf-shim.sh"
        shim.write_bytes((SOURCE / "scripts/okf-shim.sh").read_bytes())
        result = self.run_shim("okf-check.sh", "knowledge", launcher=shim,
                               env=dict(self.env, FIXTURE_STATUS="17"))
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], str(self.repo.resolve()))

    def test_bad_requested_digest_never_executes(self):
        path = self.repo / ".okf-drift-version"
        original = path.read_text()
        line = next(x for x in original.splitlines() if x.endswith("  okf-check.sh"))
        for replacement in (line + "\n" + line, "bad  okf-check.sh", "", line + " extra"):
            with self.subTest(replacement=replacement):
                path.write_text(original.replace(line, replacement))
                result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_invalid_tag_is_rejected(self):
        self.pin("../../escape")
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_concurrent_worktrees_share_only_complete_cache_entries(self):
        other = self.base / "second worktree"
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-qm", "fixture"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "--detach", str(other)], check=True,
                       capture_output=True)
        (other / ".okf-drift-version").write_bytes((self.repo / ".okf-drift-version").read_bytes())
        roots = [self.repo, other] * 3
        processes = [subprocess.Popen(["sh", str(SOURCE / "scripts/okf-shim.sh"), "--repo-root", str(root), "okf-check.sh", "two words"],
                                      env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for root in roots]
        for root, process in zip(roots, processes):
            out, err = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, err)
            self.assertEqual(out.splitlines(), [str(root.resolve()), "two words"])
        cache = self.base / "cache/okf-drift/v0.7.0"
        self.assertEqual([p.name for p in cache.iterdir()], ["okf-check.sh"])
        self.assertEqual((cache / "okf-check.sh").read_bytes(), (self.release / "okf-check.sh").read_bytes())

    def test_download_empty_wrong_digest_and_missing_hash_tool(self):
        args = ("--repo-root", str(self.repo), "okf-check.sh")
        for contents in ("", "#!/bin/sh\\necho UNVERIFIED\\n"):
            (self.release / "okf-check.sh").write_text(contents)
            result = self.run_shim(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("UNVERIFIED", result.stdout)
            self.assertFalse((self.base / "cache/okf-drift/v0.7.0/okf-check.sh").exists())
        isolated = self.base / "minimal-bin"
        isolated.mkdir()
        import shutil
        for name in ("sed", "grep", "awk"):
            (isolated / name).symlink_to(shutil.which(name))
        result = subprocess.run(["/bin/sh", str(SOURCE / "scripts/okf-shim.sh"), *args],
                                env=dict(self.env, PATH=str(isolated)), text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("neither shasum nor sha256sum", result.stderr)

    def test_missing_pin_and_unrelated_cwd_fail_closed(self):
        result = self.run_shim("okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no Git root", result.stderr)
        (self.repo / ".okf-drift-version").unlink()
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("missing", result.stderr)

    def test_cache_corruption_and_download_failure(self):
        args = ("--repo-root", str(self.repo), "okf-check.sh")
        self.assertEqual(self.run_shim(*args).returncode, 0)
        cached = self.base / "cache/okf-drift/v0.7.0/okf-check.sh"
        cached.write_text("#!/bin/sh\nexit 0\n")
        self.assertEqual(self.run_shim(*args).returncode, 2)
        cached.unlink()
        (self.release / "okf-check.sh").unlink()
        self.assertEqual(self.run_shim(*args).returncode, 2)
        self.assertFalse(cached.exists())

    def test_explicit_root_refuses_old_pin_without_upgrading(self):
        self.pin("v0.6.2")
        before = (self.repo / ".okf-drift-version").read_bytes()
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("v0.7.0", result.stderr)
        self.assertEqual((self.repo / ".okf-drift-version").read_bytes(), before)

    def test_visible_development_override(self):
        dev = self.base / "dev"
        (dev / "scripts").mkdir(parents=True)
        self.script("okf-check.sh", '#!/bin/sh\npwd\n', dev / "scripts")
        (self.repo / ".okf-drift-version").unlink()
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh",
                               env=dict(self.env, OKF_DRIFT_ROOT=str(dev)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("development override", result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.repo.resolve()))

    def ci(self):
        text = (SOURCE / "skills/okf-setup/templates/knowledge.yml").read_text()
        if "      - name: pinned runtime gate\n        run: |\n" in text:
            body = text.split("      - name: pinned runtime gate\n        run: |\n", 1)[1]
            command = "\n".join(line[10:] for line in body.splitlines())
        else:
            command = "scripts/okf-check.sh knowledge"
        return subprocess.run(["sh", "-c", command], cwd=self.repo, env=dict(self.env, OKF_DRIFT_ROOT="/must/not/be/used"),
                              text=True, capture_output=True)

    def test_ci_bootstrap_without_plugin_or_consumer_scripts(self):
        result = self.ci()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo.resolve()), "knowledge"])
        self.assertFalse((self.repo / "scripts").exists())
        (self.release / "okf-shim.sh").write_text("#!/bin/sh\necho UNVERIFIED\n")
        result = self.ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("UNVERIFIED", result.stdout)

    def test_newer_plugin_does_not_replace_pinned_runtime(self):
        plugin = self.base / "new plugin"
        (plugin / "scripts").mkdir(parents=True)
        (plugin / "VERSION").write_text("9.0.0\n")
        launcher = plugin / "scripts/okf-shim.sh"
        launcher.write_bytes((SOURCE / "scripts/okf-shim.sh").read_bytes())
        self.script("okf-check.sh", '#!/bin/sh\necho UNPINNED\n', plugin / "scripts")
        result = self.run_shim("--repo-root", str(self.repo), "okf-check.sh", "knowledge", launcher=launcher)
        ci = self.ci()
        self.assertEqual(result.returncode, ci.returncode, result.stderr + ci.stderr)
        self.assertEqual(result.stdout, ci.stdout)
        self.assertNotIn("UNPINNED", result.stdout)

    def test_ci_rejects_missing_duplicate_malformed_shim_hash_and_asset(self):
        pin = self.repo / ".okf-drift-version"
        original = pin.read_text()
        line = next(x for x in original.splitlines() if x.endswith("  okf-shim.sh"))
        for replacement in ("", line + "\n" + line, "bad  okf-shim.sh"):
            pin.write_text(original.replace(line, replacement))
            result = self.ci()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")
        pin.write_text(original)
        (self.release / "okf-shim.sh").unlink()
        self.assertNotEqual(self.ci().returncode, 0)

    def test_ci_refuses_pre_root_aware_pin(self):
        self.pin("v0.6.2")
        result = self.ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("v0.7.0", result.stderr)

    def test_runtime_skill_uses_host_directory_without_implicit_environment(self):
        skill = SOURCE / "skills/okf-runtime/SKILL.md"
        self.assertTrue(skill.exists(), "model-invocable runtime skill is missing")
        text = skill.read_text()
        self.assertNotIn("disable-model-invocation: true", text)
        code = text.split("```sh\n", 1)[1].split("```", 1)[0]
        code = code.replace("<host-supplied absolute skill directory>", str(skill.parent))
        code = code.replace("<absolute consumer root>", str(self.repo))
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        result = subprocess.run(["sh", "-c", code], cwd=self.base, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo.resolve()), "knowledge"])
        for name in ("read", "write", "setup", "migrate"):
            manual = (SOURCE / f"skills/okf-{name}/SKILL.md").read_text()
            self.assertIn(f"MANUAL TRIGGER ONLY: invoke only when the user types /okf-{name}.", manual)
            self.assertIn("disable-model-invocation: true", manual)

    def test_skill_templates_have_no_consumer_wrapper_commands(self):
        for path in (SOURCE / "skills").rglob("*.md"):
            text = path.read_text()
            for name in ("okf-check", "okf-recall"):
                self.assertNotIn(f"scripts/{name}.sh", text, str(path))

    def test_pin_rejects_missing_duplicate_or_malformed_required_hash(self):
        sums = (self.release / "SHA256SUMS").read_text()
        before = (self.repo / ".okf-drift-version").read_bytes()
        for name in ("okf-check.sh", "okf-recall.sh", "okf-shim.sh", "okf-drift-bootstrap.sh"):
            line = next(x for x in sums.splitlines() if x.endswith("  " + name))
            for replacement in ("", line + "\n" + line, "bad  " + name):
                with self.subTest(name=name, replacement=replacement):
                    (self.release / "SHA256SUMS").write_text(sums.replace(line, replacement))
                    result = subprocess.run(["sh", str(SOURCE / "scripts/okf-pin.sh"), "v0.7.0", str(self.repo)],
                                            env=self.env, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual((self.repo / ".okf-drift-version").read_bytes(), before)


class Integration(Fixture):
    def integrate(self, *args):
        return subprocess.run(["python3", str(SOURCE / "scripts/okf-integrate.py"),
                               "--repo-root", str(self.repo), *args], env=self.env,
                              text=True, capture_output=True)

    def historic(self, tag, path):
        return subprocess.check_output(["git", "-C", str(SOURCE), "show", f"{tag}:{path}"])

    def legacy(self):
        scripts = self.repo / "scripts"
        scripts.mkdir()
        (scripts / "okf-shim.sh").write_bytes(self.historic("v0.5.1", "scripts/okf-shim.sh"))
        for name in ("okf-check", "okf-recall"):
            (scripts / f"{name}.sh").write_text(
                f'#!/bin/sh\n# {name}.sh from alvistar/okf-drift at the tag in .okf-drift-version — see scripts/okf-shim.sh.\n'
                f'exec "$(dirname "$0")/okf-shim.sh" {name}.sh "$@"\n')
        (scripts / "mine.sh").write_text("do not touch\n")
        workflows = self.repo / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "knowledge.yml").write_bytes(self.historic("v0.6.2", "skills/okf-setup/templates/knowledge.yml"))
        old = self.historic("v0.6.2", "skills/okf-setup/templates/CLAUDE-knowledge-section.md").decode()
        old = old.replace("At the start of every session read", "First read docs/HANDOVER.md, then read")
        (self.repo / "CLAUDE.md").write_text("# Identity\nRead docs/HANDOVER.md first.\n\n" + old + "\n## Other\nKeep this.\n")
        (self.repo / "knowledge").mkdir()
        (self.repo / "knowledge/index.md").write_text('Historical command: scripts/okf-recall.sh "terms"\n')
        (self.repo / "drift.lock").write_text('version = 1\n')

    def snapshot(self):
        return {str(p.relative_to(self.repo)): ("symlink", os.readlink(p)) if p.is_symlink() else p.read_bytes()
                for p in self.repo.rglob("*") if ".git" not in p.relative_to(self.repo).parts and (p.is_symlink() or p.is_file())}

    def test_install_creates_no_scripts_and_is_idempotent(self):
        result = self.integrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.repo / "scripts").exists())
        before = self.snapshot()
        self.assertEqual(self.integrate().returncode, 0)
        self.assertEqual(before, self.snapshot())
        self.assertIn("okf-runtime", (self.repo / "CLAUDE.md").read_text())

    def test_legacy_conversion_preserves_bundle_lock_and_custom_navigation(self):
        self.legacy()
        before = self.snapshot()
        result = self.integrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.snapshot()
        for name in ("knowledge/index.md", "drift.lock", "scripts/mine.sh", ".okf-drift-version"):
            self.assertEqual(before[name], after[name])
        self.assertIn("knowledge/index.md", result.stderr)
        self.assertIn("First read docs/HANDOVER.md", (self.repo / "CLAUDE.md").read_text())
        for name in ("okf-check.sh", "okf-recall.sh", "okf-shim.sh"):
            self.assertFalse((self.repo / "scripts" / name).exists())
        self.assertEqual(self.integrate().returncode, 0)
        self.assertEqual(after, self.snapshot())

    def section(self, text, title):
        return re.search(rf"^## {re.escape(title)}\n.*?(?=^## |\Z)", text, re.M | re.S)[0].rstrip()

    def test_official_v0_8_2_sections_are_recognised_and_upgraded(self):
        # The OUTGOING release's body digests must be in SECTIONS before the template text
        # moves; otherwise every consumer carrying the previous official body is refused
        # as "customized; merge explicitly" and cannot be upgraded at all.
        official = self.historic("v0.8.2", "skills/okf-setup/templates/CLAUDE-knowledge-section.md").decode()
        (self.repo / "CLAUDE.md").write_text("# Identity\n\n" + official + "\n## Other\nKeep this.\n")
        result = self.integrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("customized", result.stderr)
        text = (self.repo / "CLAUDE.md").read_text()
        current = (SOURCE / "skills/okf-setup/templates/CLAUDE-knowledge-section.md").read_text()
        for title in ("Knowledge Bundle", "Work Loop"):
            self.assertIn(self.section(current, title), text, title)
        self.assertIn("Keep this.", text)
        after = self.snapshot()
        self.assertEqual(self.integrate().returncode, 0)
        self.assertEqual(after, self.snapshot())

    def test_frontmatter_okf_accepts_is_not_parsed_as_strict_yaml(self):
        # okf accepts a description whose value starts with an unquoted backtick; a strict
        # YAML parser raises on it, and 12 concepts on the reference consumer carry one.
        # Only code_refs is needed here, so it is read with the bootstrap's line rule.
        self.legacy()
        concept = self.repo / "knowledge/concept.md"
        head = '---\ntype: Reference\ndescription: `a/b.sh` runs on every push\n'
        concept.write_text(head + "code_refs:\n  - src/app.py\n  - 'docs/notes.md'\n---\nBody.\n")
        before = self.snapshot()
        result = self.integrate("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())
        # The same description, with a binding to a deletion candidate: the list is still read.
        concept.write_text(head + "code_refs:\n  - scripts/okf-check.sh\n---\nBody.\n")
        before = self.snapshot()
        result = self.integrate("--dry-run")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("code_refs binds a deletion candidate", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_modified_wrapper_preflight_changes_nothing_even_with_upgrade(self):
        self.legacy()
        with (self.repo / "scripts/okf-check.sh").open("a") as f:
            f.write("# custom\n")
        before = self.snapshot()
        result = self.integrate("--tag", "v0.8.0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("scripts/okf-check.sh", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_preflight_rejects_each_customized_candidate(self):
        self.legacy()
        for name in ("scripts/okf-shim.sh", "scripts/okf-recall.sh", ".github/workflows/knowledge.yml", "CLAUDE.md"):
            path = self.repo / name
            original = path.read_bytes()
            if name == "CLAUDE.md":
                path.write_bytes(original.replace(b"## Work Loop", b"## Work Loop\nCustom rule."))
            else:
                path.write_bytes(original + b"# custom\n")
            before = self.snapshot()
            result = self.integrate()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(name, result.stderr)
            self.assertEqual(before, self.snapshot())
            path.write_bytes(original)

    def test_preflight_rejects_symlinks_including_parent_directories(self):
        self.legacy()
        for name in ("scripts/okf-check.sh", "scripts/okf-shim.sh", "CLAUDE.md", ".okf-drift-version", "drift.lock"):
            path = self.repo / name
            original = path.read_bytes()
            external = self.base / "external"
            external.write_bytes(original)
            path.unlink()
            path.symlink_to(external)
            before = self.snapshot()
            result = self.integrate()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("symlink", result.stderr)
            self.assertEqual(before, self.snapshot())
            self.assertEqual(external.read_bytes(), original)
            path.unlink()
            path.write_bytes(original)
        scripts = self.repo / "scripts"
        moved = self.base / "outside-scripts"
        scripts.rename(moved)
        scripts.symlink_to(moved, target_is_directory=True)
        result = self.integrate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("symlink", result.stderr)

    def test_code_refs_and_bindings_refuse_deletion(self):
        self.legacy()
        concept = self.repo / "knowledge/concept.md"
        for target in ("scripts/okf-check.sh", "./scripts/okf-recall.sh#main", "scripts", "scripts/*", "."):
            concept.write_text(f'---\ntype: Reference\ncode_refs: ["{target}"]\n---\n')
            before = self.snapshot()
            result = self.integrate()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("code_refs", result.stderr)
            self.assertEqual(before, self.snapshot())
        concept.unlink()
        (self.repo / "drift.lock").write_text('version = 1\n[[bindings]]\ndoc="knowledge/index.md"\ntarget="scripts/okf-shim.sh"\nsig="a"\n')
        before = self.snapshot()
        result = self.integrate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("binding", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_code_ref_alias_to_deletion_candidate_is_protected(self):
        self.legacy()
        (self.repo / "gate-alias").symlink_to("scripts/okf-check.sh")
        (self.repo / "knowledge/concept.md").write_text('---\ntype: Reference\ncode_refs: [gate-alias]\n---\n')
        before = self.snapshot()
        result = self.integrate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("code_refs", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_old_pin_requires_explicit_upgrade_and_failed_download_is_nondestructive(self):
        self.legacy()
        self.pin("v0.6.2")
        before = self.snapshot()
        result = self.integrate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("v0.7.0", result.stderr)
        self.assertEqual(before, self.snapshot())
        sums = self.release / "SHA256SUMS"
        original = sums.read_bytes()
        sums.unlink()
        self.assertEqual(self.integrate("--tag", "v0.7.0").returncode, 2)
        self.assertEqual(before, self.snapshot())
        sums.write_bytes(original)
        result = self.integrate("--tag", "v0.7.0", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())
        result = self.integrate("--tag", "v0.7.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / ".okf-drift-version").read_text().startswith("v0.7.0\n"))


if __name__ == "__main__":
    unittest.main()
