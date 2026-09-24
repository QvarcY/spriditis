# Sprīdītis Architecture

Current baseline: **3.3.0-alpha.1**

Sprīdītis is structured as a research engine rather than a single-purpose scraper. The design separates discovery, extraction, analysis, persistence, and presentation so each layer can evolve independently.

## High-level flow

```text
Research question
      ↓
ResearchProject
      ├── Seed URLs
      └── Expedition
             ↓
       Query Generator
             ↓
       SearchProvider
             ↓
       candidate URLs/domains
             ↓
       Domain Registry
             ↓
          URL Frontier
             ↓
Crawler
      ├── robots / URL safety
      ├── crawl budgets
      ├── sitemap discovery
      └── external-link discovery
              ↓
        Domain Registry
              ↓
Structured Extraction
(JSON-LD / OpenGraph / adapters)
      ↓
MarketEntity
      ↓
Optional AI enrichment
      ↓
SQLite persistence
      ├── projects
      ├── runs
      ├── entities
      ├── observations
      ├── domains
      ├── domain_discoveries
      ├── search_queries
      └── search_results
      ↓
HTML report / service consumers
```

## Core layers

### `spriditis/core`

Contains reusable domain models such as:

- `ResearchProject`;
- `MarketEntity`;
- run result structures;
- Domain Registry records and discovery events.

The core should not know about a particular private deployment.

### `spriditis/crawler`

Owns traversal behavior:

- URL frontier;
- URL normalization and safety policy;
- robots handling;
- crawl depth and page budgets;
- Domain Registry discovery decisions;
- sitemap discovery;
- crawl engine.

### `spriditis/search`

Owns active source discovery for Expedition:

- provider-neutral `SearchProvider` interface;
- deterministic query generation;
- search-result models;
- offline fake provider for repeatable integration tests;
- SearXNG JSON API provider.

Search results do not bypass crawler policy. They enter through Domain Registry relevance, safety and domain-budget decisions before being added to the crawl frontier.

### `spriditis/extraction`

Converts source HTML and structured metadata into generic market entities.

Structured evidence is preferred before AI enrichment.

### `spriditis/sources`

Contains source-specific adapters for cases where generic structured extraction is insufficient.

Adapters should remain isolated so source quirks do not spread through the crawler core.

### `spriditis/ai`

Provides optional AI enrichment.

The crawler/extraction pipeline must remain usable when AI is disabled or temporarily unavailable.

The current flow batches already-extracted entities before AI analysis. Provider failure can fall back to local classification.

### `spriditis/storage`

Owns SQLite persistence and schema evolution.

The version-neutral default database is:

```text
data/spriditis.db
```

Schema migration is explicit, and legacy databases can be copied through SQLite's backup API before applying the current schema.

### `spriditis/reports`

Turns completed run data into human-readable reports.

### `spriditis/api`

Provides a service boundary for future UI/API consumers.

A future UI should call the service layer rather than importing crawler internals directly.

## Domain Registry

The Domain Registry is the central memory of source discovery.

Current states:

- `candidate` — observed but not activated;
- `active` — allowed into the crawl process;
- `blocked` — rejected by a safety/policy rule;
- `rejected` — explicitly rejected by research logic;
- `failed` — crawl or source failure.

Discovery events preserve provenance such as source URL, target URL, relevance score, action, reason, and timestamp.

The controlled discovery baseline validates:

```text
external link
    ↓
relevance score
    ↓
candidate / active / blocked
    ↓
domain budget
    ↓
frontier
    ↓
crawl
```

## Safety boundaries

Crawler policy should be evaluated before a URL becomes an active crawl target.

Important boundaries include:

- supported HTTP/HTTPS schemes;
- localhost/private/link-local IP protection;
- blocked hosts;
- blocked paths;
- binary/static-file filtering;
- redirects;
- robots policy;
- page/domain budgets.

## 3.3 SearchProvider / Expedition

Provider-neutral active discovery is now part of the current baseline:

```text
ResearchProject
      ↓
Query Generator
      ↓
SearchProvider
      ↓
candidate results
      ↓
Domain Registry
      ↓
existing safety + relevance + budgets
```

A project may now bootstrap Expedition without seed URLs. Search results do not bypass Domain Registry or crawler safety policy; they enter through the same auditable decision path as link-based discoveries.

The deterministic integration path uses a fake provider so tests do not depend on external services. A SearXNG provider supplies the first real-provider implementation. Provider/query provenance and search counters are preserved for auditability.

The next architectural work is stabilization: provider health/error surfaces, query/result quality, repeated-run behavior and real-provider integration coverage.

## Design principles

1. **Source facts before AI interpretation.**
2. **AI is optional, not the source of truth.**
3. **Discovery decisions are auditable.**
4. **Budgets and safety rules are explicit.**
5. **The public core stays generic.**
6. **UI/API consumers depend on a service boundary, not crawler internals.**
