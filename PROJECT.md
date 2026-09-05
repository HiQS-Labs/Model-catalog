---
gh_issue: 1
source: https://github.com/HiQS-Labs/Model-catalog/issues/1
title: "Model-catalog — one versioned alias/pin catalog feeding the XYZ-forge and AEGIS-Sleuth resolvers"
status: Reviewed (2 relay rounds folded; Phases 1–2 ready to execute)
created: 2026-09-05
owner: noel
doc_type: plan
effort: 3
complexity: 2
risk: 2
phases: 4
related: "HiQS-Labs/XYZ-forge#346, HiQS-Labs/AEGIS-Sleuth-Slackbot#171, HiQS-Labs/AEGIS-Sleuth-Slackbot#168"
---

# Model-catalog — one versioned catalog, two local resolvers

## Problem

Three repos resolve "what model did the operator mean" today, with three disjoint mechanisms and
zero shared state:

1. **XYZ-forge** — `relay-automation/openrouter-model-aliases.yml`: 7 hand-maintained rows mapping
   colloquial names to **OpenRouter slugs** (`deepseek v4 pro` → `deepseek/deepseek-v4-pro`),
   consumed by `resolve-model-alias.sh` (fuzzy normalize + token-subset match) and
   `resolve-profile.sh` (GH-346 Phase 3a). Adding a row requires a hand-appended line **and** a
   hand-added test assertion in `test/model-alias.sh`.
2. **AEGIS-Sleuth** — `data/static/ai/command-normalization.json` → `ModelAliases`: 53
   entire-value pins mapping colloquial names/vendor words to **provider-native IDs**
   (`chatgpt` → `gpt-5.6-terra`, `sonnet` → `claude-sonnet-5`), seeded by an operator-supplied
   Perplexity pass (GH-168 Rev 4). Its GH-168 resolver **shipped 2026-09-05** (issue closed
   completed) and consumes this table with a refusal-on-unknown contract today.
3. **Nothing** records *when* a pin was last verified against a live catalog, or where it came
   from. The one known-stale row (`gemini pro` → `gemini-2.5-pro`, flagged in GH-168 Rev 4) is
   flagged only in a doc, not in the data.

The failure mode is drift: the same operator maintains the same kind of facts in two formats in two
repos, and a pin corrected in one stays wrong in the other.

## Decision record — what this repo IS and IS NOT

**Model-catalog IS:** a **data-only repo**. One versioned JSON catalog of model alias pins, with
provenance (`source`, `verified_on`) and a target-space tag. It is the single source of truth both
resolvers consume **as a local file**.

**Model-catalog IS NOT:** a service, a gateway, a proxy, or a runtime network dependency. There is
no server. Both consumers read a **vendored/pinned copy at their own deploy time**; nothing calls
out at model-resolution time. A gateway (routing/auth/failover) is explicitly out of scope until a
concrete need exists — see Phase 3.

Why not a service (decided 2026-09-05, XYZ-forge#346 + Sleuth#171 context):

- Both repos' recorded contracts are *static, entire-value, refusal-on-unknown*. A runtime service
  reintroduces the unverifiable-resolver behavior GH-168 exists to remove (Sleuth#171's own
  research rejected Portkey/Mastra-class gateways for exactly this reason).
- XYZ-forge measured alias resolution (GH-365 step 7) and concluded even *caching* was unwarranted
  — a network hop is strictly slower than reading a checked-in file, and adds a daemon failure mode
  to every sandboxed lane.
- Provenance requires immutability: "resolved by catalog vX.Y.Z" must name a committed, diffable
  artifact. A mutable service table destroys exactly that.

## Data model (v1)

`data/catalog.json`:

```json
{
  "schema": "hiqs.model-catalog/1",
  "version": "1.0.0",
  "updated": "2026-09-05",
  "aliases": [
    {
      "match": "deepseek v4 pro",
      "replace": "deepseek/deepseek-v4-pro",
      "target": "openrouter",
      "provider": "deepseek",
      "source": "XYZ-forge relay-automation/openrouter-model-aliases.yml (GH-120)",
      "verified_on": null,
      "flags": []
    },
    {
      "match": "sonnet",
      "replace": "claude-sonnet-5",
      "target": "native",
      "provider": "anthropic",
      "source": "AEGIS-Sleuth GH-168 rev4 operator pins (Perplexity pass over first-party pages)",
      "verified_on": "2026-09-04",
      "flags": []
    }
  ]
}
```

Field contract:

| Field | Required | Meaning |
|---|---|---|
| `match` | yes | The colloquial form, lower-cased. Matched **entire-value** by Sleuth; fuzzy-normalized by XYZ. Carried as authored by the source table. |
| `replace` | yes | The pinned ID. Never a default the resolver invents. |
| `target` | yes | Which ID space `replace` lives in: `native` (provider-native) or `openrouter` (OpenRouter slug). Consumers filter on this; an `openrouter` row must never resolve for a native-ID consumer and vice versa. |
| `provider` | yes | Owning provider of `replace` (openai, anthropic, google, deepseek, z-ai, nvidia, x-ai, qwen, stealth, …). |
| `source` | yes | Where the pin came from (file + issue/PR). Every row must name its provenance. |
| `verified_on` | no | Last date the pin was checked against a live catalog. Backfilled `2026-09-04` for the **31 rows whose `replace` is one of the six non-flagged Rev-4 pins** (six distinct first-party URLs, one per pinned ID); the flagged pin's rows (`gemini pro` / `gemini 2.5 pro` → `gemini-2.5-pro`) stay `null` per the flagged rule; the remaining **29 rows** (20 pre-GH-168 native + 7 XYZ openrouter) stay `null`. Rule: a dated row requires recorded per-ID evidence — a bulk pass qualifies only when each pinned ID carries its own source URL. (Coordination relay r3 S1 corrected this field's earlier "seven pins / 46 rows" arithmetic, which conflated pins with rows: v1.0.0 data = 31 dated / 29 null across 53 native + 7 openrouter.) A row flagged `unverified-generation` must have `verified_on: null` — a known-questionable pin claiming a verification date is false precision (relay QA r1); a row flagged `disputed` **keeps** its verify date, and the dispute date lives in the PR/commit history (relay QA r2 F11). |
| `flags` | no | Machine-readable caveats. v1 vocabulary: `unverified-generation` (carried but flagged for review, e.g. `gemini pro` → `gemini-2.5-pro`), `disputed` (two consumers disagree — see Governance; resolves per the row as it stands, contract item 6). |

Schema rules (enforced by this repo's CI, `scripts/validate_catalog.py`): valid JSON per schema;
`replace` non-empty; `target` in vocabulary; `flags` in vocabulary; every row has `source`.
Uniqueness holds **under each consumer's normalization, scoped to same-target rows** (relay QA r2
F2a: a cross-target fold pair is valid data no consumer ever sees together): under XYZ's squash
normalization (lower-case, all non-alphanumerics stripped) two rows may collide only if they share
the same `replace`; under Sleuth's whole-phrase normalization `(match, target)` is unique, full
stop. **Row order is behaviorally load-bearing** (relay QA r2 F2c: XYZ's resolver is file-order-wins
within tiers), so the renderer's output order is deterministic (squash-length of `match`
descending, then lexicographic) — this is also the determinism prerequisite for the byte-equality
drift check. Additional CI rule (relay QA r2 F2b, tier-4 capture, scoped to `openrouter` rows —
the only rows a substring-fallback consumer renders): for any two openrouter rows A, B where
squash(A.match) is a substring of squash(B.replace) and A.replace ≠ B.replace, CI fails (e.g. a
future `grok` row would let XYZ's tier 4 silently capture the exact-ID query `x-ai/grok-4.6`).
Residual case the data rule cannot see — a *pin correction* leaves old exact IDs capturable at
resolver level after the old replace has left the data — is an XYZ-side guard obligation, landed
as an explicit Phase 1 test. **Spelling-variant rows that differ only in punctuation/spacing are
intentionally kept** — consumers normalize differently, and the variants are how each finds its
hits.

## Consumer contract (binding on both resolvers)

1. **Entire-value or consumer-normalized lookup only — never substring substitution.** The catalog
   stores data; matching semantics stay consumer-owned (XYZ: normalize + token-subset;
   Sleuth: entire-value, GH-168 rev2/rev3 staged lookup). Consumer-side **case-folding of the
   lookup input is explicit** — `match` keys are lower-cased; "ChatGPT" resolves because the
   consumer folds case before lookup, not because the loader happens to (relay QA r2 F9).
2. **Lookup miss ≠ refusal.** A miss passes the value through **unresolved** to the consumer's
   normal validation path (live-catalog check); an exact ID is just a value that never needed the
   table. Refusal is the *terminal* state: an unresolved value that also fails validation is
   refused — never defaulted. Each consumer ships a negative control that observes the refusal.
3. **No network at resolution time.** Consumers read a vendored/pinned copy. (The consumer's own
   post-alias validation may hit its provider catalog — that is validation, not resolution.)
4. **Version pinning + provenance.** Each consumer records which catalog version resolved a turn
   (XYZ: `harnesses.db` invocation telemetry; Sleuth: `run-diagnostics` probe output).
5. **Exact IDs always win** — structurally for future rows via the tier-4 capture CI rule, and at
   the resolver for post-correction old IDs via the Phase 1 test obligation (F2b).
6. **Flagged rows resolve normally** (relay QA r2 F7): `flags` are advisory metadata — logged,
   surfaced in diagnostics — never terminal. Both consumers MUST NOT refuse a row merely for
   carrying `unverified-generation` or `disputed`; divergence on flag handling is the exact drift
   this repo exists to kill.

## Phases

### Phase 0 — catalog v1 lands here (this commit)

Merge XYZ's 7 OpenRouter rows + Sleuth's 53 native pins into `data/catalog.json` per the schema
above; dedupe on `(match, target)`; carry the flagged `gemini pro` row with
`flags: ["unverified-generation"]`; carry the documented `gpt` → `gpt-5.6-terra`
vendor-default-not-flagship deviation as data (a note in README), not silently.

- Accept: validation passes on the merged file; dedupe key is `(match, target)` — the same key
  arriving from both sources with **different** `replace` values lands as
  `flags: ["disputed"]` and the operator arbitrates before merge (relay QA r2 F10); row counts
  reconcile against both sources (7 + 53, no exact duplicates → **60 rows**, recorded in the PR);
  README + this doc + canonical issue exist; **no secrets, keys, or tokens in the tree** (public
  repo); **license decided** (relay QA r2 F8 — see Governance).

### Phase 1 — XYZ-forge consumes

1. Add a **sync/compile step** that renders `data/catalog.json`'s `target: "openrouter"` rows into
   the legacy `alias: slug` YAML at `relay-automation/openrouter-model-aliases.yml`, as a
   **generated file** (header: "generated from HiQS-Labs/Model-catalog vX.Y.Z — edit the catalog,
   not this file"). The renderer ships HERE: `scripts/render_openrouter.py` (coordination relay
   r3 B3 — it was previously assigned to this repo but untracked). Deterministic order: squash-length
   of `match` descending, then lexicographic. Decided shape (relay QA
   r2 F4): XYZ vendors `catalog.json` **byte-identical to the upstream tag** at
   `relay-automation/model-catalog/catalog.json` with a **pin record (tag + sha256)** beside it
   that CI verifies, closing the copy↔upstream edge no drift check can otherwise see; the drift
   check re-renders the committed YAML from the committed copy and demands byte equality.
2. **Leave `resolve-model-alias.sh` untouched** (relay QA r1: a Bash shim parsing JSON invites
   fragile hand-rolled parsing and GH-551 adjacency; the compile-to-YAML shape keeps the resolver,
   its callers, and the vendored `.xyz/` lifecycle exactly as they are). The GH-346
   caller-supplied-table seam (`c5831ff3`, `MODEL_ALIASES_FILE`) stays available for tests.
3. `test/model-alias.sh` keeps its **explicit, hand-written assertions driving the real resolver**
   (not assertions generated from the catalog — a test generated from its own input data is a
   tautology). What IS generated: the YAML artifact, plus the CI drift check above. New obligation
   (relay QA r2 F2b residual): an explicit test pinning what tier 4 does when a query is itself an
   exact-ID form that contains a row match (the post-pin-correction redirection scenario) — the
   guard lives in the resolver's test contract, not in data.
4. `profile_resolve.py` / invocation telemetry records the catalog version (read from the vendored
   copy's `version` field).

- Accept: green `validate.sh` on the PR; a stale-pin scenario (flip a row in the vendored copy) is
  caught by the CI drift check (render ≠ committed YAML), while the hand-written resolver
  assertions still drive the real resolver (relay QA r2 F3); refusal contract negative control
  still red when mutated.

### Phase 2 — AEGIS-Sleuth consumes (decided: build-time sync — relay QA r2 F6)

> Update 2026-09-05: GH-168 **shipped** (closed completed) — `ResolveModelAlias` is live over the
> hand-maintained rows. Phase 2 is therefore a **conversion**: point the shipped resolver's table
> input at the synced catalog, not a from-scratch build. Build-out issue: AEGIS-Sleuth-Slackbot#173.

1. The shipped resolver (GH-168) reads `ModelAliases` from a **build-time sync**
   of this catalog's `target: "native"` rows into `data/static/ai/command-normalization.json`,
   the synced rows **carrying GH-168's optional provenance columns** (`Source`, `VerifiedOn`,
   `Flags`), which the loader already ignores. This mirrors Phase 1's shape — generated data file,
   resolver untouched, deploy hermetic, no new runtime read path. "Consume the catalog directly"
   (teaching Sleuth's loader a new schema) is demoted to a Phase-3-gated alternative.
2. `run-diagnostics` pin audit reports `verified_on` age and `flags` **read from the synced file's
   provenance columns** (the named data source for the stale-pin probe, GH-168 rev3).

- Accept: `rmm change model to ChatGPT` resolves with logged provenance naming catalog version;
  unknown name still refuses; the `gemini pro` flag surfaces in diagnostics.

### Phase 3 — parked: gateway/service (do NOT build without a new decision)

Only a concrete routing/auth/failover need (multi-provider fallback, centralized auth, cost
routing) reopens this. If it ever does: server-side, thin, in front of a proven gateway (e.g.
Portkey) rather than from scratch, with its own reversibility read. This repo's data remains the
source of truth either way.

## Versioning & cadence (relay QA r2 F5 — the taxonomy the doc previously presumed)

Semver on a data file, judged by what the change does to resolution:

- **MAJOR** — reader-contract change: schema URI/fields, vocabulary removal, uniqueness or
  normalization rule changes, **row removal** — anything that can make a previously-resolving
  alias miss.
- **MINOR** — any other resolution-affecting change: a row added, or `replace`/`target`/`flags`
  changed (pin corrections included: a repin changes what an input resolves to).
- **PATCH** — provenance-only metadata (`source`, `verified_on`): zero resolution change.

Rules: consumers pin **exact** versions (the two-PR governance already presumes it); every release
is **git-tagged** so "resolved by catalog vX.Y.Z" names an immutable commit; catalog CI rejects a
`data/catalog.json` change that does not bump `version` + `updated`; sync PRs are event-driven
(consumer needs a row; dispute adjudicated; MAJOR upgrade), plus a periodic `verified_on`-age audit
on **both** consumer sides — XYZ's 7 rows otherwise sit `verified_on: null` forever with no
freshness signal.

## Governance (relay QA r1/r2)

- **This catalog wins.** A row here is the pin of record; a consumer's vendored copy that drifts
  from its pinned version is a bug in the consumer's sync, not a competing source.
- **Disputes:** if a consumer has evidence a pin is wrong, the fix is a PR here changing the row
  (with `source` for the new evidence) — never a local override file. While disputed, the row gets
  `flags: ["disputed"]` and the operator arbitrates; consumers resolve per the row as it stands.
- **Contribution flow costs two PRs** (row here, then a version-bump/sync PR per consumer). That is
  the deliberate price of pinned provenance; do not "fix" it with auto-sync or a live feed.
- **License — DECIDED (operator, 2026-09-05):** CC0-1.0 for the data (`data/LICENSE`), MIT for
  code and docs (`LICENSE`). This clears the relay-r2-F8 blocker: a public data-only repo with no
  license is legally unvendorable by either consumer.
  External-row evidence bar: `source` = first-party provider URL; every `source` string must be
  publicly resolvable (no private-repo issue refs).

## Blast radius & reversibility

- **This repo + Phase 0:** Easy. A data feed; both existing tables keep working untouched until
  each consumer's PR lands.
- **Phase 1 (XYZ):** the only step touching a live shared surface (`resolve-model-alias.sh` feeds
  the Aider lane + `resolve-profile.sh`). Mitigation: the resolver itself is untouched; the change
  swaps a generated artifact behind the existing compile-to-YAML shape, and the drift check plus
  retained hand-written assertions are strictly *more* coverage than today's hand-add flow
  (relay QA r2 F3). Undo = revert the PR; day-or-less.
- **Phase 2 (Sleuth):** additive — the GH-168 resolver is already live over hand-maintained rows;
  the catalog only changes that table's source (build-time sync), so no runtime path changes. Easy.
- **Phase 3:** not attempted; n/a.

## Non-goals

- No runtime service, no live catalog queries, no "newest in family" resolution — pinned rows only.
- No migration of Sleuth's `DirectCommandPatterns` (command normalization, not model aliases).
- No per-request model routing, cost/latency strategies, or failover chains.

## Review record

### Relay r1 — agy (GLM), 2026-09-05: Changes requested (folded)

Blocker-grade: uniqueness must hold under XYZ's punctuation-fold normalization (folded into Schema
rules, with the same-`replace` carve-out for intentional spelling variants); Phase 1 must not point
the Bash resolver at JSON — compile to the legacy YAML instead (folded into Phase 1; the frozen-twin
claim itself was overstated — `resolve-model-alias.sh` is not one of the twelve frozen twins — but
the design is stronger untouched). Should-grade: "refusal on unknown" wording invited a misreading
where exact IDs get refused — contract now states lookup-miss → pass-through → validate → refuse
(folded); governance + two-PR cost now explicit (folded). Nit: flagged rows carry
`verified_on: null` (folded). Pass: the `MODEL_ALIASES_FILE` seam verified at `c5831ff3`.
Raw block: XYZ-forge `relay-system/2026-09-05/model-catalog-plan-qa-agy.md` (uncommitted — the shim's
structural validator rejected the block's `**Verdict:**` formatting, exit 8, after the content was
written; content reviewed and folded manually).

### Relay r2 — DeepSeek harness / Alibaba Token Plan / qwen3.8-max, 2026-09-05: Changes requested (folded)

Sharpening pass; no blockers, architecture endorsed ([Pass] F13–F15). Folded: F1 `verified_on`
antecedent clarified (7-vs-53 "Rev 4" ambiguity); F2 schema rules now model XYZ's real 4-tier
resolver — same-target scoping, tier-4 capture CI rule, load-bearing row order with deterministic
render order; F3 "generated assertions" contradictions removed; F4 Phase 1 vendor shape decided
(byte-identical vendored copy + tag/sha256 pin record); F5 Versioning & cadence section added
(exact pins, tagged releases, CI version-bump check); F6 Phase 2 decided (build-time sync carrying
provenance columns; diagnostics reads the synced file); F7 contract item 6 (flagged rows resolve
normally, flags advisory); F8 license named as standing Phase 0 blocker (operator decision);
F9–F12 nits folded (case-folding explicit, dedupe wording + disputed-conflict rule, disputed rows
keep verify dates, this record cites committed relay files). Not folded as stated: none — all
findings accepted. Raw block: XYZ-forge
`relay-system/2026-09-05/model-catalog-plan-qa-qwen.md` (uncommitted at review time — the shim's
structural validator rejected the block's `VERDICT:` placement, exit 8, after the content was
written; folded manually).
