# Model-catalog

One versioned catalog of **model alias pins** — the colloquial names operators say ("chatgpt",
"deepseek v4 pro", "sonnet") mapped to the exact model IDs systems should use — shared by every
HiQS Labs resolver instead of maintained per-repo.

Consumed today (or planned) by:

- **XYZ-forge** — `resolve-model-alias.sh` / `resolve-profile.sh` (GH-346 Phase 3a) via the
  `target: "openrouter"` rows.
- **AEGIS-Sleuth-Slackbot** — the GH-168 model alias resolver via the `target: "native"` rows.

Canonical plan: [PROJECT.md](PROJECT.md) · canonical issue: [#1](https://github.com/HiQS-Labs/Model-catalog/issues/1).

## What this repo is NOT

A service, a gateway, or a runtime network dependency. There is no server and there is no live
lookup. Consumers **vendor or pin a copy** of `data/catalog.json` and read it as a local file;
the only network call in a consumer is its own post-resolution validation against its provider
catalog, which is not this repo's concern.

## The catalog

[`data/catalog.json`](data/catalog.json) — one row per alias:

| Field | Meaning |
|---|---|
| `match` | The colloquial form, lower-cased, as the source table authored it. Spelling variants (`gpt 5.5` / `gpt5.5`) are intentionally separate rows — consumers normalize differently. |
| `replace` | The pinned model ID. Never a default the resolver invents. |
| `target` | Which ID space `replace` lives in: `native` (provider-native) or `openrouter` (OpenRouter slug). Consumers filter on this. |
| `provider` | Owning provider of `replace`. |
| `source` | Where the pin came from — file + issue/PR/URL. Every row names its provenance. |
| `verified_on` | Last date the pin was checked against a live catalog. `null` = unverified, stated honestly. |
| `flags` | Machine-readable caveats: `unverified-generation`, `disputed`. |

### Consumer contract

1. Entire-value or consumer-normalized lookup — **never substring substitution**.
2. Lookup miss → pass the value through unresolved to your normal validation; refusal is the
   terminal state (unresolved **and** invalid), never a default.
3. No network at resolution time.
4. Record which catalog version resolved a turn (provenance).
5. Exact model IDs are never declared keys, so they always pass through untouched.

## Changing the catalog

1. PR a row here (all fields, honest `source`; verify against the provider's first-party model
   page if you can and set `verified_on`).
2. CI validates the schema rules (`scripts/validate_catalog.py`): uniqueness under both
   consumers' normalizations, vocabulary limits, flagged rows carry no verify date.
3. A maintainer bumps `version` and tags; each consumer then PRs its own pin-bump/sync. Two PRs
   of friction is the deliberate price of pinned provenance — see PROJECT.md → Governance.

## Versioning

Semver on a data file, judged by what the change does to resolution:

- **MAJOR** — reader-contract change: schema fields, vocabulary removal, rule changes, row removal
  (a previously-resolving alias can now miss).
- **MINOR** — any other resolution-affecting change: rows added, `replace`/`target`/`flags` changed
  (corrections included).
- **PATCH** — provenance-only metadata (`source`, `verified_on`): zero resolution change.

Every release is git-tagged; consumers pin an **exact** version and record it with each resolution.

## License

**TBD — operator decision, currently the standing Phase 0 blocker** (a data-only public repo with
no license is legally unvendorable by its consumers; see PROJECT.md → Governance). Proposal on the
table: CC0-1.0 for the data, MIT for `scripts/`.

## Status

Phase 0 (this catalog, v1.0.0) — merged from XYZ-forge's `openrouter-model-aliases.yml` (7 rows)
and AEGIS-Sleuth's `command-normalization.json` `ModelAliases` (53 rows). Phases 1–2 (consumer
integration) are planned in [PROJECT.md](PROJECT.md); the gateway/service conversation is parked
there on purpose.

## Security

This repo holds **data only**: model names, IDs, providers, dates, source links. Never commit
API keys, tokens, or credentials — pins are verified against provider catalogs out-of-band, and
`verified_on` attests that check without storing any secret.
