#!/usr/bin/env python3
"""Compile data/catalog.json from data/models.json and data/aliases.json.

Deterministic compiler that transforms canonical model entities and alias rules into
the flat data/catalog.json consumed by downstream resolvers. Supports deterministic
spelling variant generation (spacing, vendor prefix) and CI sync checks (--check).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def generate_variants(phrase: str, provider: str, variant_rules: list) -> list:
    """Deterministically generate spelling variants according to requested rules."""
    results = {phrase}
    
    if "spacing" in variant_rules:
        # Spacing: "hy4" <-> "hy 4", "fable5" <-> "fable 5"
        for p in list(results):
            # Letter followed by digit -> insert space
            results.add(re.sub(r"([a-z])([0-9])", r"\1 \2", p))
            # Letter space digit -> remove space
            results.add(re.sub(r"([a-z])\s+([0-9])", r"\1\2", p))

    if "vendor_prefix" in variant_rules:
        # Vendor prefix: "hy4" -> "tencent hy4"
        for p in list(results):
            if not p.startswith(provider + " ") and p != provider:
                results.add(f"{provider} {p}")

    return sorted(results)


def build_catalog(models_path: Path, aliases_path: Path, base_catalog_path: Path) -> dict:
    models = json.loads(models_path.read_text())
    aliases = json.loads(aliases_path.read_text())
    base_catalog = json.loads(base_catalog_path.read_text()) if base_catalog_path.exists() else {}

    schema = base_catalog.get("schema", "hiqs.model-catalog/1")
    version = "1.3.0"
    updated = base_catalog.get("updated", "2026-09-08")
    sources = base_catalog.get("sources", [])

    rows = []
    seen = set()

    for item in aliases:
        model_key = item["model"]
        if model_key not in models:
            raise ValueError(f"Unknown model key {model_key!r} in {aliases_path}")
        model = models[model_key]
        provider = model["provider"]
        status = model.get("status", "ga")

        targets = item.get("targets") or [item["target"]]
        base_match = item["match"]
        variant_rules = item.get("variants", [])

        expanded_matches = generate_variants(base_match, provider, variant_rules) if variant_rules else [base_match]

        for target in targets:
            if target not in model["targets"]:
                raise ValueError(f"Model {model_key!r} does not have target {target!r}")
            t_info = model["targets"][target]
            replace_id = t_info["id"]
            source = t_info["source"]
            verified_on = t_info.get("verified_on")
            flags = t_info.get("flags", [])

            for m in expanded_matches:
                k = (m, target)
                if k in seen:
                    continue
                seen.add(k)
                rows.append({
                    "match": m,
                    "replace": replace_id,
                    "target": target,
                    "provider": provider,
                    "status": status,
                    "source": source,
                    "verified_on": verified_on,
                    "flags": flags,
                })

    return {
        "schema": schema,
        "version": version,
        "updated": updated,
        "sources": sources,
        "aliases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check that data/catalog.json is in sync with models/aliases")
    parser.add_argument("--models", type=Path, default=ROOT / "data" / "models.json")
    parser.add_argument("--aliases", type=Path, default=ROOT / "data" / "aliases.json")
    parser.add_argument("--catalog", type=Path, default=ROOT / "data" / "catalog.json")
    args = parser.parse_args()

    try:
        compiled = build_catalog(args.models, args.aliases, args.catalog)
    except Exception as exc:
        print(f"FAIL: generation error: {exc}", file=sys.stderr)
        return 1

    formatted = json.dumps(compiled, indent=2) + "\n"

    if args.check:
        if not args.catalog.exists():
            print(f"FAIL: {args.catalog} does not exist", file=sys.stderr)
            return 1
        current = args.catalog.read_text()
        if current != formatted:
            print("FAIL: data/catalog.json is out of sync with data/models.json and data/aliases.json.", file=sys.stderr)
            print("Run: python3 scripts/generate_catalog.py", file=sys.stderr)
            return 1
        print(f"OK: data/catalog.json is in sync ({len(compiled["aliases"])} rows, v{compiled["version"]})")
        return 0

    args.catalog.write_text(formatted)
    print(f"Generated {args.catalog}: {len(compiled["aliases"])} rows, version {compiled["version"]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
