/**
 * Reference consumer for HiQS-Labs/Model-catalog (TypeScript, zero runtime deps).
 *
 * STARTER, not a library: vendor data/catalog.json at a pinned tag into your own
 * repo and read YOUR copy — never this repo, never the network.
 *
 * Consumer contract demonstrated (PROJECT.md -> Consumer contract):
 *   1. Entire-value lookup only — never substring substitution.
 *   2. Miss -> pass through UNRESOLVED to your own validation; refusal is terminal
 *      (unresolved AND invalid), never a default.
 *   3. No network at resolution time.
 *   4. Report which catalog version resolved each turn.
 *   5. Exact model IDs are never keys, so they miss the table and pass through.
 *   6. Flags are advisory: flagged rows resolve normally; you log/surface them.
 *
 * Run: npx tsx examples/typescript/demo.ts
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const EXPECTED_SCHEMA = "hiqs.model-catalog/1";
export type Target = "native" | "openrouter";

export interface CatalogRow {
  match: string;
  replace: string;
  target: Target;
  provider: string;
  source: string;
  verified_on: string | null;
  flags: string[];
}

export interface Catalog {
  schema: string;
  version: string;
  updated: string;
  aliases: CatalogRow[];
}

export interface Resolution {
  query: string;
  resolved: boolean; // false = passthrough; caller still owes validation
  modelId?: string;
  provider?: string;
  flags: string[];
  matchedOn?: "phrase" | "squash";
  catalogVersion: string;
}

const phrase = (s: string): string => s.toLowerCase().trim().split(/\s+/).join(" ");
const squash = (s: string): string => s.toLowerCase().replace(/[^a-z0-9]/g, "");

export function loadCatalog(p: string): Catalog {
  const catalog = JSON.parse(readFileSync(p, "utf8")) as Catalog;
  if (catalog.schema !== EXPECTED_SCHEMA) {
    throw new Error(`unsupported catalog schema: ${catalog.schema}`);
  }
  return catalog;
}

export class Resolver {
  readonly version: string;
  readonly #byPhrase: Map<string, CatalogRow>;
  readonly #bySquash: Map<string, CatalogRow>;

  constructor(catalog: Catalog, readonly target: Target) {
    if (target !== "native" && target !== "openrouter") {
      throw new Error(`target must be native|openrouter, got ${target}`);
    }
    this.version = catalog.version;
    this.#byPhrase = new Map();
    this.#bySquash = new Map();
    for (const row of catalog.aliases) {
      if (row.target !== target) continue;
      this.#byPhrase.set(phrase(row.match), row);
      this.#bySquash.set(squash(row.match), row);
    }
  }

  resolve(query: string): Resolution {
    const base: Resolution = { query, resolved: false, flags: [], catalogVersion: this.version };
    if (!query.trim()) return base;
    for (const [matchedOn, key, table] of [
      ["phrase", phrase(query), this.#byPhrase],
      ["squash", squash(query), this.#bySquash],
    ] as const) {
      const row = table.get(key);
      if (row) {
        return {
          ...base, resolved: true, modelId: row.replace, provider: row.provider,
          flags: row.flags ?? [], matchedOn,
        };
      }
    }
    // Miss = passthrough. No default, ever — the caller validates or refuses.
    return base;
  }
}
