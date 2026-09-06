/**
 * Demo runner for the Model-catalog reference consumer.
 * Run: npx tsx examples/typescript/demo.ts
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadCatalog, Resolver } from "./resolve.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const catalogPath = path.join(here, "..", "..", "data", "catalog.json");
const native = new Resolver(loadCatalog(catalogPath), "native");
const openrouter = new Resolver(loadCatalog(catalogPath), "openrouter");

const cases: Array<[string, Resolver]> = [
  ["ChatGPT", native],                  // case-folding + vendor-default pin
  ["gemini pro", native],               // FLAGGED row still resolves (advisory)
  ["deepseek v4 pro", openrouter],      // plain hit
  ["z-ai/glm-5.2", openrouter],         // exact ID -> misses table -> passthrough
  ["totally unknown model", native],    // miss -> passthrough, no default
];

for (const [query, resolver] of cases) {
  const r = resolver.resolve(query);
  if (r.resolved) {
    const note = r.flags.length ? ` flags=[${r.flags.join(", ")}]` : "";
    console.log(`resolved  ${JSON.stringify(query).padEnd(26)} -> ${r.modelId}  (tier=${r.matchedOn}, catalog v${r.catalogVersion}${note})`);
  } else {
    console.log(`passthru  ${JSON.stringify(query).padEnd(26)} -> unresolved; caller validates or refuses (catalog v${r.catalogVersion})`);
  }
}

// Contract assertions — the reference behavior in three lines.
console.assert(native.resolve("gemini pro").modelId === "gemini-2.5-pro", "flags must not block");
console.assert(native.resolve("totally unknown model").resolved === false, "no default on miss");
console.assert(openrouter.resolve("z-ai/glm-5.2").resolved === false, "exact IDs pass through");
console.log("all contract assertions held");
