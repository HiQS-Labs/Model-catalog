#!/usr/bin/env python3
"""Validate the portable local-model sidecar catalog."""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = {"mlx", "ollama"}
FORMATS = {"gguf", "mlx"}
STATUSES = {"ga", "preview", "deprecated"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "local-models.json"
    try:
        catalog = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"cannot read {path}: {exc}")
    if catalog.get("schema") != "hiqs.local-model-catalog/1":
        return fail("schema must be 'hiqs.local-model-catalog/1'")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(catalog.get("version", ""))):
        return fail("version must be semver")
    try:
        datetime.date.fromisoformat(catalog.get("updated", ""))
    except (TypeError, ValueError):
        return fail("updated must be a real YYYY-MM-DD date")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        return fail("models must be a non-empty list")

    keys, aliases, runtime_ids = set(), set(), set()
    for index, model in enumerate(models):
        where = f"model {index} ({model.get('key')!r})"
        for field in ("key", "display_name", "family", "provider", "source"):
            if not isinstance(model.get(field), str) or not model[field].strip():
                return fail(f"{where}: {field} missing or empty")
        if model["key"] in keys:
            return fail(f"{where}: duplicate key")
        keys.add(model["key"])
        if model.get("status") not in STATUSES:
            return fail(f"{where}: invalid status {model.get('status')!r}")
        if not isinstance(model.get("context_window"), int) or model["context_window"] <= 0:
            return fail(f"{where}: context_window must be a positive integer")
        try:
            datetime.date.fromisoformat(model.get("verified_on", ""))
        except (TypeError, ValueError):
            return fail(f"{where}: verified_on must be a real YYYY-MM-DD date")

        model_aliases = model.get("aliases")
        if not isinstance(model_aliases, list) or not model_aliases:
            return fail(f"{where}: aliases must be a non-empty list")
        for alias in model_aliases:
            normalized = " ".join(alias.lower().split()) if isinstance(alias, str) else ""
            if not normalized or normalized != alias:
                return fail(f"{where}: alias {alias!r} must be non-empty, lowercase, and whitespace-normalized")
            if normalized in aliases:
                return fail(f"{where}: duplicate alias {alias!r}")
            aliases.add(normalized)

        runtime = model.get("runtime")
        if not isinstance(runtime, dict):
            return fail(f"{where}: runtime object missing")
        for field in ("engine", "model_id", "format", "quantization"):
            if not isinstance(runtime.get(field), str) or not runtime[field].strip():
                return fail(f"{where}: runtime.{field} missing or empty")
        if runtime["engine"] not in ENGINES:
            return fail(f"{where}: unsupported engine {runtime['engine']!r}")
        if runtime["format"] not in FORMATS:
            return fail(f"{where}: unsupported format {runtime['format']!r}")
        runtime_key = (runtime["engine"], runtime["model_id"])
        if runtime_key in runtime_ids:
            return fail(f"{where}: duplicate engine/model_id pair {runtime_key!r}")
        runtime_ids.add(runtime_key)

        artifact = model.get("artifact")
        if not isinstance(artifact, dict):
            return fail(f"{where}: artifact object missing")
        for field in ("repository", "file", "revision", "sha256"):
            if not isinstance(artifact.get(field), str) or not artifact[field].strip():
                return fail(f"{where}: artifact.{field} missing or empty")
        if not REVISION.fullmatch(artifact["revision"]):
            return fail(f"{where}: artifact.revision must be a 40-character lowercase Git SHA")
        if not SHA256.fullmatch(artifact["sha256"]):
            return fail(f"{where}: artifact.sha256 must be 64 lowercase hex characters")
        if not isinstance(artifact.get("size_bytes"), int) or artifact["size_bytes"] <= 0:
            return fail(f"{where}: artifact.size_bytes must be a positive integer")
        if any(field in runtime or field in artifact for field in ("local_path", "endpoint", "credential")):
            return fail(f"{where}: machine-specific paths, endpoints, and credentials are forbidden")

    engines = ", ".join(sorted({model["runtime"]["engine"] for model in models}))
    print(f"OK: {len(models)} local models ({engines}), version {catalog['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
