# W6.9B: target-aware discovery and evidence-based continuation — closeout

## Closeout status

**CLOSED / ACCEPTED / PRODUCTION** — 2026-09-28.

- CORE base before W6.9B: `0301a31caf7359a98c6e068efa7d19f75dbadffa` (W6.9A).
- W6.9B commit chain:
  - `acf08b81e4a76314ab2c107abeecf9f37ef6cbb3` — target-aware research orchestration;
  - `8ba8605e02a67fa1b205d6e970e5e919c640e3a1` — preempt low-value target continuations;
  - `19833e95281eab5356ee35736fc2da99f01211ba` — aggregate target continuation telemetry.
- GitHub `main` and production core now point to `19833e95281eab5356ee35736fc2da99f01211ba`.
- WEB/API required no W6.9B runtime change; W6.9A WEB target parser remains at `5d8db4c7167c5617a6b12eceac187907045c7e9f`.
- Production API/worker release remains `/opt/spriditis-web-api/releases/5d8db4c7167c5617a6b12eceac187907045c7e9f`.
- No DB schema migration, frontend release, extractor rewrite or transport-safety relaxation was part of W6.9B.

## Problem and resulting behavior

The old loop could stop after three extracted entities even when all three were
rejected by the final target gate. Failed sources also consumed the lifetime
domain activation budget. Search planning could spend a quick-profile query on
the first three words of the request, omitting the requested model entirely.

For a specific target, the new loop is:

1. Build model/qualifier/constraint-preserving queries and rank target matches.
2. Collect a ranked candidate pool before assigning source slots.
3. Fetch and extract a page.
4. Enrich that page's new entities and apply the existing W6.9A identity gate.
5. Record confirmed, relevant entities and sources with confirmed prices.
6. Continue eligible pages; replace exhausted sources from search or deferred
   HTML/feed discovery when useful-source slots are available.
7. If the pool is exhausted and coverage is insufficient, issue unused target
   query variants within a separate recovery budget.
8. Finish on an existing soft stop only after the source goal is met, or finish
   on a hard ceiling / exhausted discovery with explicit insufficient coverage.

The regression reproducing three wrong extracted entities now reaches the next
source and confirms its actual target offer. Rejected models remain in the
audit and are excluded from price analytics. Search snippets are discovery
signals only; they are not promoted to confirmed offers.

## Audit and budget semantics

`DomainRegistry.active_count` still returns `len(run_active_domains)`: it includes
every domain activated in this run, including domains that later fail. Domain
lifecycle status, extracted entity counts, activation reasons, and discovery
history retain their audit roles. A robots-denied URL is not relabeled as a
domain-wide HTTP failure.

`ResearchCoverage` is separate run-local state:

| Field | Meaning |
| --- | --- |
| `attempted_domains` / `attempted_urls` | Main-page attempts, including robots denials and transport failures |
| `usable_domains` | At least one successful HTML response |
| `productive_domains` | At least one new extracted entity, even if later rejected |
| `confirmed_domains` | At least one relevant entity confirmed by the target gate |
| `priced_domains` | At least one such entity also has a price |
| `exhausted_domains` | No eligible queued pages remain, including failures or a per-domain cap |

For the currently supported product-market / price-monitoring flows, occupied
slots are pending sources plus sources with confirmed priced offers. A source
may be exhausted for further crawling while its existing evidence still occupies
a useful-source slot. Broad searches retain successful HTML sources in their
budget and keep the existing ungated entity-based soft-stop behavior.

Registry observation methods accept an optional `activation_budget_available`
decision from orchestration. Their defaults preserve the previous budget rule.
URL safety, relevance thresholds, sticky blocked/rejected states, and discovery
depth limits still apply. A persisted active source must also obtain a run-local
slot before search schedules it.

## Coverage and safety ceilings

- For specific market research, `crawl.max_domains` is the source coverage goal:
  that many distinct source hosts with confirmed relevant priced offers. This is
  a configurable market-research heuristic, not a universal count of results.
- `confirmed=0` cannot satisfy this goal or trigger diminishing/saturation stops.
- Sources are probed until their eligible queue drains or the per-domain cap is
  reached; one unproductive page does not discard other eligible pages.
- `search.max_queries` remains the initial query ceiling.
- New `search.max_recovery_queries` defaults to 2; 0 disables reformulation.
  Total search calls are bounded by their sum, and queries are not repeated.
- `crawl.max_pages_total` also bounds main-page attempts. Robots denials and
  connection failures cannot cause unlimited replacements. Existing async retry,
  sitemap, and feed-specific limits still apply separately.
- If the goal remains unmet, final `stop_reason` is
  `insufficient_target_coverage`. The `coverage_assessment` decision preserves
  the underlying reason such as `max_pages`, `max_page_attempts`, or
  `discovery_exhausted`. The final stop audit and report agree on the outcome.

## Confirmed validation point

Specific-target validation runs immediately after extraction/deduplication and
before `_update_adaptive_stop`. It uses the actual enrichment result followed by
the unchanged `apply_target_identity_gate`, not a provisional snippet match.
Only `is_relevant` entities with `target_identity_status=confirmed` count.
Entities are enriched once. Broad searches keep their final batch enrichment.
Existing progress event names are retained; query positions continue across
recovery rounds and analysis events reflect the earlier validation work.

## Files to review

| File | Responsibility |
| --- | --- |
| `spriditis/crawler/coverage.py` | Separate evidence state and useful-source accounting |
| `spriditis/crawler/engine.py` | Early validation, replacement, recovery, stopping and audit |
| `spriditis/crawler/discovery.py` | Accept explicit activation capacity while retaining audit counts |
| `spriditis/crawler/frontier.py` | Read queued items without changing their priority/order |
| `spriditis/search/query.py` | Target queries, constraints, locale, unused recovery variants |
| `spriditis/search/relevance.py` | Token-based target/anchor ranking signals |
| `spriditis/crawler/policy.py` | Target evidence contributes to discovery relevance |
| `spriditis/core/projects.py` | Bounded recovery-query configuration |
| `spriditis/reports/html.py` | Honest insufficient-coverage note |

No DB schema, API route, worker/queue, frontend, transport implementation,
extractor, or W6.9A identity-rule changes are included.

## Local verification

23 CORE regression scripts and 2 callback test functions passed across 24 CORE
test files, plus 10 WEB project-builder tests.
The accompanying `verification.txt` names every executed script.

New regression files cover query planning, target ranking, failed-source
replacement, and the complete coverage loop. The loop tests exercise sequential
and async execution, wrong models/generic brand entries, per-domain probing,
missing prices/required evidence, recovery queries, saved active sources, HTTP
403, connection errors, robots denials, URL safety, deferred HTML discovery,
hard attempt ceilings, exhaustion, and no duplicate enrichment.

Existing checks cover domain registry behavior, query/source memory ordering,
local relevance, global domain selection, stopping, multihop discovery,
diversity, async planning/retries, feeds, progress callbacks, HTTP security,
extraction evidence, DOM/microdata extraction, and the final identity gate.

The real WEB request was also passed through its unchanged builder into CORE.
Its quick profile produces:

- Initial: the configured full request; `Bambu Lab P1S Combo Latvija`.
- Recovery: `Bambu Lab P1S Combo cena`; `Bambu Lab P1S Combo veikals Latvija`.
- Limits: 12 main-page attempts, 4 pages/domain, 3 useful source slots,
  2 initial queries and at most 2 recovery queries.

## Production acceptance and closeout

The deterministic local suite passed before promotion. The final W6.9B telemetry patch completed the full core regression gate with **71/71** test scripts passing.

Two isolated live P1S Combo acceptance runs were used to validate the orchestration:

1. The first W6.9B run exposed a real budget-waste defect: irrelevant same-domain continuation URLs could consume the page budget before recovery search.
2. The continuation-filter fix allowed recovery search to run before the budget was exhausted and preserved target-anchor-positive URL paths.
3. The telemetry follow-up replaced thousands of per-URL continuation discard decisions with bounded per-page/per-source-type summaries.

In the final isolated acceptance, recovery behavior remained intact while adaptive-decision volume fell from roughly 3.3k events in the noisy run to **52 total decisions**, including **11 `target_continuation / filtered_summary` events** representing **1756 discarded continuation candidates**. Audit totals and bounded samples remained available without database event spam.

Production deployment then:

- acquired the shared execution lock;
- stopped only `spriditis-web-worker.service`;
- fast-forwarded core from W6.9A `0301a31...` to W6.9B `19833e9...`;
- passed import sanity;
- passed target coverage orchestration, adaptive decision trace and target identity regressions on production;
- restarted the worker;
- left the production worktree clean;
- left worker, API and Nginx active;
- left the API immutable release unchanged at `5d8db4c...`;
- passed a post-deploy health check with the execution lock available again.

### Remaining limitations

- Distinct hosts are a coverage proxy, not proof of independently owned sellers.
- The source goal does not establish statistical market completeness.
- Live fetchability, extraction quality and latency still vary with third-party sites.
- Opaque same-domain continuation URLs with no target evidence may be skipped intentionally; recovery search is preferred under a scarce page budget.
- Locale-specific query wording is currently conservative and not a full multilingual query-planning system.

This file is now a historical/technical closeout for W6.9B. Current project status belongs in `README.md`, `ROADMAP.md` and `docs/ARCHITECTURE.md`; do not turn this closeout back into a live status dashboard.
