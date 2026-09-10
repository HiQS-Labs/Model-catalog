#!/usr/bin/env python3
"""Validate the portable local-model sidecar catalog."""
import datetime
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"ga", "preview", "deprecated"}
RUNTIME_CONTRACTS = {
    ("ollama", "gguf"): {"Q4_K_M", "Q8_0", "F16"},
    ("mlx", "mlx"): {"4bit", "8bit", "bf16"},
}
ROOT_FIELDS = {"schema", "version", "updated", "models"}
MODEL_FIELDS = {"key", "display_name", "family", "provider", "status", "aliases", "runtime",
                "artifact", "model_context_window", "tested_context_window", "source", "verified_on"}
RUNTIME_FIELDS = {"engine", "model_id", "format", "quantization"}
ARTIFACT_FIELDS = {"repository", "file", "url", "revision", "sha256", "size_bytes"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OLLAMA_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$")
ARTIFACT_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def reject_duplicate_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def valid_date(value) -> bool:
    if not isinstance(value, str) or not DATE.fullmatch(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def unexpected_fields(value: dict, allowed: set[str]) -> list[str]:
    return sorted(set(value) - allowed)


def portable_file(value: str) -> bool:
    path = PurePosixPath(value)
    return (bool(path.parts) and not path.is_absolute() and value == path.as_posix()
            and all(ARTIFACT_COMPONENT.fullmatch(part) for part in path.parts))


def repository_id(value: str) -> bool:
    return bool(REPOSITORY.fullmatch(value)) and all(part not in {".", ".."} for part in value.split("/"))


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "local-models.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_members)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return fail(f"cannot read {path}: {exc}")
    if not isinstance(catalog, dict):
        return fail("catalog root must be an object")
    extra = unexpected_fields(catalog, ROOT_FIELDS)
    if extra:
        return fail(f"catalog contains unsupported fields: {', '.join(extra)}")
    if catalog.get("schema") != "hiqs.local-model-catalog/1":
        return fail("schema must be 'hiqs.local-model-catalog/1'")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(catalog.get("version", ""))):
        return fail("version must be semver")
    if not valid_date(catalog.get("updated")):
        return fail("updated must be a real YYYY-MM-DD date")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        return fail("models must be a non-empty list")

    keys, aliases, runtime_ids = set(), set(), set()
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            return fail(f"model {index} must be an object")
        where = f"model {index} ({model.get('key')!r})"
        extra = unexpected_fields(model, MODEL_FIELDS)
        if extra:
            return fail(f"{where}: unsupported fields: {', '.join(extra)}")
        for field in ("key", "display_name", "family", "provider", "source"):
            if not isinstance(model.get(field), str) or not model[field].strip():
                return fail(f"{where}: {field} missing or empty")
        if model["key"] in keys:
            return fail(f"{where}: duplicate key")
        keys.add(model["key"])
        if not isinstance(model.get("status"), str) or model["status"] not in STATUSES:
            return fail(f"{where}: invalid status {model.get('status')!r}")
        if not positive_int(model.get("model_context_window")):
            return fail(f"{where}: model_context_window must be a positive integer")
        tested = model.get("tested_context_window")
        if tested is not None and (not positive_int(tested) or tested > model["model_context_window"]):
            return fail(f"{where}: tested_context_window must be a positive integer no larger than model_context_window")
        if not valid_date(model.get("verified_on")):
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
        extra = unexpected_fields(runtime, RUNTIME_FIELDS)
        if extra:
            return fail(f"{where}: runtime contains unsupported fields: {', '.join(extra)}")
        for field in RUNTIME_FIELDS:
            if not isinstance(runtime.get(field), str) or not runtime[field].strip():
                return fail(f"{where}: runtime.{field} missing or empty")
        pair = (runtime["engine"], runtime["format"])
        if pair not in RUNTIME_CONTRACTS:
            return fail(f"{where}: unsupported engine/format pair {pair!r}")
        if runtime["quantization"] not in RUNTIME_CONTRACTS[pair]:
            return fail(f"{where}: unsupported quantization {runtime['quantization']!r} for {pair!r}")
        if runtime["engine"] == "ollama" and not OLLAMA_ID.fullmatch(runtime["model_id"]):
            return fail(f"{where}: runtime.model_id must be a portable Ollama model name")
        if runtime["engine"] == "mlx" and not repository_id(runtime["model_id"]):
            return fail(f"{where}: runtime.model_id must be a portable MLX owner/repository ID")
        runtime_key = (runtime["engine"], runtime["model_id"])
        if runtime_key in runtime_ids:
            return fail(f"{where}: duplicate engine/model_id pair {runtime_key!r}")
        runtime_ids.add(runtime_key)

        artifact = model.get("artifact")
        if not isinstance(artifact, dict):
            return fail(f"{where}: artifact object missing")
        extra = unexpected_fields(artifact, ARTIFACT_FIELDS)
        if extra:
            return fail(f"{where}: artifact contains unsupported fields: {', '.join(extra)}")
        for field in ("repository", "file", "url", "revision", "sha256"):
            if not isinstance(artifact.get(field), str) or not artifact[field].strip():
                return fail(f"{where}: artifact.{field} missing or empty")
        if not repository_id(artifact["repository"]):
            return fail(f"{where}: artifact.repository must be owner/repository")
        if not portable_file(artifact["file"]):
            return fail(f"{where}: artifact.file must be a portable relative path without traversal")
        expected_url = f"https://huggingface.co/{artifact['repository']}/resolve/{artifact['revision']}/{artifact['file']}"
        if artifact["url"] != expected_url:
            return fail(f"{where}: artifact.url must be an HTTPS Hugging Face URL pinned to artifact.revision")
        if not REVISION.fullmatch(artifact["revision"]):
            return fail(f"{where}: artifact.revision must be a 40-character lowercase Git SHA")
        if not SHA256.fullmatch(artifact["sha256"]):
            return fail(f"{where}: artifact.sha256 must be 64 lowercase hex characters")
        if not positive_int(artifact.get("size_bytes")):
            return fail(f"{where}: artifact.size_bytes must be a positive integer")

    engines = ", ".join(sorted({model["runtime"]["engine"] for model in models}))
    print(f"OK: {len(models)} local models ({engines}), version {catalog['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
