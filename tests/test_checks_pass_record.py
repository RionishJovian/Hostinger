"""Tests for check/deploy pass-recording helpers (scripts/check.sh checks_pass_lib)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_SH = ROOT / "scripts" / "check.sh"


def invoke(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ | {"CHECKS_PASS_LIB_ONLY": "1"}
    return subprocess.run(
        ["bash", str(CHECK_SH), "invoke", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ChecksPassRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.cwd,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.cwd, check=True, capture_output=True)
        (self.cwd / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.cwd, check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_and_read_stamp(self):
        invoke("checks_pass_write_stamp", "abc123", "def456", cwd=self.cwd)
        tree = invoke("checks_pass_read_tree", cwd=self.cwd)
        commit = invoke("checks_pass_read_commit", cwd=self.cwd)
        self.assertEqual(tree.returncode, 0)
        self.assertEqual(tree.stdout.strip(), "abc123")
        self.assertEqual(commit.stdout.strip(), "def456")

    def test_tree_with_manifest_staged(self):
        manifest = self.cwd / ".corrective-source-manifest.txt"
        manifest.write_text("old manifest\n", encoding="utf-8")
        subprocess.run(["git", "add", ".corrective-source-manifest.txt"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add manifest"], cwd=self.cwd, check=True, capture_output=True)
        head_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=self.cwd, text=True).strip()

        manifest.write_text("new manifest content\n", encoding="utf-8")
        staged_tree = invoke("checks_pass_tree_with_manifest_staged", cwd=self.cwd)
        self.assertEqual(staged_tree.returncode, 0)
        new_tree = staged_tree.stdout.strip()
        self.assertNotEqual(new_tree, head_tree)
        self.assertEqual(
            subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=self.cwd, text=True).strip(),
            head_tree,
        )

    def test_diff_docs_only_allows_md_and_manifest(self):
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.cwd, text=True).strip()
        (self.cwd / "docs").mkdir()
        (self.cwd / "docs" / "note.md").write_text("doc\n", encoding="utf-8")
        (self.cwd / ".corrective-source-manifest.txt").write_text("manifest v2\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/note.md", ".corrective-source-manifest.txt"], cwd=self.cwd, check=True)
        subprocess.run(["git", "commit", "-m", "docs"], cwd=self.cwd, check=True, capture_output=True)
        ok = invoke("checks_pass_diff_docs_only", base, cwd=self.cwd)
        self.assertEqual(ok.returncode, 0, msg=ok.stderr)

    def test_diff_docs_only_rejects_code_changes(self):
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.cwd, text=True).strip()
        (self.cwd / "app.py").write_text("print(1)\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=self.cwd, check=True)
        subprocess.run(["git", "commit", "-m", "code"], cwd=self.cwd, check=True, capture_output=True)
        bad = invoke("checks_pass_diff_docs_only", base, cwd=self.cwd)
        self.assertNotEqual(bad.returncode, 0)

    def test_manifest_only_dirty(self):
        manifest = self.cwd / ".corrective-source-manifest.txt"
        manifest.write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "add", ".corrective-source-manifest.txt"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "manifest"], cwd=self.cwd, check=True, capture_output=True)
        manifest.write_text("dirty\n", encoding="utf-8")
        only = invoke("checks_pass_manifest_only_dirty", cwd=self.cwd)
        self.assertEqual(only.returncode, 0, msg=only.stderr)
        (self.cwd / "other.txt").write_text("x\n", encoding="utf-8")
        not_only = invoke("checks_pass_manifest_only_dirty", cwd=self.cwd)
        self.assertNotEqual(not_only.returncode, 0)


class RunTestsResolveModuleTests(unittest.TestCase):
    def test_resolve_paths(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_tests", ROOT / "scripts" / "run-tests.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        self.assertEqual(mod.resolve_module("test_hubs"), "test_hubs")
        self.assertEqual(mod.resolve_module("hubs"), "test_hubs")
        self.assertEqual(mod.resolve_module("tests/test_hubs.py"), "test_hubs")


if __name__ == "__main__":
    unittest.main()
