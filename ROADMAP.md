# Sprīdītis Roadmap

This roadmap describes direction, not delivery dates. Sprīdītis is developed iteratively and each stage should remain testable before the next layer is added.

## Current baseline — 3.2.0-alpha.3

The current public checkpoint establishes the Discovery Engine foundation.

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
- controlled integration test for `candidate → active → crawled`.

## 3.3 — SearchProvider + true Expedition mode

Goal: allow Sprīdītis to discover relevant sources that are not linked from existing seed pages.

Planned architecture:

```text
ResearchProject
      ↓
Query Generator
      ↓
SearchProvider
      ↓
candidate URLs / domains
      ↓
Domain Registry
      ↓
relevance + safety + budgets
      ↓
crawl frontier
```

Planned work:

- provider-neutral `SearchProvider` interface;
- deterministic query generation from project intent;
- offline/fake provider for repeatable tests;
- one practical provider implementation;
- deduplication between search results and existing Domain Registry entries;
- explicit discovery provenance;
- search budgets and provider request limits;
- true `expedition` mode.

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

Pašreizējais pieturas punkts ir **3.2.0-alpha.3** ar pārbaudītu Domain Registry un kontrolētu vairāku domēnu discovery plūsmu.

Nākamais lielais posms ir **3.3 — SearchProvider + īsts Expedition režīms**, lai Sprīdītis spētu pats atrast jaunus avotus arī tad, ja uz tiem nav saišu jau zināmajās lapās.

Pēc tam var sekot konkurentu un pakalpojumu tirgus ekstraktori, cenu/tendenču analīze, atkārtoti darbi, API un UI slānis.
