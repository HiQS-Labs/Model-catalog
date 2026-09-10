import json
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
        self.catalog = json.loads(CATALOG.read_text())
        self.local = json.loads(LOCAL_MODELS.read_text())

    def validate(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local-models.json"
            path.write_text(json.dumps(data))
            return subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                text=True,
                capture_output=True,
            )

    def test_existing_catalog_contract_is_unchanged(self):
        self.assertEqual(self.catalog["schema"], "hiqs.model-catalog/1")
        self.assertEqual(self.catalog["version"], "1.3.0")
        self.assertEqual({row["target"] for row in self.catalog["aliases"]}, {"native", "openrouter"})
        self.assertTrue(all("runtime" not in row for row in self.catalog["aliases"]))

    def test_local_models_are_runtime_pinned(self):
        models = self.local["models"]
        self.assertEqual(len(models), 2)
        self.assertEqual({m["runtime"]["engine"] for m in models}, {"mlx", "ollama"})
        for model in models:
            self.assertRegex(model["artifact"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("local_path", model["runtime"])

    def test_validator_rejects_unpinned_artifact(self):
        broken = json.loads(json.dumps(self.local))
        del broken["models"][0]["artifact"]["sha256"]
        result = self.validate(broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact.sha256", result.stdout)

    def test_validator_rejects_machine_specific_path(self):
        broken = json.loads(json.dumps(self.local))
        broken["models"][0]["runtime"]["local_path"] = "/Users/example/model.gguf"
        result = self.validate(broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("machine-specific", result.stdout)


if __name__ == "__main__":
    unittest.main()
