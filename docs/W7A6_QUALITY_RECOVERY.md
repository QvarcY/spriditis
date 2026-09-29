# W7A6 — Quality recovery diagnosis (Phase A)

## Scope and baseline

Diagnosis only. No frontend, crawler, or deployment changes were made. Core repository: C:\Users\mail\Spriditis_Dev\spriditis. Branch: main. HEAD: cdb48cf5ef35f1451dc01e84e07f1bd4bf923ea0. Working tree was clean before this document was added. The production example and its counts below come from the task brief; this diagnosis did not replay the production query or inspect the live sites.

Reported regression: the personalized laser engraved / 3D printed keychain query visited 11 pages on 3 active/crawled domains and returned 7 entities. dainamax.lv and nela-gems.myshopify.com yielded entities; laserlux.lv was crawled but yielded none; craftin.lv was discovered as below_search_threshold and was never inspected. CraftIN is a regression example, not a domain to special case.

## Current lifecycle, with code anchors

1. Query plan: build_search_queries in spriditis/search/query.py:170-366 starts with configured queries, adds target identity / required evidence / keyword queries, deduplicates and caps at search.max_queries (or max_recovery_queries). Configured order is preserved; generated queries are ordered by query memory. Target identity mode narrows generated queries, and recovery is target identity only.
2. Provider and local priority: ResearchCrawler._seed_from_search in spriditis/crawler/engine.py:1414-1729 calls SearchProvider.search per query with results_per_query, ranks each result set using _rank_search_hits (1340-1412) and local_relevance_signals (spriditis/search/relevance.py:55-192), then scores URL + title/snippet using text_relevance_score (spriditis/crawler/policy.py:156-225). The global candidate sort favors target anchor/identity matches, the legacy score, required evidence query, and earlier positions. It uses search metadata, not fetched page content.
3. Candidate pool: _search_candidate_pool is reset at run start (engine.py:166-172). It stores all normalized provider result URLs across the initial queries, one best ranked observation per normalized URL, sorted globally (1483-1497, 1685-1729). It remains available after bootstrap and is enlarged/re-ranked during recovery queries. Below-threshold search candidates remain in this in-memory pool and get a DomainRegistry candidate record. They are not queued for crawling merely by being in the pool. The pool is bounded indirectly by max_queries × results_per_query plus recovery queries; it is not a persistent cross-run queue.
4. Registry and activation: DomainRegistry.observe_search_result (spriditis/crawler/discovery.py:221-321) applies URL safety, persisted blocked/rejected/active state, expedition mode, search.result_threshold, then the supplied slot flag. A low score becomes candidate / below_search_threshold before the slot check. A high score without a slot becomes candidate / domain_budget_reached. Activation makes the record active and adds the domain to run_active_domains. observe_link and observe_feed_entry use external_link_threshold and similar checks (discovery.py:125-218, 324-423). Their direct crawl-time calls omit activation_budget_available, so their fallback check uses cumulative registry.active_count; their deferred-source backfill supplies an explicit free-slot flag. Seeds are explicitly activated (101-123), with no max_domains check at that call.
5. Frontier and crawl: only active records are fetched (engine.py:253-309; async planning at 1041-1086). URLFrontier deduplicates queued URLs and pops highest priority first (spriditis/crawler/frontier.py:23-79). Safety and robots, max_depth, max_pages_per_domain, and max_pages_total/attempts gate requests. HTTP/redirect failures mark the domain failed (engine.py:343-464). A 200 HTML response adds the final domain to coverage.usable_domains before extraction (466-503). Extracted entities are deduplicated by stable_key; registry.entities_found increments for new raw entities, while coverage.observe_entities is called with the resulting page entities (713-759). Sitemap, feed, and HTML links may queue further pages and activate/defer other domains.
6. Evidence and exhaustion: coverage.productive_domains means at least one page entity passed to observe_entities, regardless of price; registry.entities_found counts newly extracted entities before target enrichment. For a specific target, confirmed_domains requires relevant entities with confirmed target identity and priced_domains also requires a price (spriditis/crawler/coverage.py:42-55). The scheduler recomputes exhausted_domains at each _replenish_sources call as run_active_domains minus domains with eligible pending frontier items (engine.py:2034-2056). Thus exhaustion means no currently eligible queued work, not that a site lacks relevant products. It includes failed domains, domains whose queue ran dry, and domains capped by depth/pages. The run_active_domains audit set is not reduced.
7. Backfill: _replenish_sources calls _backfill_search_domain_slots then _backfill_discovered_sources before deciding whether to end (engine.py:2057-2092). Search backfill walks _search_candidate_pool and activates previously unactivated domains if a slot is free, but calls observe_search_result without a threshold override, so below_search_threshold stays untried (2154-2261). Discovered link/feed backfill only receives events deferred for domain_budget_reached, not below_threshold (engine.py:863-867, 2094-2152; feed at 671-696). An empty bootstrap frontier gets a ranked fallback that may override the search threshold for eligible safe results (1835-1942), but this runs only when the frontier is empty at bootstrap/recovery, not when existing active sources later prove weak. Recovery query reformulation is attempted only when coverage.needs_evidence is true (2069-2091).

## Precise answers

1. max_domains is enforced during registry observation: DomainRegistry's default active_count check (discovery.py:163-170, 258-265, 363-370), or the engine-supplied _source_slot_available flag for search (engine.py:1771-1783, 1865-1877, 2195-2205). The engine slot function compares len(coverage.occupied_domains(...)) with max_domains (2028-2032). _backfill_discovered_sources also checks slots (2112-2122). spriditis/crawler/policy.py:228-255 has a max_domains check in url_allowed, but the traced engine does not call that function. The bootstrap fallback's registry.active_count comparison (1937-1941) can stop its loop. Seed activation is an exception.
2. Semantically, search activation/backfill limits *occupied source slots*: active domains with eligible pending work plus retained sources. Direct crawl-time link/feed activation still uses the registry's cumulative activation count, so enforcement is mixed. For broad research, **every domain with one successful HTML response is retained**, even with zero entities. For specific-target research, only confirmed priced domains are retained (coverage.py:57-62). This is neither a strict lifetime total of domains tried nor a count of proven productive domains. DomainRegistry.active_count is a cumulative in-run audit count of activations, including later failures (discovery.py:459-462); using it for direct link/feed activation, stop_reason, or fallback can confuse these semantics.
3. A failed or exhausted source can free a slot after its eligible frontier work disappears, provided it was not retained. Thus HTTP failures and non-HTML responses generally permit replacement. A broad-mode 200 HTML source with zero entities does **not** free its slot, because usable_domains retains it. In specific-target mode, an unpriced/unconfirmed source can release its slot. Released domains still remain in run_active_domains and are skipped for reactivation in search/discovery backfill.
4. Failed-source backfill already exists and is tested by tests/search_failed_source_backfill_test.py: two 403 domains free slots and a third search domain is fetched. There is also deferred link/feed backfill, plus target-specific recovery queries and bootstrap ranked fallback. The test does not cover 200 HTML pages with no entities or below-search-threshold candidates.
5. _search_candidate_pool retains the best observation per normalized URL from all issued queries, including active, budget-blocked, and below-threshold candidates. It retains query, hit, local rank, legacy score, and positions. It does not retain every duplicate observation, fetched page evidence, or a dedicated tried/probed state.
6. Yes, below-threshold search candidates remain in the pool and registry, but ordinary backfill applies the same threshold again. The ranked fallback can bypass it only when the frontier is empty during bootstrap/recovery and its eligibility checks pass. Below-threshold link/feed events are not added to _deferred_sources.
7. “Productive” has multiple current meanings: coverage.productive_domains means any retained page entity; DomainRegistry.entities_found is raw newly extracted entity count; query/source memory has historical productive runs; broad slot retention requires only 200 HTML (usable_domains), not productivity; specific-target evidence requires relevant confirmed priced entities. These signals must not be conflated.
8. A domain is marked exhausted at the next replenish check if it has no eligible pending frontier URL. Robots-blocked/failed URLs, page/depth caps, and drained queues can produce this. It can be exhausted while still occupying a retained slot. Exhaustion is recomputed and may be cleared when new search URLs are queued (engine.py:1820-1833).
9. The loop can end on max_pages_total attempted URLs, max_pages_total successful visits, empty eligible frontier after backfill, or adaptive saturation/diminishing windows (engine.py:253-264, 935-974, 1230-1266). Adaptive windows are disabled at zero; when enabled they count entity-free successful HTML pages, and only specific-target unmet price coverage suppresses them. A broad run with weak sources can therefore stop before later candidates. A full occupied slot set blocks backfill; low-score candidates stay below threshold even when a slot later frees. search.max_queries and results_per_query also limit the discovered universe. The reported max_domains stop_reason is assigned after exhaustion and is a label, not an independent crawl-loop termination rule.
10. Yes. The existing candidate pool, registry, frontier, coverage state, and _replenish_sources/backfill points provide one scheduler where trial inspection and replacement can be added. A second crawler path would duplicate safety, robots, fetch, extraction, and audit logic.
11. Smallest safe Phase B change: introduce a **run-local, bounded trial state** for candidate domains in the existing scheduler. Preserve the global metadata ranking as order of work. After normal activation or as slots turn over, admit a small number of safe, untried search candidates to the same frontier for cheap inspection, including candidates below result_threshold if they pass a separate conservative trial-eligibility rule (negative and specific-target identity guards still apply). Fetch at most a small per-candidate page allowance using the existing request/extraction path. Promote/retain a broad source only on actual relevant entity or sufficiently strong page-level offering evidence; for specific targets require the existing confirmed identity and priced evidence for retained coverage. If a trial yields no such evidence after its allowance or eligible queue drains, record it as inspected/nonproductive for this run, free its slot, and advance to the next candidate. Do not mark a 200-but-unproductive source as an HTTP failure. A relevant category page may merit one bounded continuation before retirement; the exact content signal and allowance need focused implementation/test decisions. Make occupancy and audit counts explicit, and prevent the same domain from being retried indefinitely in one run.
12. Keep hard max_pages_total (including attempts/probes), max_pages_per_domain, max_depth, robots, public-URL/redirect safety, rate limits/politeness, SearchProvider query/result caps, negative keyword and target identity gates, plus an explicit cap on trial domains/pages and concurrent trials. Never let a below-threshold candidate bypass safety or specific-target identity rules merely because metadata is weak. Log candidate consideration, trial, promotion, retirement, and cap exhaustion so reported coverage distinguishes “discovered” from “inspected”.

## Why the later useful candidate is skipped

In the reported broad query, a low metadata score records craftin.lv as below_search_threshold, so it gets no frontier item. The other three sources can fill the three slots. A crawled 200 HTML source such as laserlux.lv is kept in usable_domains even when it yields zero entities; after its queue drains it remains in occupied_domains. Normal backfill therefore cannot take the candidate. Even if a slot frees by failure, search backfill reapplies result_threshold. The ranked bootstrap fallback is not invoked while another source populated the initial frontier. No page content from that later domain is examined, so the system cannot correct the metadata ranking with evidence.

## Phase B implementation handoff

Likely core files: spriditis/crawler/engine.py (trial scheduling, same fetch path, promotion/retirement events, stop sequencing); spriditis/crawler/coverage.py (occupied/retained semantics and run-local trial evidence); spriditis/crawler/discovery.py (explicit trial admission/status reason without treating an HTML nonproduct as a transport failure). spriditis/crawler/policy.py or spriditis/search/relevance.py only if a generic, conservative trial/page evidence predicate belongs there. spriditis/crawler/frontier.py and spriditis/search/query.py need no expected change; preserve their limits and ordering. Add one targeted regression test; adjust existing narrowly scoped assertions only if semantics intentionally change.

Exact regression test to add: tests/search_nonproductive_source_trial_backfill_test.py. Use FakeSearchProvider and FakeSession, expedition broad product-market mode, max_domains=2, max_pages_per_domain=1, max_pages_total=4, no sitemap/feed/robots/network. Return three distinct safe domains in metadata order: two high-score results whose 200 HTML pages contain no products or relevant entities, and a third result whose score is below search.result_threshold but whose fetched HTML contains a relevant priced Product JSON-LD item. Assert initial discovery records the third as below_search_threshold; after the two cheap inspections, the third URL is fetched through the ordinary frontier, produces the expected entity, and is promoted/retained based on page evidence. Assert the first two are recorded as inspected/nonproductive (not HTTP failed), the run never exceeds the hard page/attempt and trial caps, and decision events explain trial and replacement. The current code should fail the third-fetch/entity assertions. Keep tests/search_failed_source_backfill_test.py, tests/search_global_domain_budget_test.py, tests/adaptive_stopping_test.py, tests/adaptive_source_diversity_test.py, and target identity tests as targeted compatibility checks, not a full-suite run.

## Unresolved decisions / evidence limits

- The brief does not include the production result payload, configured crawl/adaptive windows, or exact candidate URL/score ordering. The code explains the skip mechanism but this document does not claim a replayed production trace.
- Define a reliable page-level offering signal for landing/category pages that reveal products through links but do not immediately extract an entity; decide whether one bounded continuation is enough. Product extraction failures and JS-only sites may still need separate work.
- Set explicit default trial-domain and per-trial page caps, and decide whether trialing should be on by default for all broad expeditions or opt-in. Keep max_domains as a bounded retained/concurrent budget and report cumulative attempted domains separately.
- Decide how to persist a run-local “inspected, nonproductive” result without falsely changing DomainRecord to failed or permanently rejecting a source that may improve later.
- Check redirect-to-new-domain accounting before changing slot semantics: engine.py:425-435 can add the final domain as a seed, which may affect occupied/audit counts.

## Next task

Implement the bounded trial/retirement path in the existing engine, coverage, and registry; add the exact fake-provider regression above; run only that test and the named targeted compatibility tests; inspect the resulting decision trace. Stop before frontend or deployment work.

## Phase B result (supersedes the Phase A next task)

Branch: fix/w7a6-source-lifecycle-recovery. Implementation commit: e0d3f2b1db8d6762adfb6312ba53c4fe644e9167. Base main HEAD remained cdb48cf5ef35f1451dc01e84e07f1bd4bf923ea0; no sync was needed. The Phase A document was preserved and extended here. No frontend or deployment changes.

Lifecycle change: broad expedition sources now retain a max_domains slot after their queue drains only if extraction has yielded an entity (the existing coverage.productive_domains signal). A 200 HTML response alone still records a usable/attempted source but no longer permanently retains capacity. An evidence-free source gets at most two processed pages (or the smaller configured max_pages_per_domain); when that allowance or its eligible queue is exhausted, DomainRegistry marks it candidate / nonproductive_source, coverage records a released domain, and a source_slot / released decision records the reason and page count. The run_active_domains set and active_count remain cumulative audit history. The same domain cannot reactivate during that run, but can be considered on a later run. Productive sources keep the configured per-domain cap. Specific-target and non-expedition slot retention remain unchanged.

Backfill still uses the existing candidate pool and frontier. After an evidence-free HTML source releases a slot, a safe below-result_threshold search candidate may be admitted using the existing ranked-bootstrap eligibility guard; negative matches and specific-target identity safeguards remain in force. Each trial uses the ordinary robots, safety, fetch, extraction, deduplication, depth, and page-budget paths. Adaptive stopping waits while a newly admitted or evidence-free trial source has eligible work, so it cannot stop just before the replacement is fetched. Async wave reservations honor the same per-source trial cap and drain cached waves before another wave is reserved. Stop telemetry now reports occupied_source_slots beside the preserved historical active_domains count; max_domains as a stop reason uses current occupancy.

Changed functions/files: spriditis/crawler/engine.py (_crawl_impl, _source_page_limit, _replenish_sources, _backfill_search_domain_slots, _prefetch_async_wave); spriditis/crawler/coverage.py (occupied_domains and released_domains); spriditis/crawler/discovery.py (_persisted_state and mark_nonproductive); spriditis/crawler/async_wave.py (optional per-domain wave limit). The regression tests are tests/search_nonproductive_source_trial_backfill_test.py (two empty HTML sources, later below-threshold product, and a two-page bound), tests/search_failed_source_backfill_test.py (the replacement now genuinely contains a product), tests/adaptive_stopping_test.py (deferred source is tried after slot release), and tests/async_wave_planner_test.py (per-domain reservation cap).

Targeted validation passed with the repository .venv and UTF-8 output: search_nonproductive_source_trial_backfill_test.py, search_failed_source_backfill_test.py, search_global_domain_budget_test.py, search_ranked_bootstrap_fallback_test.py, adaptive_stopping_test.py, async_wave_planner_test.py, and async_crawler_integration_test.py. git diff --check and staged diff --check passed. No full test suite was run.

Remaining limits: this phase only revisits URLs already returned by the bounded SearchProvider query/result plan. A source that yields a raw extracted entity is retained even if later broad-mode enrichment judges that entity irrelevant; tightening this would require changing the current productivity signal. An evidence-free category page can be retired after two pages even if relevant products are deeper. JS-only product content remains outside this change. **Broader candidate probing is still Phase C**, including wider discovery beyond the retained search pool and stronger page-level evidence for category pages; Phase B does not claim that work complete.

## Phase C1 — promising probe continuation

Status: implemented and locally validated on branch `fix/w7a6-c1-probe-evidence`.

Baseline before C1:

`e0ac8839bafc8f4d290361efcd8c627f4d7dd231`

### Problem addressed

Phase B correctly releases broad-expedition sources that return usable HTML but never produce entity evidence. Its default provisional allowance is two pages.

That is safe for genuinely empty sources, but can retire a legitimate shop or category source too early when the useful product page is one internal hop deeper.

Example lifecycle before C1:

search result
→ shop landing page
→ relevant category page
→ provisional 2-page cap reached
→ source retired
→ actual product page never inspected

### C1 behavior

C1 preserves the Phase B default:

- ordinary evidence-free source: maximum 2 provisional pages;
- no meaningful continuation evidence: release the source slot normally.

A broad-expedition provisional source may receive exactly one additional page, for a maximum provisional allowance of 3 pages, when actual page-level internal-link evidence is strong enough.

The continuation is granted only when:

- crawl mode is `expedition`;
- research is not specific-target mode;
- the source is not already productive;
- the source has not already received the C1 extension;
- `max_pages_per_domain >= 3`;
- the candidate is within `max_depth`;
- the existing `text_relevance_score()` meets the configured search relevance threshold;
- the URL/link context contains actual subject evidence from project keywords or required evidence terms;
- no configured negative keyword is present.

A structural URL bonus such as `/item/` or `/product/` is therefore not sufficient by itself.

While the source remains provisional, evidence-backed internal links are prioritized over structurally attractive but subject-unrelated internal URLs so the bounded extra probe is spent on the evidence that justified it.

### Important lifecycle semantics

The C1 extension does not promote or retain the source.

The source remains provisional.

Lifecycle:

candidate
→ normal short trial
→ strong internal-link evidence
→ one extra provisional page
→ entity evidence → productive
OR
→ no entity evidence → nonproductive release

Once entity evidence makes the source productive, `_source_page_limit()` returns to the ordinary configured `max_pages_per_domain`.

The extra provisional allowance is bounded by:

`min(3, max_pages_per_domain)`

and remains subject to all existing total-page, depth, safety, robots, deduplication, and lifecycle limits.

Specific-target behavior is unchanged.

### Files changed

- `spriditis/crawler/engine.py`
- `tests/search_promising_probe_continuation_test.py`
- `tests/search_nonproductive_source_trial_backfill_test.py`
- `docs/W7A6_QUALITY_RECOVERY.md`

### Validation

Focused C1 regression:

- relevant landing → category → product chain reaches the third provisional page;
- product entity and price are extracted;
- source becomes productive;
- exactly one `source_probe / continuation_granted` decision is emitted;
- ordinary navigation such as About → Contact does not earn the extra page;
- structural `/item/` URL score without actual subject evidence does not earn the extra page.

Compatibility validation passed:

- `tests/search_promising_probe_continuation_test.py`
- `tests/search_nonproductive_source_trial_backfill_test.py`
- `tests/adaptive_stopping_test.py`
- `tests/async_crawler_integration_test.py`
- `git diff --check`

The full test suite was intentionally not run.

### Known C1 limitations

C1 intentionally does not solve broad candidate discovery.

It still works only with sources already admitted into the existing search/discovery lifecycle.

The promising-evidence predicate is deliberately conservative and uses literal project keyword / required-evidence matches plus the existing relevance score. It does not attempt semantic page classification.

C1 reuses `search.result_threshold` for the strong internal-link decision instead of adding another configuration parameter. This keeps the change small; real research acceptance may later justify separating these thresholds.

JavaScript-only product discovery remains outside this phase.

### Exact Phase C2 task

C2 owns candidate-universe breadth.

Its goal is to let broad expedition research inspect substantially more safe candidate domains than the productive-source target without permanently occupying productive source slots.

C2 must:

1. separate probe capacity from retained productive-source capacity;
2. introduce explicit bounded probe-domain / probe-page budgets;
3. continue through additional untried SearchProvider candidates while useful candidates remain;
4. preserve search ranking as work priority rather than a premature final exclusion;
5. reuse the same crawler, safety, robots, extraction, lifecycle and deduplication paths;
6. prevent same-run candidate churn or repeated probing;
7. preserve Phase B nonproductive replacement and Phase C1 promising continuation;
8. keep specific-target identity safeguards unchanged;
9. add coverage telemetry for discovered versus actually probed candidate domains;
10. remain bounded by hard global resource limits.

C2 does not yet redesign query generation. Query-plan quality remains Phase D.

## Phase C2 — bounded candidate probe capacity

Status: implemented and locally validated on branch `fix/w7a6-c2-candidate-probe-capacity`.

Baseline before C2:

`e6d9106eb938e9694b998a6133b9a18060277e9c`

### Problem addressed

Broad expedition research previously treated `max_domains` as both retained deep-crawl capacity and practical candidate-inspection capacity.

That allowed the first productive sources to occupy all available source slots and could prevent lower-ranked but still relevant SearchProvider candidates from ever being inspected.

Search ranking therefore acted too much like a final exclusion boundary instead of work priority.

### C2 behavior

C2 separates retained source capacity from bounded candidate probing.

`max_domains` now represents retained/deep-crawl source capacity for broad expedition research.

A separate overflow probe lane may inspect additional SearchProvider candidates after retained capacity is full.

New crawl limits:

- `max_probe_domains`
- `max_probe_pages_total`

The ordinary global `max_pages_total` remains the final hard page ceiling.

### Retained versus productive sources

`productive_domains` records every source that produced entity evidence.

`retained_domains` records the bounded subset allowed to occupy retained deep-crawl capacity.

A productive overflow source still contributes its discovered entities to the research result even if retained capacity is already full.

It does not automatically receive unrestricted deep-crawl capacity.

Specific-target research keeps its existing priced-domain occupancy semantics.

### Candidate discovery telemetry

Coverage now tracks:

- SearchProvider candidate domains discovered;
- candidate domains actually probed;
- retained domains;
- productive domains;
- overflow probe domains;
- overflow probe pages.

The full globally ranked SearchProvider candidate pool remains available for bounded backfill/probing.

### Sequential overflow probing

When retained `max_domains` capacity is full, broad expedition research may activate one unresolved overflow probe domain at a time.

The candidate still passes the existing safety and ranked-bootstrap eligibility rules.

Below-threshold ranking no longer automatically prevents inspection when independent relevance signals justify a bounded probe.

Phase B nonproductive release and Phase C1 promising 3-page continuation remain in effect.

### Async overflow probing

Async prefetch reserves overflow probe-page budget before network I/O.

This prevents one concurrent fetch wave from overshooting `max_probe_pages_total`.

The same hard probe-page limit therefore applies to sequential and async execution.

### Honest stopping semantics

Broad expedition research no longer reports `max_domains` as though retained source capacity meant the candidate universe was exhausted.

C2 distinguishes:

- `search_candidates_exhausted`
- `probe_budget_disabled`
- `probe_domain_budget_exhausted`
- `probe_page_budget_exhausted`
- `search_candidates_unreached`
- existing global page/adaptive stop reasons

Stop telemetry also reports whether coverage was:

- candidate-pool exhausted;
- resource-limited;
- adaptive-stop limited;
- specific-target.

Remaining probeable candidate domains are included in the stop audit.

### Validation

Focused C2 validation passed:

- `tests/candidate_probe_retention_test.py`
- `tests/search_candidate_overflow_probe_test.py`
- `tests/search_candidate_overflow_probe_async_test.py`
- `tests/search_candidate_coverage_stop_test.py`
- `tests/search_nonproductive_source_trial_backfill_test.py`
- `tests/search_promising_probe_continuation_test.py`
- `tests/search_global_domain_budget_test.py`
- `tests/adaptive_stopping_test.py`
- `tests/async_crawler_integration_test.py`
- `git diff --check`

The full repository test suite was intentionally not run.

### Known C2 limits

C2 only broadens inspection across candidates already returned by the existing SearchProvider query plan.

It does not improve query generation itself.

Literal query/keyword quality can still limit which sites enter the candidate universe in the first place.

JavaScript-only discovery remains outside this phase.

The probe budgets are intentionally bounded and therefore do not claim complete Internet coverage.

### Exact next task — Phase D

Phase D owns query-plan quality.

It should:

1. separate instruction/filler wording from subject concepts and hard constraints;
2. generate multiple compact search formulations from the research request;
3. preserve specific-target identity requirements;
4. avoid topic-specific hardcoding;
5. improve recall without flooding the provider with weak permutations;
6. keep query count bounded;
7. record query-plan reasons in existing audit telemetry;
8. validate against real broad-market research rather than synthetic query volume alone.

After Phase D, run a real core acceptance research before changing the public API/frontend result model.
