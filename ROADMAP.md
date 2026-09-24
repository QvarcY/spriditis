# Sprīdītis Roadmap

This roadmap describes direction, not delivery dates. Sprīdītis is developed iteratively and each stage should remain testable before the next layer is added.

## Current baseline — 3.3.0-alpha.1

The current public checkpoint establishes the first true SearchProvider-backed Expedition bootstrap.

Completed or validated:

- configurable `ResearchProject`;
- generic `MarketEntity`;
- single-domain crawling;
- controlled multi-domain discovery;
- persistent Domain Registry;
- domain states: `candidate`, `active`, `blocked`, `rejected`, `failed`;
- discovery audit trail;
- per-domain and total crawl budgets;
- URL-safety policy;
- `robots.txt` handling;
- sitemap discovery;
- structured extraction from JSON-LD and OpenGraph;
- source adapters;
- optional batched AI enrichment with local fallback;
- SQLite observations and schema migration foundation;
- HTML reports;
- CLI and service boundary;
- controlled integration test for `candidate → active → crawled`;
- provider-neutral `SearchProvider` interface;
- deterministic query generation from project intent;
- offline/fake provider for repeatable tests;
- SearXNG JSON API provider;
- zero-seed Expedition bootstrap;
- provider/query provenance for search discoveries;
- search query/result/activation/error counters;
- database schema v3;
- integration coverage proving search → activation → crawl.

## 3.3 stabilization

Near-term work stays inside the 3.3 line and focuses on making active search dependable outside the deterministic test harness.

Planned direction:

- validate and harden real SearXNG execution;
- improve provider error/health reporting;
- refine query construction and result relevance;
- strengthen deduplication and repeated-run behavior;
- keep search budgets explicit and auditable;
- expand integration coverage without weakening URL/SSRF protections.

## Later research capabilities

Potential directions after Expedition is stable:

- competitor/company research extractors;
- service-market extractors;
- stronger price normalization;
- longitudinal change and trend analysis;
- domain/source quality signals;
- richer evidence lineage;
- reusable research templates;
- scheduled/repeated research jobs;
- export formats beyond HTML.

## API and UI direction

The core already exposes a service boundary so a UI does not need to call crawler internals directly.

Potential product-facing layers:

- REST API;
- web UI;
- job queue;
- scheduler;
- run history and comparison;
- project editor;
- Domain Registry explorer;
- report browser.

These should remain separate from the crawler/extraction core.

## Open-core direction

The public core is intended to remain useful on its own. Hosted, operational, team, billing, or other product-layer capabilities may be developed separately.

See [docs/OPEN_CORE.md](docs/OPEN_CORE.md).

## Non-goals

Sprīdītis is not intended to become a mechanism for bypassing authentication, CAPTCHAs, paywalls, access controls, or private-network restrictions.

---

## Latviski

Pašreizējais pieturas punkts ir **3.3.0-alpha.1**. Ir pārbaudīts zero-seed Expedition starts: Sprīdītis ģenerē meklēšanas vaicājumu, saņem SearchProvider rezultātus, izlaiž tos caur Domain Registry drošības un relevances noteikumiem, aktivizē derīgu avotu un to pārmeklē.

Tuvākais darbs ir reālā SearXNG providera stabilizācija, kvalitatīvāka vaicājumu/rezultātu atlase un atkārtotu Expedition skrējienu uzvedības nostiprināšana.

Pēc tam var sekot konkurentu un pakalpojumu tirgus ekstraktori, cenu/tendenču analīze, atkārtoti darbi, API un UI slānis.
