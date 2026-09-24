# Sprīdītis — arhitektūra / Architecture

Pašreizējā publiskā bāze / Current public baseline: **3.3.0-alpha.5 — Adaptive Expedition**  
Pilnībā validēts kandidāts / Fully validated candidate: **3.3.0-alpha.6 — Entity Resolution**

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
Research Memory
(memory / explain / trace)
             ↓
Reports / service consumers
```

## Galvenie slāņi

### `spriditis/core`
Atkārtoti izmantojamie modeļi: `ResearchProject`, `MarketEntity`, run struktūras, `PageVisit`, Domain Registry ieraksti un discovery eventi. Alpha4 `PageVisit` glabā URL/final URL, domēnu, source URL/type, depth, priority, outcome, HTTP statusu, content type un timestamp, lai page lineage būtu auditējams.

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
SQLite persistence un schema evolution. Alpha4 izmanto DB schema v6 un pievieno `page_visits` tabulu Research Memory lineage auditam. Alpha5 pāriet uz DB schema v7 un pievieno `adaptive_decisions` tabulu izskaidrojamai adaptīvo lēmumu secībai. Alpha6 release candidate izmanto DB schema v10 un pievieno canonical `entity_clusters`, `entity_cluster_members`, `entity_resolution_events` un `entity_cluster_merge_events` slāņus, saglabājot source-specific `entities` un `observations` kā pierādījumu avotu. Esošie `runs` search skaitītāji tiek izmantoti arī duplicate-rate atmiņai, tāpēc šim signālam nav vajadzīga paralēla dublējoša tabula.

Noklusējuma DB:
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

## Research Memory — 3.3.0-alpha.4

Alpha4 ievieš auditējamu pieredzes slāni virs jau esošajiem run, Domain Registry, feed, entity un observation datiem.

Ieviestais lineage:

```text
query / seed
 ↓
provider / discovery source
 ↓
domain
 ↓
HTML link / sitemap / feed
 ↓
page visit
 ↓
extraction
 ↓
entity
 ↓
observation
```

Research Memory saglabā atsevišķus signālus, nevis vienu opaque score:

- query `productive_domain_rate`;
- source entity yield;
- HTTP success rate;
- crawl runs / productive runs / productive-run rate;
- observation count un `last_useful_at`;
- search raw / unique / duplicate / filtered rezultātus un duplicate rate;
- `last_seen`, `last_crawled`, `last_feed_success`, `last_useful_at` un no tiem atvasinātus freshness vecumus;
- konfigurējamu stale slieksni un skaidru freshness basis;
- discovery provenance un page lineage.

`memory` apkopo query/search/source signālus. `explain` parāda viena domēna profilu, freshness pamatu, discovery evidence, page lineage un feed stāvokli. `trace` parāda viena run provenance; pēc noklusējuma atkārtoti discovery eventi tiek grupēti lasāmībai, bet `--full` saglabā raw audita skatu.

Svarīga robeža: alpha4 **krāj un izskaidro** pieredzi. Automātiska šo signālu izmantošana prioritizācijai un stopping lēmumiem pieder alpha5 Adaptive Expedition.

Svarīgs princips: **katram nozīmīgam lēmumam jābūt izskaidrojamam.**

## Adaptive Expedition — 3.3.0-alpha.5

Alpha5 sāk **patērēt** alpha4 Research Memory un lokālos relevance signālus, bet saglabā tos atsevišķi auditējamus.

Adaptīvā plūsma:

```text
Research Memory
  ├── query productive-domain history
  └── source productivity/freshness
             ↓
Query priority
             ↓
Search result priority
  ├── source-memory band
  ├── local BM25
  ├── title/path/domain matches
  └── negative-keyword signal
             ↓
Controlled discovery
  ├── discovery_depth
  ├── per-depth activation budgets
  └── source-diversity priority penalty
             ↓
Adaptive stopping
  ├── saturation streak
  └── diminishing-returns streak
             ↓
Adaptive Decision Trace
```

Galvenās robežas:

- configured query vienmēr paliek priekšā automātiski ģenerētiem query;
- produktīva query/source vēsture palīdz prioritizēt, bet neveido vienu opaque quality score;
- nepārbaudīti avoti paliek eksplorējami un netiek automātiski sodīti kā neproduktīvi;
- `depth` apzīmē lapas navigācijas dziļumu, bet `discovery_depth` — starpdomēnu hop skaitu;
- source diversity ir soft frontier penalty, nevis entity dzēšana;
- adaptive stopping ir opt-in ar `0 = disabled` logiem;
- katrs nozīmīgais adaptīvais lēmums tiek pievienots `AdaptiveDecision` un persistēts DB schema v7 `adaptive_decisions` tabulā;
- `trace --run N` parāda lēmumu secību un signālus kopā ar page/discovery/observation provenance.

## Entity Resolution — 3.3.0-alpha.6 validated release candidate

Alpha6 ievieš atsevišķu identity-resolution slāni **virs** source-specific entity/observation pierādījumiem. Canonical clusteri neaizstāj avota rindas un neizdzēš observations.

Plūsma:

```text
Structured Extraction
      ↓
source-specific MarketEntity
      ↓
identity signals
(GTIN / maker+model / maker+MPN / source SKU)
      ↓
deterministic resolver
      ↓
canonical entity cluster
      ├── source entity A
      ├── source entity B
      └── observations remain source-specific
      ↓
resolution audit
      ├── linked
      ├── new_cluster
      ├── deferred_ambiguous
      └── created_separate / identity_conflict
      ↓
review-queue
      ↓
guarded explicit merge
```

Galvenās robežas:

- GTIN tiek izmantots tikai pēc check-digit validācijas;
- maker+model un maker+MPN ir strong cross-source identitātes signāli;
- SKU ir strong signāls tikai viena source-domain kontekstā;
- vienāds normalized title viens pats nekad neveic cross-source merge;
- cross-source SKU viens pats ir tikai supporting signāls;
- bridge entity, kas strong-matcho vairākus atsevišķus clusterus, tiek `deferred_ambiguous`;
- explicit merge prasa vismaz vienu strong identity match un nevienu strong conflict;
- GTIN konflikts bloķē merge arī manuālā workflow;
- rejected merge membership nemaina;
- merge’ots source clusteris paliek vēsturē ar `merged_into_cluster_key` / `merged_at`;
- review queue ir atvasināts skats no auditējamiem eventiem un aktīvā cluster stāvokļa, nevis paralēla statusu tabula;
- `explain-cluster` apkopo members, identity signālus, observations, resolution history, merge history un review items.

DB schema v10 uztur canonical clusterus, resolution auditu un merge auditu, nezaudējot source provenance.

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
Research Memory
(memory / explain / trace)
             ↓
Reports / service consumers
```

## Core layers

### `spriditis/core`
Reusable models: `ResearchProject`, `MarketEntity`, run structures, `PageVisit`, Domain Registry records and discovery events. Alpha4 `PageVisit` preserves URL/final URL, domain, source URL/type, depth, priority, outcome, HTTP status, content type and timestamp so page lineage remains auditable.

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
SQLite persistence and schema evolution. Alpha4 uses database schema v6 and adds a `page_visits` table for Research Memory lineage auditing. Alpha5 moves to database schema v7 and adds an `adaptive_decisions` table for explainable adaptive-decision sequences. The alpha6 release candidate uses database schema v10 and adds canonical `entity_clusters`, `entity_cluster_members`, `entity_resolution_events` and `entity_cluster_merge_events` layers while preserving source-specific `entities` and `observations` as evidence. Existing search counters in `runs` also back duplicate-rate memory, avoiding a parallel duplicate source of truth.

Default DB:
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

## Research Memory — 3.3.0-alpha.4

Alpha4 implements an auditable experience layer over the existing run, Domain Registry, feed, entity and observation data.

Implemented lineage:

```text
query / seed
 ↓
provider / discovery source
 ↓
domain
 ↓
HTML link / sitemap / feed
 ↓
page visit
 ↓
extraction
 ↓
entity
 ↓
observation
```

Research Memory preserves separate signals instead of collapsing them into one opaque score:

- query `productive_domain_rate`;
- source entity yield;
- HTTP success rate;
- crawl runs / productive runs / productive-run rate;
- observation count and `last_useful_at`;
- raw / unique / duplicate / filtered search results and duplicate rate;
- `last_seen`, `last_crawled`, `last_feed_success`, `last_useful_at` and derived freshness ages;
- configurable stale threshold with an explicit freshness basis;
- discovery provenance and page lineage.

`memory` summarizes query/search/source signals. `explain` shows one domain's profile, freshness basis, discovery evidence, page lineage and feed state. `trace` exposes one run's provenance; repeated discovery events are grouped by default for readability while `--full` preserves the raw audit view.

The milestone boundary is deliberate: alpha4 **records and explains** experience. Automatic use of these signals for prioritization and stopping decisions belongs to alpha5 Adaptive Expedition.

Important principle: **every important decision should be explainable.**

## Adaptive Expedition — 3.3.0-alpha.5

Alpha5 begins to **consume** alpha4 Research Memory together with local relevance signals while keeping the underlying evidence separate and auditable.

Adaptive flow:

```text
Research Memory
  ├── query productive-domain history
  └── source productivity/freshness
             ↓
Query priority
             ↓
Search result priority
  ├── source-memory band
  ├── local BM25
  ├── title/path/domain matches
  └── negative-keyword signal
             ↓
Controlled discovery
  ├── discovery_depth
  ├── per-depth activation budgets
  └── source-diversity priority penalty
             ↓
Adaptive stopping
  ├── saturation streak
  └── diminishing-returns streak
             ↓
Adaptive Decision Trace
```

Key boundaries:

- configured queries always remain ahead of automatically generated queries;
- productive query/source history influences priority without collapsing into one opaque quality score;
- untested sources remain explorable and are not treated as historically nonproductive;
- `depth` is page-navigation depth while `discovery_depth` counts cross-domain hops;
- source diversity is a soft frontier penalty, not entity deletion;
- adaptive stopping is opt-in with `0 = disabled` windows;
- every important adaptive decision is appended as an `AdaptiveDecision` and persisted in the schema-v7 `adaptive_decisions` table;
- `trace --run N` exposes the decision sequence and signals alongside page/discovery/observation provenance.

## Entity Resolution — 3.3.0-alpha.6 validated release candidate

Alpha6 adds a dedicated identity-resolution layer **above** source-specific entity/observation evidence. Canonical clusters do not replace source rows and do not discard observations.

Flow:

```text
Structured Extraction
      ↓
source-specific MarketEntity
      ↓
identity signals
(GTIN / maker+model / maker+MPN / source SKU)
      ↓
deterministic resolver
      ↓
canonical entity cluster
      ├── source entity A
      ├── source entity B
      └── observations remain source-specific
      ↓
resolution audit
      ├── linked
      ├── new_cluster
      ├── deferred_ambiguous
      └── created_separate / identity_conflict
      ↓
review-queue
      ↓
guarded explicit merge
```

Key boundaries:

- GTIN is only used after check-digit validation;
- maker+model and maker+MPN are strong cross-source identity signals;
- SKU is strong only within one source-domain context;
- equal normalized title alone never performs cross-source merge;
- cross-source SKU alone is only a supporting signal;
- a bridge entity strongly matching multiple separate clusters becomes `deferred_ambiguous`;
- explicit merge requires at least one strong identity match and no strong conflict;
- GTIN conflict blocks merge even in the manual workflow;
- a rejected merge does not change membership;
- a merged source cluster remains historical through `merged_into_cluster_key` / `merged_at`;
- the review queue is derived from auditable events and live cluster state instead of a parallel status table;
- `explain-cluster` combines members, identity signals, observations, resolution history, merge history and review items.

Database schema v10 stores canonical clusters, resolution audit and merge audit without losing source provenance.

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
