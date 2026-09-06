//! Reference consumer for HiQS-Labs/Model-catalog (Rust, serde_json only).
//!
//! STARTER, not a library: vendor data/catalog.json at a pinned tag into your own
//! repo and read YOUR copy — never this repo, never the network.
//!
//! Consumer contract demonstrated (PROJECT.md -> Consumer contract):
//!   1. Entire-value lookup only — never substring substitution.
//!   2. Miss -> pass through UNRESOLVED to your own validation; refusal is
//!      terminal (unresolved AND invalid), never a default.
//!   3. No network at resolution time.
//!   4. Report which catalog version resolved each turn.
//!   5. Exact model IDs are never keys, so they miss the table and pass through.
//!   6. Flags are advisory: flagged rows resolve normally; you log/surface them.
//!
//! Run: cargo run --manifest-path examples/rust/Cargo.toml

use serde::Deserialize;
use std::collections::HashMap;
use std::path::Path;

const EXPECTED_SCHEMA: &str = "hiqs.model-catalog/1";

#[derive(Deserialize)]
struct Catalog {
    schema: String,
    version: String,
    aliases: Vec<CatalogRow>,
}

#[derive(Deserialize, Clone)]
struct CatalogRow {
    #[serde(rename = "match")]
    match_: String,
    replace: String,
    target: Target,
    provider: String,
    #[serde(default)]
    flags: Vec<String>,
}

#[derive(Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
enum Target {
    Native,
    Openrouter,
}

#[derive(Debug)]
struct Resolution {
    resolved: bool, // false = passthrough; caller still owes validation
    model_id: String,
    provider: String,
    flags: Vec<String>,
    matched_on: &'static str,
    catalog_version: String,
}

fn phrase(s: &str) -> String {
    // Tier 1: case-fold + whitespace collapse (Sleuth-style whole-phrase).
    s.to_lowercase().split_whitespace().collect::<Vec<_>>().join(" ")
}

fn squash(s: &str) -> String {
    // Tier 2: alphanumerics only (XYZ-style squash). Entire-value still.
    s.chars().filter(|c| c.is_ascii_alphanumeric()).collect()
}

struct Resolver {
    version: String,
    by_phrase: HashMap<String, CatalogRow>,
    by_squash: HashMap<String, CatalogRow>,
}

impl Resolver {
    fn new(catalog: &Catalog, target: Target) -> Self {
        let mut by_phrase = HashMap::new();
        let mut by_squash = HashMap::new();
        for row in &catalog.aliases {
            if row.target != target {
                continue;
            }
            by_phrase.entry(phrase(&row.match_)).or_insert_with(|| row.clone());
            by_squash.entry(squash(&row.match_)).or_insert_with(|| row.clone());
        }
        Resolver { version: catalog.version.clone(), by_phrase, by_squash }
    }

    fn resolve(&self, query: &str) -> Resolution {
        let miss = Resolution {
            resolved: false,
            model_id: String::new(),
            provider: String::new(),
            flags: vec![],
            matched_on: "",
            catalog_version: self.version.clone(),
        };
        if query.trim().is_empty() {
            return miss;
        }
        for (matched_on, key, table) in [
            ("phrase", phrase(query), &self.by_phrase),
            ("squash", squash(query), &self.by_squash),
        ] {
            if let Some(row) = table.get(&key) {
                return Resolution {
                    resolved: true,
                    model_id: row.replace.clone(),
                    provider: row.provider.clone(),
                    flags: row.flags.clone(),
                    matched_on,
                    catalog_version: self.version.clone(),
                };
            }
        }
        // Miss = passthrough. No default, ever — the caller validates or refuses.
        miss
    }
}

fn main() {
    // Optional catalog path arg; default = this repo's data/ (starter convenience —
    // real consumers vendor their pinned copy and point at THAT).
    let args: Vec<String> = std::env::args().collect();
    let path = args.get(1).map(String::as_str).unwrap_or("data/catalog.json");
    let raw = std::fs::read_to_string(Path::new(path)).expect("catalog.json not found");
    let catalog: Catalog = serde_json::from_str(&raw).expect("invalid catalog JSON");
    assert_eq!(catalog.schema, EXPECTED_SCHEMA, "unsupported catalog schema");

    let native = Resolver::new(&catalog, Target::Native);
    let openrouter = Resolver::new(&catalog, Target::Openrouter);

    let cases: Vec<(&str, &Resolver)> = vec![
        ("ChatGPT", &native),                 // case-folding + vendor-default pin
        ("gemini pro", &native),              // FLAGGED row still resolves (advisory)
        ("deepseek v4 pro", &openrouter),     // plain hit
        ("z-ai/glm-5.2", &openrouter),        // exact ID -> misses table -> passthrough
        ("totally unknown model", &native),   // miss -> passthrough, no default
    ];
    for (query, resolver) in cases {
        let r = resolver.resolve(query);
        if r.resolved {
            let note = if r.flags.is_empty() {
                String::new()
            } else {
                format!(" flags={:?}", r.flags)
            };
            println!(
                "resolved  {:<26} -> {} [{}]  (tier={}, catalog v{}{})",
                format!("{query:?}"),
                r.model_id,
                r.provider,
                r.matched_on,
                r.catalog_version,
                note
            );
        } else {
            println!(
                "passthru  {:<26} -> unresolved; caller validates or refuses (catalog v{})",
                format!("{query:?}"),
                r.catalog_version
            );
        }
    }

    // Contract assertions — the reference behavior in three lines.
    assert_eq!(native.resolve("gemini pro").model_id, "gemini-2.5-pro"); // flags don't block
    assert!(!native.resolve("totally unknown model").resolved); // no default
    assert!(!openrouter.resolve("z-ai/glm-5.2").resolved); // exact IDs pass through
    println!("all contract assertions held");
}
