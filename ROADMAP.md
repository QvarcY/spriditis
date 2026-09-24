# Sprīdītis Roadmap

> **Direction, not deadlines.** This roadmap is intentionally iterative. A milestone is only considered complete after the behavior is testable and the previous layers remain stable.

## Status

- ✅ **Released** — public implementation
- 🧪 **Validating** — implemented locally / under validation or publication preparation
- 🚧 **Next in progress** — next active development milestone
- 🧭 **Planned** — accepted direction, implementation not started
- 🔭 **Later** — useful future work, deliberately not prioritized yet

## Guiding principles

1. **Source-backed facts before AI interpretation.**
2. **Research Memory before brute-force crawling.**
3. **Safety, provenance and auditability are architectural features.**
4. **Prefer local, open, self-hostable and zero-cost building blocks where practical.**
5. **Paid APIs may exist as optional providers, but the public core should not require them.**
6. **Make the crawler smarter before making it massively distributed.**
7. **A good research run should know when to stop.**

## Current public baseline — ✅ 3.3.0-alpha.1

The public baseline establishes the first true zero-seed Expedition bootstrap.

Implemented:

- configurable `ResearchProject`;
- generic `MarketEntity`;
- structured extraction from JSON-LD and OpenGraph;
- source adapters;
- optional batched AI enrichment with local fallback;
- persistent SQLite observations;
- Domain Registry;
- domain lifecycle states;
- controlled multi-domain discovery;
- sitemap discovery;
- URL/SSRF safety policy;
- `robots.txt` handling;
- crawl budgets;
- discovery audit trail;
- provider-neutral `SearchProvider`;
- deterministic Expedition query generation;
- offline fake provider;
- SearXNG provider;
- zero-seed Expedition;
- provider/query provenance;
- search counters;
- search → activation → crawl integration coverage.

## 🧪 3.3.0-alpha.2 — SearchProvider hardening

Implemented locally and validated; publication is the next step.

Scope:

- retry/backoff for transient provider failures;
- `Retry-After` handling;
- structured SearchProvider errors;
- retryability and HTTP-status metadata;
- result deduplication across multiple queries;
- separate raw / unique / duplicate counters;
- early rejection of invalid non-HTTP(S) search results;
- database schema v4;
- `search-check` CLI command;
- reliability and dedupe tests.

## 🚧 3.3.0-alpha.3 — Feed Discovery & Incremental Monitoring

Goal: make every useful domain capable of becoming an efficient recurring discovery source.

Planned:

- RSS 2.0;
- Atom;
- JSON Feed;
- HTML `<link rel="alternate">` autodiscovery;
- conservative common-feed-path fallback;
- feed provenance;
- feed-to-frontier relevance/safety/dedupe path;
- `ETag`;
- `Last-Modified`;
- `304 Not Modified`;
- feed state persistence;
- new-entry counters;
- incremental repeated-run tests.

## 🧭 3.3.0-alpha.4 — Research Memory

Goal: remember not only observations, but the effectiveness of the research process itself.

Planned:

- query yield;
- source/domain yield;
- useful-entity yield;
- duplicate rate;
- source success rate;
- last useful run;
- discovery provenance metrics;
- source-value score;
- query-value score;
- history that can influence later prioritization.

Research Memory should make this possible:

```text
query → provider → domain → discovery path → page → extraction → entity → observation
   ↑                                                                  ↓
   └────────────────────── future prioritization ← metrics ←───────────┘
```

## 🧭 3.3.0-alpha.5 — Adaptive Expedition

Goal: make Expedition choose better paths without requiring a paid AI service.

Planned:

- BM25/local text relevance;
- richer title/path/domain signals;
- query prioritization from historical yield;
- source-value weighting;
- coverage saturation;
- diminishing-returns stopping;
- controlled multi-hop discovery;
- explicit discovery-depth and domain budgets.

A successful run should be able to stop because **enough useful coverage has been reached**, not only because `max_pages` was exhausted.

## 🧭 3.3.0-alpha.6 — Entity Resolution

Goal: represent the same real-world product/service as one entity observed across multiple sources.

Planned signals:

- GTIN / EAN;
- manufacturer + model;
- SKU where meaningful;
- normalized title;
- price range;
- fuzzy title similarity as a supporting signal.

Expected model:

```text
MarketEntity
└── source observations
    ├── shop A → price / availability
    ├── shop B → price / availability
    └── shop C → price / availability
```

## 🧭 3.3.0-alpha.7 — Fallback Extraction + Evidence Confidence

Goal: improve coverage while preserving evidence quality.

Extraction priority:

1. JSON-LD;
2. schema.org microdata;
3. OpenGraph;
4. source adapter;
5. deterministic DOM heuristics;
6. optional AI extractor as a last resort.

Every extracted field should be able to preserve:

- value;
- source URL;
- extraction method;
- confidence;
- evidence/provenance.

## 🧭 3.3.0-alpha.8 — Change Detection

Goal: turn observations into meaningful events.

Planned events:

- `PRICE_DROP`;
- `PRICE_INCREASE`;
- `NEW_ENTITY`;
- `ENTITY_DISAPPEARED`;
- `SOURCE_CHANGED`;
- `DOMAIN_FAILED`;
- `DOMAIN_RECOVERED`;
- feed appeared/disappeared.

This becomes the foundation for trend analysis and notifications.

## 🧭 3.3.0-alpha.9 — Watch mode

Goal: make projects capable of living over time.

Planned:

- incremental repeated research;
- local scheduling hooks;
- `spriditis watch`;
- change-only summaries;
- notification hooks;
- feed/ETag-aware low-cost refresh;
- reuse of Research Memory.

## 🧭 3.3.0-alpha.10 — Async crawler + adaptive politeness

Goal: improve throughput only after the research logic is selective enough.

Planned:

- bounded async requests;
- per-domain semaphore;
- global concurrency cap;
- adaptive delay from server behavior;
- retry budgets;
- backpressure;
- no weakening of robots/URL/private-network protections.

## 🔭 Longer-term backlog

### Discovery
- additional SearchProvider adapters;
- prioritize zero-cost/self-hostable integrations;
- optional paid providers only as plugins;
- richer research templates.

### Extraction
- price/currency/VAT normalization;
- images;
- specification tables;
- carefully isolated source adapters.

### Analytics
- weekly/monthly category trends;
- cross-project comparisons;
- market-entry/disappearance analysis;
- confidence-weighted summaries.

### Export
- CSV;
- JSONL;
- Parquet;
- future BI integrations.

### API / UI / automation
- FastAPI layer;
- project/run dashboard;
- Domain Registry explorer;
- report viewer;
- scheduler/background jobs;
- webhooks/notifications.

### Engineering
- stricter typing;
- larger automated test suite;
- CI/CD;
- Docker;
- project JSON Schema;
- plugin entry points for providers/adapters.

### Optional AI
- additional provider adapters;
- local models such as Ollama where useful;
- structured model outputs;
- cost tracking;
- evaluation framework;
- RAG over collected observations after the deterministic data model is mature.

## What is deliberately not a near-term priority?

These may become useful later, but they should not distract from the research engine:

- distributed queues;
- Redis/RabbitMQ infrastructure;
- PostgreSQL migration before SQLite becomes a measured bottleneck;
- Playwright as a default for every page;
- heavy agent frameworks;
- hosted dashboards before the research core is mature;
- mandatory paid search or AI APIs.

## The intended differentiator

Sprīdītis should not compete by being “another HTML crawler”.

The target behavior is:

> **Give me a research goal. I will find sources, remember which paths were useful, avoid repeated work, detect meaningful change, and make the next run more selective than the previous one.**

That is the long-term combination of **Research Memory + Adaptive Discovery + Evidence Confidence + Incremental Monitoring**.

---

## Latviski

Sprīdīša attīstības virziens ir apzināti veidots tā, lai publiskais kodols varētu būt praktiski lietojams arī bez obligātiem maksas API.

Tuvākā secība:

```text
3.3.0-alpha.2  SearchProvider stabilizācija
        ↓
3.3.0-alpha.3  RSS / Atom / JSON Feed + incremental monitoring
        ↓
3.3.0-alpha.4  Research Memory
        ↓
3.3.0-alpha.5  Adaptive Expedition + BM25 + coverage saturation
        ↓
3.3.0-alpha.6  Entity Resolution
        ↓
3.3.0-alpha.7  Fallback Extraction + Evidence Confidence
        ↓
3.3.0-alpha.8  Change Detection
        ↓
3.3.0-alpha.9  Watch mode
        ↓
3.3.0-alpha.10 Async crawler + adaptive politeness
```

Mērķis nav panākt, lai Sprīdītis vienkārši pārmeklē pēc iespējas vairāk lapu. Mērķis ir, lai viņš ar laiku **atceras, kā atrada vērtīgus avotus, saprot, kuri ceļi dod rezultātus, pamana izmaiņas un netērē resursus tur, kur jaunā informācija vairs nerodas**.

See also [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/OPEN_CORE.md](docs/OPEN_CORE.md).
