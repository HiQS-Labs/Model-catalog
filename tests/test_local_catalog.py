import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog.json"
LOCAL_MODELS = ROOT / "data" / "local-models.json"
VALIDATOR = ROOT / "scripts" / "validate_local_models.py"


class LocalCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.local = json.loads(LOCAL_MODELS.read_text(encoding="utf-8"))

    def validate_raw(self, raw: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local-models.json"
            path.write_text(raw, encoding="utf-8")
            return subprocess.run([sys.executable, str(VALIDATOR), str(path)], text=True, capture_output=True)

    def validate(self, data):
        return self.validate_raw(json.dumps(data))

    def test_existing_catalog_contract_is_unchanged(self):
        self.assertEqual(self.catalog["schema"], "hiqs.model-catalog/1")
        self.assertRegex(self.catalog["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual({row["target"] for row in self.catalog["aliases"]}, {"native", "openrouter"})
        self.assertTrue(all("runtime" not in row for row in self.catalog["aliases"]))

    def test_current_local_catalog_passes_validator(self):
        result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.local["models"])
        self.assertTrue({"mlx", "ollama"} <= {m["runtime"]["engine"] for m in self.local["models"]})

    def test_validator_rejects_invalid_values(self):
        cases = []
        for label, mutation, expected in [
            ("missing hash", lambda d: d["models"][0]["artifact"].pop("sha256"), "artifact.sha256"),
            ("bool integer", lambda d: d["models"][0]["artifact"].__setitem__("size_bytes", True), "positive integer"),
            ("week date", lambda d: d.__setitem__("updated", "2026-W37-4"), "YYYY-MM-DD"),
            ("bad pair", lambda d: d["models"][0]["runtime"].__setitem__("format", "mlx"), "engine/format pair"),
            ("bad quant", lambda d: d["models"][0]["runtime"].__setitem__("quantization", "banana"), "quantization"),
            ("absolute path", lambda d: d["models"][0]["artifact"].__setitem__("file", "/tmp/model.gguf"), "portable relative"),
            ("traversal", lambda d: d["models"][0]["artifact"].__setitem__("file", "../model.gguf"), "portable relative"),
            ("windows path", lambda d: d["models"][0]["artifact"].__setitem__("file", "models\\model.gguf"), "portable relative"),
            ("runtime absolute path", lambda d: d["models"][0]["runtime"].__setitem__("model_id", "/Users/alice/model"), "portable Ollama"),
            ("runtime traversal", lambda d: d["models"][0]["runtime"].__setitem__("model_id", "../model"), "portable Ollama"),
            ("runtime endpoint", lambda d: d["models"][0]["runtime"].__setitem__("model_id", "http://localhost/model"), "portable Ollama"),
            ("mutable URL", lambda d: d["models"][0]["artifact"].__setitem__("url", d["models"][0]["artifact"]["url"].replace(d["models"][0]["artifact"]["revision"], "main")), "pinned"),
            ("blob URL", lambda d: d["models"][0]["artifact"].__setitem__("url", d["models"][0]["artifact"]["url"].replace("/resolve/", "/blob/")), "pinned"),
            ("fragment URL", lambda d: d["models"][0]["artifact"].__setitem__("url", d["models"][0]["artifact"]["url"] + "#/" + d["models"][0]["artifact"]["revision"] + "/" + d["models"][0]["artifact"]["file"]), "pinned"),
            ("MLX traversal", lambda d: d["models"][1]["runtime"].__setitem__("model_id", "../model"), "portable MLX"),
            ("MLX dot owner", lambda d: d["models"][1]["runtime"].__setitem__("model_id", "./model"), "portable MLX"),
            ("MLX dot repo", lambda d: d["models"][1]["runtime"].__setitem__("model_id", "owner/.."), "portable MLX"),
            ("artifact traversal repo", lambda d: d["models"][0]["artifact"].__setitem__("repository", "../model"), "owner/repository"),
            ("status object", lambda d: d["models"][0].__setitem__("status", []), "invalid status"),
            ("root machine field", lambda d: d.__setitem__("endpoint", "http://localhost"), "unsupported fields"),
            ("model machine field", lambda d: d["models"][0].__setitem__("local_path", "/tmp/x"), "unsupported fields"),
        ]:
            broken = copy.deepcopy(self.local)
            mutation(broken)
            cases.append((label, broken, expected))
        for label, broken, expected in cases:
            with self.subTest(label=label):
                result = self.validate(broken)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout)

    def test_validator_rejects_duplicate_members_and_bad_shapes(self):
        duplicate = LOCAL_MODELS.read_text(encoding="utf-8").replace(
            '"schema": "hiqs.local-model-catalog/1",',
            '"schema": "hiqs.local-model-catalog/1", "schema": "hiqs.local-model-catalog/1",', 1)
        result = self.validate_raw(duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate JSON member", result.stdout)
        for raw in ("[]", '{"schema":"hiqs.local-model-catalog/1","version":"1.0.0","updated":"2026-09-10","models":[1]}'):
            with self.subTest(raw=raw):
                self.assertNotEqual(self.validate_raw(raw).returncode, 0)

    @unittest.skipUnless(shutil.which("cargo"), "cargo is required for the closed-enum regression")
    def test_closed_enum_consumer_rejects_local_target_before_filtering(self):
        broken = copy.deepcopy(self.catalog)
        broken["aliases"].append({
            "match": "local test", "replace": "local/test", "target": "local",
            "provider": "test", "source": "test", "verified_on": None, "flags": [],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            result = subprocess.run(
                ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "examples/rust/Cargo.toml"), "--", str(path)],
                cwd=ROOT, text=True, capture_output=True,
                env={**os.environ, "CARGO_TARGET_DIR": str(Path(tmp) / "target")})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown variant", result.stderr)

    def test_validator_rejects_duplicate_catalog_identifiers(self):
        duplicate_key = copy.deepcopy(self.local)
        duplicate_key["models"][1]["key"] = duplicate_key["models"][0]["key"]
        duplicate_alias = copy.deepcopy(self.local)
        duplicate_alias["models"][1]["aliases"] = duplicate_alias["models"][0]["aliases"]
        duplicate_runtime = copy.deepcopy(self.local)
        duplicate_runtime["models"][1]["runtime"] = copy.deepcopy(duplicate_runtime["models"][0]["runtime"])
        for broken, expected in [
            (duplicate_key, "duplicate key"),
            (duplicate_alias, "duplicate alias"),
            (duplicate_runtime, "duplicate engine/model_id"),
        ]:
            with self.subTest(expected=expected):
                result = self.validate(broken)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout)

    def test_valid_owner_repository_identifier_is_accepted(self):
        valid = copy.deepcopy(self.local)
        valid["models"][1]["runtime"]["model_id"] = "owner-name/repo.name_2"
        self.assertEqual(self.validate(valid).returncode, 0)


if __name__ == "__main__":
    unittest.main()
