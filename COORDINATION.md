---
title: Coordination map — Model-catalog across HiQS-Labs repos
status: Current (2026-09-05)
maintainer: noel
---

# Coordination map

One page answering "what exists, where, what's next" for the Model-catalog project. If this page
and a repo disagree, the repo's own tracker wins — then fix this page.

## The artifact graph

| Artifact | Where | State |
|---|---|---|
| Artifact | Where | State |
|---|---|---|
| Umbrella tracker (Phases 0–3) | [Model-catalog#1](https://github.com/HiQS-Labs/Model-catalog/issues/1) | Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3 parked |
| Authoritative plan | [PROJECT.md](PROJECT.md) (this repo) | Reviewed — plan QA ×2 + coordination ×4 relay cycles folded |
| Catalog data v1.2.0 | [data/catalog.json](data/catalog.json) | 66 rows (57 native / 9 openrouter) — generated from `models.json` + `aliases.json` |
| Catalog source entities | [data/models.json](data/models.json) | 21 canonical models with `status: "ga"\|"preview"\|"deprecated"` |
| Alias declarations & variants | [data/aliases.json](data/aliases.json) | 64 declarations with deterministic variant rules |
| Catalog generator | [scripts/generate_catalog.py](scripts/generate_catalog.py) | Compiles `models.json` + `aliases.json` $\rightarrow$ `catalog.json`; CI `--check` |
| Schema validator | [scripts/validate_catalog.py](scripts/validate_catalog.py) | Uniqueness, dates, vocabulary, bare-word GA stability gate |
| Provider verification probe | [scripts/verify_providers.py](scripts/verify_providers.py) | Scheduled probe measuring `verified_on` freshness and live OpenRouter status |
| OpenRouter YAML renderer | [scripts/render_openrouter.py](scripts/render_openrouter.py) | Deterministic (squash-length desc, then lex); XYZ #450 consumes it |
| CI | [.github/workflows/catalog-validate.yml](.github/workflows/catalog-validate.yml) | Generator sync + validator + renderer smoke + version-bump enforcement |
| Scheduled CI | [.github/workflows/catalog-verify.yml](.github/workflows/catalog-verify.yml) | Weekly provider catalog drift probe (report-only) |
| Release tags | `v1.0.0`, `v1.1.0`, `v1.2.0` | `v1.0.0` Phase 0; `v1.1.0` Hy4 preview; `v1.2.0` generator & bare-word GA gate |
| License | [LICENSE](LICENSE) (MIT, code/docs) · [data/LICENSE](data/LICENSE) (CC0-1.0, data) | Decided 2026-09-05 |
| **Phase 1 build-out (XYZ-forge)** | [XYZ-forge#450](https://github.com/HiQS-Labs/XYZ-forge/issues/450) → [PR #456](https://github.com/HiQS-Labs/XYZ-forge/pull/456) | ✅ Merged (`b282aa7c`) — live on `development` |
| **Phase 2 build-out (AEGIS-Sleuth)** | [AEGIS-Sleuth#173](https://github.com/HiQS-Labs/AEGIS-Sleuth-Slackbot/issues/173) → [PR #180](https://github.com/HiQS-Labs/AEGIS-Sleuth-Slackbot/pull/180) | ✅ Merged & deployed to production (`4b192c76`) |
| **Generator evolution & Tier 4 retirement** | [Model-catalog#3](https://github.com/HiQS-Labs/Model-catalog/issues/3) / [XYZ-forge#457](https://github.com/HiQS-Labs/XYZ-forge/issues/457) | Landed in `v1.2.0`: generator in CI, bare-word GA gate, Tier 4 retired |
| Sleuth planning thread | [AEGIS-Sleuth-Slackbot#171](https://github.com/HiQS-Labs/AEGIS-Sleuth-Slackbot/issues/171) (+ #168 resolver, closed completed) | Open |
| Adjacent defect: dsh default-model | [XYZ-forge#448](https://github.com/HiQS-Labs/XYZ-forge/issues/448) → **[PR #449](https://github.com/HiQS-Labs/XYZ-forge/pull/449)** | PR open, CI green, awaiting review/merge |
| Relay QA raw blocks | XYZ-forge `relay-system/2026-09-05/model-catalog-plan-qa-{agy,qwen}.md` (commit `a90c4df5`, local until next development push) | Committed |

## Decisions already made (do not re-litigate)

1. **Data-only repo — no service, no gateway** (PROJECT.md → Decision record; gateway is Phase 3,
   parked until a concrete routing/auth need).
2. **Consumers vendor/pin copies; no runtime network.** Two-PR change flow (row here, sync PR per
   consumer) is deliberate.
3. **Compile-to-legacy-shape integration** on both sides: XYZ renders the legacy YAML (resolver
   untouched); Sleuth build-time-syncs `ModelAliases` rows into `command-normalization.json`
   (loader untouched). Resolvers never parse the catalog directly.
4. **Contract:** entire-value/consumer-normalized lookup only; miss → pass-through → validate →
   refuse (never default); no network at resolution; exact pinned version recorded per turn;
   flags advisory (flagged rows resolve normally); exact IDs always win.
5. **License:** CC0-1.0 data / MIT code+docs.

## Next steps (in order)

1. **XYZ-forge:** review + merge [PR #449](https://github.com/HiQS-Labs/XYZ-forge/pull/449)
   (GH-448). Independent of Phase 1, but every dsh lane run before it lands records the wrong
   executed model in telemetry.
2. **XYZ-forge:** execute #450 (Phase 1) — vendor the `v1.0.0` tag, render the YAML with
   `scripts/render_openrouter.py` (shipped here at the pinned tag), wire the drift check + tier-4
   guard test + telemetry version. Accept criteria in the issue and PROJECT.md Phase 1.
3. **AEGIS-Sleuth:** execute #173 (Phase 2) — build-time sync of native rows + provenance-aware
   `run-diagnostics` pin audit. The resolver itself already shipped (#168); this only changes its
   table input.
4. **Both consumers:** after first sync, record catalog version in resolution provenance; then
   future model additions are: PR row here → tag → per-consumer sync PR.
5. **Parked:** gateway/service (Phase 3) — revisit only on a concrete routing/auth/failover need.

_(Coordination relay r3 B1–B3 resolved 2026-09-05: `v1.0.0` tagged, CI wired, renderer shipped —
the review's three blockers are closed in the same pass as this line.)_

## Known loose ends

- XYZ-forge relay evidence (`a90c4df5`) is on local `development` — resolves on the next push.
  Until then, comments linking it name the path + SHA.
- Historical dsh telemetry rows (pre-#449-merge) attribute `DEEPSEEK_MODEL` as executed when the
  executed model was the bundle default (`deepseek-v4-flash`).
- Harness vocabulary drift (XYZ-forge): `/relay` docs say verdicts Approved/Changes requested/Blocked,
  but `bin/validate-relay-block` only accepts `VERDICT: PASS|FAIL|PARKED` plus a `Basis:` line —
  two reviewer turns failed exit-8 on exactly this before the mapping was known. Worth a docs fix.

## Contribution flow (the standing answer to "how do I add a model?")

1. PR a row to `data/catalog.json` **with `version` + `updated` bumped in the same PR** (all
   fields; `source` = first-party provider URL; set `verified_on` only with real verification;
   flag genuinely-questionable rows). CI rejects a catalog PR that skips the bump; MAJOR/MINOR/
   PATCH per PROJECT.md → Versioning.
2. CI validates (uniqueness under both normalizations, tier-4 capture, vocabulary, dates, bump).
3. Maintainer reviews and tags the release.
4. Per consumer: a small sync PR (XYZ re-renders YAML; Sleuth re-syncs `ModelAliases`).
