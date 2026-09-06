# Sample consumers

Three minimal reference harnesses — same semantics, three languages. Each is a
**starter to copy into your project**, not a library to depend on: vendor
`data/catalog.json` at a pinned tag and point the loader at YOUR copy.

| Language | File | Run |
|---|---|---|
| Python (stdlib only) | [`python/model_catalog.py`](python/model_catalog.py) | `python3 examples/python/model_catalog.py` |
| TypeScript (Node) | [`typescript/resolve.ts`](typescript/resolve.ts) + [`demo.ts`](typescript/demo.ts) | `npx tsx examples/typescript/demo.ts` |
| Rust (serde_json) | [`rust/src/main.rs`](rust/src/main.rs) | `cargo run --manifest-path examples/rust/Cargo.toml` |

Every sample demonstrates the binding consumer contract (PROJECT.md → Consumer contract):

- **Entire-value lookup only** — two normalization tiers (case+whitespace "phrase", then
  alphanumeric "squash"); never substring substitution.
- **Miss = passthrough** — the resolver returns "unresolved" and your code validates the raw
  value against your provider catalog or refuses. No defaults, ever.
- **Exact IDs pass through** — they are never declared keys, so they miss the table untouched.
- **Flags are advisory** — the flagged `gemini pro` row resolves normally with
  `flags=["unverified-generation"]` surfaced for logging/diagnostics.
- **Provenance** — every resolution names the catalog version that produced it.

Filter by `target`: `"native"` (provider-native IDs — the AEGIS-Sleuth space) or
`"openrouter"` (OpenRouter slugs — the XYZ-forge space). Never mix.
