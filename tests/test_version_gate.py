import json
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check_version_bump.py"
SPEC = importlib.util.spec_from_file_location("check_version_bump", GATE)
GATE_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE_MODULE)


class VersionGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        self.write("data/catalog.json", "1.0.0", "2026-09-01")
        self.commit("base")
        self.base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, version, updated):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"version": version, "updated": updated}), encoding="utf-8")

    def commit(self, message):
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=self.repo, check=True)

    def gate(self, path="data/catalog.json", *extra, base=None):
        return subprocess.run(
            [sys.executable, str(GATE), "--base-ref", base or self.base, "--path", path,
             "--today", "2026-09-10", *extra],
            cwd=self.repo, text=True, capture_output=True)

    def test_unchanged_passes(self):
        self.assertEqual(self.gate().returncode, 0)

    def test_later_monotonic_release_passes(self):
        self.write("data/catalog.json", "1.1.0", "2026-09-09")
        self.commit("bump")
        self.assertEqual(self.gate().returncode, 0)

    def test_same_version_and_downgrade_fail(self):
        for version in ("1.0.0", "0.9.0"):
            with self.subTest(version=version):
                self.write("data/catalog.json", version, "2026-09-09")
                self.commit(version)
                self.assertNotEqual(self.gate().returncode, 0)

    def test_first_publication_and_missing_base(self):
        self.write("data/local-models.json", "1.0.0", "2026-09-09")
        self.commit("local")
        self.assertEqual(self.gate("data/local-models.json", "--initial-version", "1.0.0").returncode, 0)
        self.assertNotEqual(self.gate(base="missing-ref").returncode, 0)

    def test_date_must_advance_but_need_not_equal_today(self):
        self.write("data/catalog.json", "1.0.1", "2026-09-01")
        self.commit("stale date")
        self.assertNotEqual(self.gate().returncode, 0)

    def test_git_operation_failures_fail_closed(self):
        ok = subprocess.CompletedProcess([], 0, "", "")
        changed = subprocess.CompletedProcess([], 1, "", "")
        failed = subprocess.CompletedProcess([], 2, "", "injected failure")
        present = subprocess.CompletedProcess([], 0, "data/catalog.json\n", "")
        scenarios = [
            [ok, failed],
            [ok, changed, failed],
            [ok, changed, present, failed],
        ]
        argv = ["check_version_bump.py", "--base-ref", self.base, "--path", "data/catalog.json", "--today", "2026-09-10"]
        for results in scenarios:
            with self.subTest(results=[r.returncode for r in results]):
                with mock.patch.object(GATE_MODULE, "git", side_effect=results), mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                    self.assertNotEqual(GATE_MODULE.main(), 0)

    def test_explicit_base_fetch_works_in_shallow_clone(self):
        subprocess.run(["git", "switch", "-qc", "feature"], cwd=self.repo, check=True)
        self.write("data/catalog.json", "1.1.0", "2026-09-09")
        self.commit("feature")
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            subprocess.run(["git", "clone", "-q", "--depth=1", "--branch", "feature", f"file://{self.repo}", str(clone)], check=True)
            subprocess.run(["git", "fetch", "-q", "--no-tags", "--depth=1", "origin", "+refs/heads/main:refs/remotes/origin/main"], cwd=clone, check=True)
            result = subprocess.run(
                [sys.executable, str(GATE), "--base-ref", "origin/main", "--path", "data/catalog.json", "--today", "2026-09-10"],
                cwd=clone, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
