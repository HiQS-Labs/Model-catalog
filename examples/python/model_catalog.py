#!/usr/bin/env python3
"""Reference consumer for HiQS-Labs/Model-catalog (Python, stdlib only).

This is a STARTER, not a library to depend on: vendor data/catalog.json at a pinned
tag into your own repo and read YOUR copy — never this repo, never the network.

It demonstrates the binding consumer contract (PROJECT.md -> Consumer contract):
  1. Entire-value lookup only — never substring substitution.
  2. Lookup miss -> pass through UNRESOLVED to your own validation; refusal is
     terminal (unresolved AND invalid), never a default.
  3. No network at resolution time.
  4. Report which catalog version resolved each turn.
  5. Exact model IDs are never keys, so they miss the table and pass through.
  6. Flags are advisory: flagged rows resolve normally; you log/surface them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

EXPECTED_SCHEMA = "hiqs.model-catalog/1"


@dataclass(frozen=True)
class Resolution:
    query: str
    resolved: bool              # False = passthrough; caller still owes validation
    model_id: str = ""
    provider: str = ""
    flags: tuple[str, ...] = ()
    matched_on: str = ""        # which normalization tier hit: phrase|squash
    catalog_version: str = ""


def load_catalog(path: str | Path) -> dict:
    catalog = json.loads(Path(path).read_text())
    if catalog.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"unsupported catalog schema: {catalog.get('schema')!r}")
    return catalog


def _phrase(s: str) -> str:
    """Tier 1: case-fold + whitespace collapse (Sleuth-style whole-phrase)."""
    return " ".join(s.casefold().split())


def _squash(s: str) -> str:
    """Tier 2: alphanumerics only (XYZ-style squash). Last resort, entire-value still."""
    return re.sub(r"[^a-z0-9]", "", s.casefold())


class Resolver:
    """Entire-value lookup over one target ID space ("native" or "openrouter")."""

    def __init__(self, catalog: dict, target: str):
        if target not in ("native", "openrouter"):
            raise ValueError(f"target must be native|openrouter, got {target!r}")
        self.version = catalog["version"]
        self.by_phrase: dict[str, dict] = {}
        self.by_squash: dict[str, dict] = {}
        for row in catalog["aliases"]:
            if row["target"] != target:
                continue
            self.by_phrase.setdefault(_phrase(row["match"]), row)
            self.by_squash.setdefault(_squash(row["match"]), row)

    def resolve(self, query: str) -> Resolution:
        if not query.strip():
            return Resolution(query=query, resolved=False, catalog_version=self.version)
        for tier, key in (("phrase", _phrase(query)), ("squash", _squash(query))):
            row = (self.by_phrase if tier == "phrase" else self.by_squash).get(key)
            if row:
                return Resolution(
                    query=query, resolved=True, model_id=row["replace"],
                    provider=row["provider"], flags=tuple(row.get("flags", ())),
                    matched_on=tier, catalog_version=self.version,
                )
        # Miss = passthrough. No default, ever — the caller validates or refuses.
        return Resolution(query=query, resolved=False, catalog_version=self.version)


def _demo() -> int:
    catalog_path = Path(__file__).resolve().parents[2] / "data" / "catalog.json"
    native = Resolver(load_catalog(catalog_path), target="native")
    openrouter = Resolver(load_catalog(catalog_path), target="openrouter")

    cases = [
        ("ChatGPT", native),                    # case-folding + vendor-default pin
        ("gemini pro", native),                 # FLAGGED row still resolves (advisory)
        ("deepseek v4 pro", openrouter),        # plain hit
        ("z-ai/glm-5.2", openrouter),           # exact ID -> misses table -> passthrough
        ("totally unknown model", native),      # miss -> passthrough, no default
    ]
    for query, resolver in cases:
        r = resolver.resolve(query)
        if r.resolved:
            note = f" flags={list(r.flags)}" if r.flags else ""
            print(f"resolved  {query!r:26} -> {r.model_id}  "
                  f"(tier={r.matched_on}, catalog v{r.catalog_version}{note})")
        else:
            print(f"passthru  {query!r:26} -> unresolved; caller validates "
                  f"{query!r} or refuses (catalog v{r.catalog_version})")

    # Contract assertions — the reference behavior in three lines.
    assert native.resolve("gemini pro").model_id == "gemini-2.5-pro"           # flags don't block
    assert native.resolve("totally unknown model").resolved is False            # no default
    assert openrouter.resolve("z-ai/glm-5.2").resolved is False                 # exact ID untouched
    print("all contract assertions held")
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
