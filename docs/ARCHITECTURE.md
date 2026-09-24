# Sprīdītis — arhitektūra / Architecture

Pašreizējā publiskā bāze / Current public baseline: **3.3.0-alpha.3**

> **Latviski pirmajā vietā, angļu valoda zemāk. / Latvian first, English below.**

---

# Latviski

Sprīdītis ir pētniecības dzinējs, nevis viena uzdevuma scraperis. Arhitektūra atdala discovery, crawl, extraction, analīzi, persistence un presentation, lai katru slāni var attīstīt neatkarīgi.

## Augsta līmeņa plūsma

```text
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
      ├── external-link discovery
      └── RSS / Atom / JSON Feed
             ↓
Structured Extraction
             ↓
MarketEntity
             ↓
Optional AI enrichment
             ↓
SQLite persistence
             ↓
Reports / service consumers
```

## Galvenie slāņi

### `spriditis/core`
Atkārtoti izmantojamie modeļi: `ResearchProject`, `MarketEntity`, run struktūras, Domain Registry ieraksti un discovery eventi.

### `spriditis/crawler`
URL frontier, normalizācija, drošības politika, robots, crawl dziļums/budžeti, sitemap discovery, Feed Discovery, Domain Registry lēmumi un crawl engine.

3.3.0-alpha.3 pievieno RSS 2.0, Atom un JSON Feed autodiscovery no HTML, kontekstuālu feed prioritizāciju, conditional HTTP pieprasījumus ar `ETag`/`Last-Modified` un `304 Not Modified`. Feed ierakstu URL neapiet crawlera drošības vai relevances politiku.

### `spriditis/search`
Provider-neatkarīgs `SearchProvider`, query ģenerēšana, search rezultātu modeļi, FakeSearchProvider testiem un SearXNG provideris.

3.3.0-alpha.2 papildus nostiprina šo slāni ar transient kļūdu retry/backoff, `Retry-After`, strukturētām providera kļūdām un rezultātu deduplikāciju starp query. `search-check` ļauj pārbaudīt providera konfigurāciju pirms pilna crawl.

Search rezultāti nedrīkst apiet Domain Registry vai crawlera drošības politiku.

### `spriditis/extraction`
Avota HTML un strukturēto metadatu pārvēršana `MarketEntity`. Strukturēti pierādījumi ir prioritāri pirms MI enrichment.

### `spriditis/sources`
Avotiem specifiski adapteri, izolējot konkrētas vietnes īpatnības no crawlera kodola.

### `spriditis/ai`
Izvēles MI enrichment. Crawler/extraction plūsmai jāstrādā arī bez MI.

### `spriditis/storage`
SQLite persistence un schema evolution. Noklusējuma DB:
```text
data/spriditis.db
```

### `spriditis/reports`
Cilvēkam lasāmas atskaites.

### `spriditis/api`
Servisa robeža nākotnes UI/API klientiem. UI nevajadzētu importēt crawlera internals tieši.

## Domain Registry

Statusi:
- `candidate`;
- `active`;
- `blocked`;
- `rejected`;
- `failed`.

Discovery eventiem jāsaglabā provenance: source URL, target URL, relevance signāli, darbība, iemesls un laiks.

No 3.3.0-alpha.3 Domain Registry stāvoklis tiek hidratēts no SQLite **pirms** jaunā run discovery lēmumiem. `blocked` un `rejected` saglabājas sticky, `active` tiek atpazīts kā zināms, bet run-local lapu/entity skaitītāji sākas no nulles, lai vēsturiskie skaitītāji netiktu pieskaitīti atkārtoti.

## Research Memory virziens

Plānotais lineage:

```text
query
 ↓
provider
 ↓
domain
 ↓
HTML link / sitemap / feed
 ↓
page
 ↓
extraction method
 ↓
entity
 ↓
observation
 ↓
change
```

Svarīgs princips: **katram nozīmīgam lēmumam jābūt izskaidrojamam.** Tāpēc `explain` un `trace` ir dabiska Research Memory saskarne.

## Feed state un HTTP resursu stāvoklis

RSS/Atom/JSON Feed dati netiek glabāti kā nejaušas kolonnas `domains` tabulā. Vienam domēnam var būt vairāki feedi, tāpēc 3.3.0-alpha.3 izmanto atsevišķu 1:N `feeds` tabulu (DB schema v5).

Feed state:
- feed URL;
- feed type;
- status;
- ETag;
- Last-Modified;
- last entry id;
- last published;
- last checked/success;
- counters/error.

Ilgtermiņā `ETag`/`Last-Modified` var kļūt par vispārīgu per-resource fetch-state mehānismu arī sitemap un parastām lapām.

## Drošības robežas

- tikai atbalstīti HTTP/HTTPS scheme;
- localhost/private/link-local aizsardzība;
- blocked hosts/paths;
- binary/static filtrēšana;
- redirect kontrole;
- robots policy;
- page/domain/depth budgets.

## Dizaina principi

1. Avotu fakti pirms MI interpretācijas.
2. MI ir izvēles enrichment, nevis patiesības avots.
3. Discovery lēmumi ir auditējami un izskaidrojami.
4. Budžeti un drošības noteikumi ir explicit.
5. Publiskais kodols paliek generic.
6. Research Memory tiek būvēta virs SQLite, nevis ieviešot smagu infrastruktūru bez vajadzības.
7. Ātrums nedrīkst vājināt politeness un drošību.

---

# English

Sprīdītis is a research engine rather than a single-purpose scraper. The architecture separates discovery, crawling, extraction, analysis, persistence, and presentation so each layer can evolve independently.

## High-level flow

```text
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
      ├── external-link discovery
      └── RSS / Atom / JSON Feed
             ↓
Structured Extraction
             ↓
MarketEntity
             ↓
Optional AI enrichment
             ↓
SQLite persistence
             ↓
Reports / service consumers
```

## Core layers

### `spriditis/core`
Reusable models: `ResearchProject`, `MarketEntity`, run structures, Domain Registry records and discovery events.

### `spriditis/crawler`
URL frontier, normalization, safety policy, robots handling, crawl depth/budgets, sitemap discovery, Feed Discovery, Domain Registry decisions and crawl engine.

3.3.0-alpha.3 adds RSS 2.0, Atom and JSON Feed autodiscovery from HTML, context-aware feed prioritization, conditional HTTP requests with `ETag`/`Last-Modified`, and `304 Not Modified`. Feed-entry URLs do not bypass crawler safety or relevance policy.

### `spriditis/search`
Provider-neutral `SearchProvider`, query generation, search-result models, FakeSearchProvider for tests and SearXNG provider.

3.3.0-alpha.2 further hardens this layer with transient-error retry/backoff, `Retry-After`, structured provider errors and result deduplication across queries. `search-check` validates provider configuration before a full crawl.

Search results must not bypass Domain Registry or crawler safety policy.

### `spriditis/extraction`
Converts source HTML and structured metadata into `MarketEntity`. Structured evidence is preferred before AI enrichment.

### `spriditis/sources`
Source-specific adapters isolate site quirks from crawler core.

### `spriditis/ai`
Optional AI enrichment. Crawling/extraction must remain usable without AI.

### `spriditis/storage`
SQLite persistence and schema evolution. Default DB:
```text
data/spriditis.db
```

### `spriditis/reports`
Human-readable reports.

### `spriditis/api`
Service boundary for future UI/API consumers. UI should not import crawler internals directly.

## Domain Registry

States:
- `candidate`;
- `active`;
- `blocked`;
- `rejected`;
- `failed`.

Discovery events preserve provenance: source URL, target URL, relevance signals, action, reason and timestamp.

Since 3.3.0-alpha.3, Domain Registry state is hydrated from SQLite **before** discovery decisions for a new run. `blocked` and `rejected` remain sticky, `active` domains are recognized as known, while run-local page/entity counters start at zero so historical totals are not replayed.

## Research Memory direction

Planned lineage:

```text
query
 ↓
provider
 ↓
domain
 ↓
HTML link / sitemap / feed
 ↓
page
 ↓
extraction method
 ↓
entity
 ↓
observation
 ↓
change
```

Important principle: **every important decision should be explainable.** This makes `explain` and `trace` natural interfaces over Research Memory.

## Feed state and HTTP resource state

RSS/Atom/JSON Feed data is not stored as random columns in `domains`. One domain may expose multiple feeds, so 3.3.0-alpha.3 uses a dedicated 1:N `feeds` table (database schema v5).

Feed state:
- feed URL;
- feed type;
- status;
- ETag;
- Last-Modified;
- last entry id;
- last published;
- last checked/success;
- counters/error.

Long term, `ETag`/`Last-Modified` can become generic per-resource fetch-state metadata for feeds, sitemaps and ordinary pages.

## Safety boundaries

- supported HTTP/HTTPS schemes only;
- localhost/private/link-local protection;
- blocked hosts/paths;
- binary/static filtering;
- redirect controls;
- robots policy;
- page/domain/depth budgets.

## Design principles

1. Source facts before AI interpretation.
2. AI is optional enrichment, not the source of truth.
3. Discovery decisions are auditable and explainable.
4. Budgets and safety rules are explicit.
5. The public core stays generic.
6. Research Memory is built on SQLite before adding heavy infrastructure.
7. Speed must not weaken politeness or safety.
