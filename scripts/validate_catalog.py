#!/usr/bin/env python3
"""Validate data/catalog.json against the hiqs.model-catalog/1 schema rules.

Exits 0 with a row-count summary, or non-zero naming the first violation.
The point of this file is that the schema rules in PROJECT.md are CHECKED, not
prose: uniqueness under both consumers' normalizations, vocabulary limits,
bare-word GA stability, and the flagged-rows-carry-no-verify-date rule all fail loudly here.
"""
import datetime
import json
import re
import sys
from pathlib import Path

TARGETS = {"native", "openrouter"}
FLAGS = {"unverified-generation", "disputed"}
STATUSES = {"ga", "preview", "deprecated"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Recognized colloquial vendor names that must adhere to the "bare vendor word = GA model" policy
KNOWN_VENDOR_BRANDS = {
    "anthropic", "claude", "google", "gemini", "openai", "open ai", "gpt",
    "chatgpt", "chat gpt", "tencent", "hunyuan", "deepseek", "nvidia", "qwen",
    "x-ai", "grok", "z-ai", "glm", "meta", "muse", "spark"
}


def norm_ws(s: str) -> str:
    """Sleuth-side normalization: lower-case, whitespace-collapsed."""
    return " ".join(s.lower().split())


def norm_punct(s: str) -> str:
    """XYZ-side normalization: lower-case, ALL non-alphanumerics stripped (the resolver's squash)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> int:
    path = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
    try:
        catalog = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read {path}: {exc}")
        return 1

    def fail(msg: str) -> int:
        print(f"FAIL: {msg}")
        return 1

    if catalog.get("schema") != "hiqs.model-catalog/1":
        return fail(f"schema field must be 'hiqs.model-catalog/1', got {catalog.get('schema')!r}")
    if not re.match(r"^\d+\.\d+\.\d+$", str(catalog.get("version", ""))):
        return fail(f"version must be semver, got {catalog.get('version')!r}")
    if not DATE.match(str(catalog.get("updated", ""))):
        return fail(f"updated must be YYYY-MM-DD, got {catalog.get('updated')!r}")
    try:
        datetime.date.fromisoformat(str(catalog["updated"]))  # shape alone admits 2026-13-99
    except ValueError:
        return fail(f"updated {catalog.get('updated')!r} is not a real calendar date")

    rows = catalog.get("aliases")
    if not isinstance(rows, list) or not rows:
        return fail("aliases must be a non-empty list")

    seen_ws: dict = {}
    seen_punct: dict = {}
    for i, r in enumerate(rows):
        where = f"row {i} ({r.get('match')!r})"
        for field in ("match", "replace", "provider", "source", "target"):
            if not isinstance(r.get(field), str) or not r[field].strip():
                return fail(f"{where}: required field {field!r} missing or empty")
        if r["target"] not in TARGETS:
            return fail(f"{where}: target {r['target']!r} not in {sorted(TARGETS)}")
        if "status" in r and r["status"] not in STATUSES:
            return fail(f"{where}: status {r['status']!r} not in {sorted(STATUSES)}")
        flags = r.get("flags", [])
        if not isinstance(flags, list) or not set(flags) <= FLAGS:
            return fail(f"{where}: flags {flags!r} not a subset of {sorted(FLAGS)}")
        vo = r.get("verified_on")
        if vo is not None:
            if not DATE.match(vo):
                return fail(f"{where}: verified_on {vo!r} must be null or YYYY-MM-DD")
            try:
                datetime.date.fromisoformat(vo)  # catches 2026-13-99 — right shape, not a date
            except ValueError:
                return fail(f"{where}: verified_on {vo!r} is not a real calendar date")
        if flags and vo:
            return fail(f"{where}: flagged row ({flags}) must carry verified_on: null, not {vo!r}")
        if vo is None and "verified_on" not in r:
            return fail(f"{where}: verified_on key must be present (null when unverified)")

        # Bare-word GA stability gate (Issue #3 Item 2 & Issue #4):
        # A bare vendor or provider brand alias must not resolve to a preview model.
        is_bare_vendor = (
            r["match"] in KNOWN_VENDOR_BRANDS
            or r["match"] == r["provider"]
            or norm_punct(r["match"]) == norm_punct(r["provider"])
        )
        if is_bare_vendor and r.get("status") == "preview":
            return fail(
                f"{where}: bare vendor alias {r['match']!r} must not resolve to a preview model "
                f"({r['replace']!r}) — see README bare-word convention and Issue #4"
            )

        kw = (norm_ws(r["match"]), r["target"])
        if kw in seen_ws:
            return fail(
                f"{where}: whole-phrase collision with row {seen_ws[kw]['match']!r} "
                f"for target {r['target']!r} (match keys must be unique per target)"
            )
        else:
            seen_ws[kw] = r
        kp = (norm_punct(r["match"]), r["target"])
        if kp in seen_punct:
            prev = seen_punct[kp]
            if prev["replace"] != r["replace"]:
                return fail(
                    f"{where}: punctuation-fold collision with row {prev['match']!r} "
                    f"({prev['replace']!r} vs {r['replace']!r}) for target {r['target']!r}"
                )
        else:
            seen_punct[kp] = r

    by_target = {}
    for r in rows:
        by_target[r["target"]] = by_target.get(r["target"], 0) + 1
    print(f"OK: {len(rows)} rows ({', '.join(f'{v} {k}' for k, v in sorted(by_target.items()))}), "
          f"version {catalog['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
