# Sprīdītis — arhitektūra / Architecture

Pašreizējā publiskā bāze / Current public baseline: **3.3.0-alpha.10 — Async crawler + adaptive politeness**  
Nākamais aktīvais posms / Next active milestone: **vēl nav izvēlēts / not selected yet**

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
      ├── opt-in bounded async prefetch
      ├── retry budgets + adaptive politeness
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
Change Detection
             ↓
Watch mode
  ├── coverage-aware comparison
  ├── change-only JSONL
  └── cycle/change hooks
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
Avota HTML un strukturēto metadatu pārvēršana `MarketEntity`. Strukturēti pierādījumi ir prioritāri pirms MI enrichment. Alpha7 prioritizē JSON-LD → schema.org microdata → source adapter/OpenGraph → konservatīvu DOM fallback. Katrs atbalstītais lauks var glabāt atsevišķu `ExtractionEvidence` ar value, source URL, extraction method, confidence, evidence un extracted_at.

### `spriditis/sources`
Avotiem specifiski adapteri, izolējot konkrētas vietnes īpatnības no crawlera kodola.

### `spriditis/ai`
Izvēles MI enrichment. Crawler/extraction plūsmai jāstrādā arī bez MI.

### `spriditis/storage`
SQLite persistence un schema evolution. Alpha4 izmanto DB schema v6 un pievieno `page_visits` tabulu Research Memory lineage auditam. Alpha5 pāriet uz DB schema v7 un pievieno `adaptive_decisions` tabulu izskaidrojamai adaptīvo lēmumu secībai. Alpha6 izmanto DB schema v10 un pievieno canonical `entity_clusters`, `entity_cluster_members`, `entity_resolution_events` un `entity_cluster_merge_events` slāņus, saglabājot source-specific `entities` un `observations` kā pierādījumu avotu. Alpha7 pāriet uz DB schema v11 un pievieno `entities.field_evidence_json` current entity provenance glabāšanai; vēsturiskais provenance paliek katrā `observations.snapshot_json`. Esošie `runs` search skaitītāji tiek izmantoti arī duplicate-rate atmiņai, tāpēc šim signālam nav vajadzīga paralēla dublējoša tabula.

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

## Entity Resolution — 3.3.0-alpha.6 released

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

## Fallback Extraction + Evidence Confidence — 3.3.0-alpha.7 released

Alpha7 paplašina deterministisko extraction slāni un padara katra fakta provenance auditējamu.

Extraction plūsma:

```text
Page HTML
   ↓
JSON-LD
   ↓
schema.org microdata
   ↓
source adapter / OpenGraph
   ↓
conservative DOM fallback
   ↓
MarketEntity + field_evidence
   ↓
current entity persistence (schema v11)
   ├── entities.field_evidence_json
   └── observations.snapshot_json (historical)
   ↓
Evidence Quality inspection
```

Galvenās robežas:

- `MarketEntity.confidence` paliek AI/enrichment confidence; extraction confidence ir atsevišķs field-level signāls;
- direct structured facti saņem augstāku confidence nekā default/fallback vērtības;
- DOM fallback tiek aktivizēts tikai tad, ja strukturētie ekstraktori nav atraduši entity;
- DOM fallback prasa title + semantisku cenu + explicit valūtu + produkta konteksta signālu;
- default `EUR` tiek saglabāts kā explicit `default:EUR` evidence ar zemāku confidence;
- source adapteri izmanto to pašu `ExtractionEvidence` līgumu;
- current entity provenance tiek atjaunināts `field_evidence_json`, bet iepriekšējie observation snapshots netiek pārrakstīti;
- migrētām vecām entity rindām provenance netiek rekonstruēts no minējumiem — lauks paliek `{}`;
- Evidence Quality lieto auditējamus high/medium/low bandus un atsevišķi uzskaita missing, mismatched/stale un default/inferred laukus;
- Evidence Quality neveido vienu opaque score vai average confidence;
- `explain-cluster` rāda current field evidence un quality summary;
- `evidence-quality --project ... [--details]` dod projekta un entity līmeņa auditu;
- target-cluster-aware GTIN hard veto nepieļauj automātisku linku, ja vienā kandidāta clusterī vienlaikus ir strong match un GTIN conflict; nesaistīts atšķirīgs GTIN pats par sevi nav conflict.

DB schema v11 papildina alpha6 canonical Entity Resolution slāni, nezaudējot vēsturisko observation provenance.

Pilnais alpha7 regression gate ir izpildīts: **43/43 deterministiskie testi iziet**.

## Change Detection — 3.3.0-alpha.8 released

Alpha8 pārvērš vēsturiskos observation, page-visit un feed snapshot datus auditējamos notikumos.

Salīdzināšanas pamats:

```text
historical observation snapshots
        + historical page visits
        + historical feed snapshots
        + current canonical membership
                    ↓
              ChangeEvent
```

Galvenās robežas:

- entity un source izmaiņas tiek vērtētas canonical identity kontekstā, nepārrakstot vēsturiskos observation faktus;
- cenu izmaiņas tiek salīdzinātas tikai vienam un tam pašam source entity ar vienādu valūtu;
- seller/description/image izmaiņām nepieciešams atbilstošs field evidence ar confidence vismaz `0.70`;
- domain health izmanto reachable/failed/unknown semantiku, kur HTTP 4xx ir reachable, bet robots/safety-only nav failure;
- feed lifecycle tiek auditēts caur schema v12 `feed_snapshots`;
- `FEED_DISAPPEARED` rodas tikai tad, ja vēlākajā runā attiecīgais domēns patiešām bija reachable;
- feed change evidence glabā historical snapshot ID, ko var atrisināt caur `trace`;
- `diff --project ... --run-a ... --run-b ... [--details]` rāda before/after/evidence un explicit comparison basis.

Pilnais alpha8 regression gate ir izpildīts: **48/48 deterministiskie testi iziet**.

## Watch mode — 3.3.0-alpha.9 released

Alpha9 pārvērš alpha8 Change Detection par atkārtojamu, konservatīvu monitoringa plūsmu, nepievienojot smagu background infrastruktūru.

Plūsma:

```text
completed run N
      ↓
Research Memory / Domain / Feed state
      ↓
next research cycle
      ↓
completed run N+1
      ↓
coverage-aware comparison
      ├── verified ChangeEvent[]
      └── suppressed_uncertain[]
      ↓
WatchCycleResult
      ├── change-only JSONL
      ├── cycle hooks
      └── change hooks (verified event payload)
```

Galvenās robežas:

- `compare_with_previous_run` Watch ceļā lieto coverage-aware semantiku, bet tiešais `compare_runs` pēc noklusējuma saglabā alpha8 raw historical diff uzvedību;
- `NEW_ENTITY` prasa, lai attiecīgais source URL būtu salīdzināmi pārbaudīts iepriekšējā runā;
- `ENTITY_DISAPPEARED` prasa salīdzināmu source URL pārbaudi vēlākajā runā;
- `SOURCE_CHANGED` pievienotajiem/noņemtajiem avotiem prasa salīdzināmu coverage;
- nepietiekams coverage tiek saglabāts kā auditējams `suppressed_uncertain`, nevis pārvērsts par change eventu;
- baseline un no-change cikli nerada JSONL heartbeat rindas;
- cycle hook tiek izsaukts pēc katra pabeigta cikla; change hook tikai tad, ja ir verificētas izmaiņas;
- change hook saņem tos pašus verificētos eventus, ko Watch rāda un eksportē JSONL;
- hook adaptera kļūme ir izolēta un nepadara jau pabeigtu research run par neveiksmīgu;
- atkārtots Watch cikls no SQLite ielādē feed state, Domain Registry, query memory un source profiles;
- feed conditional refresh atkārtoti izmanto `ETag`/`Last-Modified`; `304 Not Modified` paliek `active` un neveido viltus lifecycle eventu;
- Research Memory ietekmē nākamā cikla query/source prioritāti un paliek auditējama Adaptive Decision Trace.

Alpha9 apzināti **neievieš** daemon scheduler, background-job queue vai webhook serveri. Publiskā kodola automatizācijas robeža ir bounded CLI loop + JSONL + hook kontrakti.

Pilnais alpha9 regression gate ir izpildīts: **55/55 deterministiskie testi iziet**.

## Async crawler + adaptive politeness — 3.3.0-alpha.10 released

Alpha10 paātrina tīkla gaidīšanu, nepārvēršot research-state mutācijas par paralēlu sacensību.

Plūsma:

```text
URL Frontier
      ↓
deterministic fetch-wave planning
  ├── total/per-domain budget reservation
  ├── preserve priority/tie order
  └── bounded pending work
      ↓
domain-aware async coordinator
  ├── global concurrency cap
  └── per-domain concurrency cap
      ↓
thread-local requests transport
(asyncio.to_thread)
      ↓
retry + adaptive politeness
  ├── Retry-After
  ├── bounded exponential backoff
  └── per-domain pressure/recovery delay
      ↓
prefetch cache
      ↓
URL restored to Frontier
      ↓
sequential deterministic processing
(Domain Registry / extraction / decisions)
```

Galvenās robežas:

- async režīms ir opt-in; sequential crawleris paliek noklusējuma baseline;
- viena domēna gaidītāji nedrīkst aizņemt visus globālos execution slotus;
- wave planneris rezervē total/per-domain crawl capacity pirms fetch un saglabā sākotnējo frontier tie-order;
- prefetched URL tiek atgriezts frontierī, tāpēc jaunatklāts augstākas prioritātes URL var to apsteigt;
- `requests.Session` netiek koplietots starp worker threadiem — transports lieto thread-local session;
- transient pressure ir `408/429/500/502/503/504` vai network error; retry skaitu ierobežo explicit budžets;
- `Retry-After` ir prioritārs pār exponential backoff un tiek capped;
- adaptīvā politeness state ir per-domain un run-scoped: pressure palielina delay, success to samazina uz bāzi;
- coordinator statiskais delay async crawler ceļā ir 0, lai pacing netiktu piemērots divreiz;
- transporta kļūme netiek klusām pārfetchota caur sync session;
- run diagnostics atdala logical fetch jobs no faktiskajiem HTTP attempts/retries;
- robots, URL/private-network safety, budgets un provenance semantika paliek esošajā crawlera kontrolē;
- alpha10 nemaina SQLite schema.

Validācija:

- async foundation testi pārbauda coordinator fairness, transport isolation un deterministic wave planning;
- retry/politeness tests pārbauda `Retry-After`, exponential backoff, hard retry budget, non-retryable HTTP un domēnu neatkarību;
- integrācijas tests pārbauda async main-page fetch bez sync fallback, deterministisku `PageVisit` secību un auditējamas kļūmes;
- sequential/async salīdzinājums ar identisku URL kopu pierāda vienādu observable crawl semantiku un izmērāmu paralēla I/O ātruma ieguvumu;
- pilnais regression gate: **60/60 deterministiskie testi iziet**.

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
Converts source HTML and structured metadata into `MarketEntity`. Structured evidence is preferred before AI enrichment. Alpha7 prioritizes JSON-LD → schema.org microdata → source adapter/OpenGraph → conservative DOM fallback. Each supported field can preserve a separate `ExtractionEvidence` with value, source URL, extraction method, confidence, evidence and extracted_at.

### `spriditis/sources`
Source-specific adapters isolate site quirks from crawler core.

### `spriditis/ai`
Optional AI enrichment. Crawling/extraction must remain usable without AI.

### `spriditis/storage`
SQLite persistence and schema evolution. Alpha4 uses database schema v6 and adds a `page_visits` table for Research Memory lineage auditing. Alpha5 moves to database schema v7 and adds an `adaptive_decisions` table for explainable adaptive-decision sequences. Alpha6 uses database schema v10 and adds canonical `entity_clusters`, `entity_cluster_members`, `entity_resolution_events` and `entity_cluster_merge_events` layers while preserving source-specific `entities` and `observations` as evidence. Alpha7 moves to database schema v11 and adds `entities.field_evidence_json` for current entity provenance while historical provenance remains embedded in each `observations.snapshot_json`. Alpha8 moves to database schema v12 and adds run-scoped `feed_snapshots` for historical feed comparison and traceable change evidence. Existing search counters in `runs` also back duplicate-rate memory, avoiding a parallel duplicate source of truth.

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

## Entity Resolution — 3.3.0-alpha.6 released

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

## Fallback Extraction + Evidence Confidence — 3.3.0-alpha.7 released

Alpha7 extends deterministic extraction and makes field-level provenance auditable.

Extraction flow:

```text
Page HTML
   ↓
JSON-LD
   ↓
schema.org microdata
   ↓
source adapter / OpenGraph
   ↓
conservative DOM fallback
   ↓
MarketEntity + field_evidence
   ↓
current entity persistence (schema v11)
   ├── entities.field_evidence_json
   └── observations.snapshot_json (historical)
   ↓
Evidence Quality inspection
```

Key boundaries:

- `MarketEntity.confidence` remains AI/enrichment confidence; extraction confidence is a separate field-level signal;
- direct structured facts receive higher confidence than default/fallback values;
- DOM fallback only runs when structured extractors produced no entity;
- DOM fallback requires title + semantic price + explicit currency + product-context evidence;
- default `EUR` is stored as explicit `default:EUR` evidence with lower confidence;
- source adapters use the same `ExtractionEvidence` contract;
- current entity provenance is updated in `field_evidence_json`, while prior observation snapshots remain immutable;
- migrated historical entity rows do not receive invented provenance and remain `{}`;
- Evidence Quality uses auditable high/medium/low bands and separately reports missing, mismatched/stale and default/inferred fields;
- Evidence Quality deliberately does not collapse facts into one opaque score or average confidence;
- `explain-cluster` exposes current field evidence and its quality summary;
- `evidence-quality --project ... [--details]` provides project/entity inspection;
- target-cluster-aware GTIN hard veto prevents automatic linking when one candidate cluster contains both a strong match and a GTIN conflict; an unrelated different GTIN alone is not a conflict.

Database schema v11 extends the alpha6 canonical Entity Resolution layer without losing historical observation provenance.

The complete alpha7 regression gate passed: **43/43 deterministic tests**.

## Change Detection — 3.3.0-alpha.8 released

Alpha8 turns historical observation, page-visit and feed-snapshot data into auditable events.

Comparison basis:

```text
historical observation snapshots
        + historical page visits
        + historical feed snapshots
        + current canonical membership
                    ↓
              ChangeEvent
```

Key boundaries:

- entity and source changes are evaluated in canonical-identity context without rewriting historical observation facts;
- price changes are compared only for the same source entity and matching currency;
- seller/description/image changes require matching field evidence with confidence of at least `0.70`;
- domain health uses reachable/failed/unknown semantics, where HTTP 4xx is reachable while robots/safety-only outcomes are not failures;
- feed lifecycle is audited through schema-v12 `feed_snapshots`;
- `FEED_DISAPPEARED` is emitted only when the feed's domain was actually reachable in the later run;
- feed change evidence retains historical snapshot IDs resolvable through `trace`;
- `diff --project ... --run-a ... --run-b ... [--details]` exposes before/after/evidence plus the explicit comparison basis.

The complete alpha8 regression gate passed: **48/48 deterministic tests**.

## Watch mode — 3.3.0-alpha.9 released

Alpha9 turns alpha8 Change Detection into a repeatable, conservative monitoring flow without introducing heavy background infrastructure.

Flow:

```text
completed run N
      ↓
Research Memory / Domain / Feed state
      ↓
next research cycle
      ↓
completed run N+1
      ↓
coverage-aware comparison
      ├── verified ChangeEvent[]
      └── suppressed_uncertain[]
      ↓
WatchCycleResult
      ├── change-only JSONL
      ├── cycle hooks
      └── change hooks (verified event payload)
```

Key boundaries:

- `compare_with_previous_run` uses coverage-aware Watch semantics while direct `compare_runs` keeps alpha8 raw historical diff behavior by default;
- `NEW_ENTITY` requires comparable prior-run rechecking of the relevant source URL;
- `ENTITY_DISAPPEARED` requires comparable source-URL rechecking in the later run;
- `SOURCE_CHANGED` requires comparable coverage for added/removed sources;
- insufficient coverage is retained as auditable `suppressed_uncertain` rather than promoted to a change event;
- baseline and no-change cycles emit no JSONL heartbeat records;
- cycle hooks run after every completed cycle; change hooks run only for verified changes;
- change hooks receive the same verified events shown by Watch and exported to JSONL;
- hook-adapter failures are isolated and do not retroactively fail an already completed research run;
- repeated Watch cycles hydrate feed state, Domain Registry, query memory and source profiles from SQLite;
- feed refresh reuses `ETag`/`Last-Modified`; `304 Not Modified` remains `active` and does not create a false lifecycle event;
- Research Memory affects next-cycle query/source priority and remains visible in the Adaptive Decision Trace.

Alpha9 deliberately does **not** include a daemon scheduler, background-job queue or webhook server. The public-core automation boundary is a bounded CLI loop + JSONL + hook contracts.

The complete alpha9 regression gate passed: **55/55 deterministic tests**.

## Async crawler + adaptive politeness — 3.3.0-alpha.10 released

Alpha10 overlaps network waiting without turning research-state mutation into a parallel race.

Flow:

```text
URL Frontier
      ↓
deterministic fetch-wave planning
  ├── total/per-domain budget reservation
  ├── preserve priority/tie order
  └── bounded pending work
      ↓
domain-aware async coordinator
  ├── global concurrency cap
  └── per-domain concurrency cap
      ↓
thread-local requests transport
(asyncio.to_thread)
      ↓
retry + adaptive politeness
  ├── Retry-After
  ├── bounded exponential backoff
  └── per-domain pressure/recovery delay
      ↓
prefetch cache
      ↓
URL restored to Frontier
      ↓
sequential deterministic processing
(Domain Registry / extraction / decisions)
```

Key boundaries:

- async mode is opt-in; the sequential crawler remains the default baseline;
- same-domain waiters cannot consume all global execution slots;
- the wave planner reserves total/per-domain crawl capacity before fetch and preserves original frontier tie order;
- prefetched URLs return to the frontier, so newly discovered higher-priority work can still overtake them;
- `requests.Session` is not shared across worker threads; the transport uses thread-local sessions;
- transient pressure is `408/429/500/502/503/504` or a network error, with an explicit retry budget;
- `Retry-After` takes precedence over exponential backoff and is capped;
- adaptive politeness is per-domain and run-scoped: pressure raises delay while successful responses decay it toward the base;
- the coordinator's static delay is zero in the integrated async path so pacing is not applied twice;
- transport failures are not silently fetched again through the synchronous session;
- run diagnostics distinguish logical fetch jobs from actual HTTP attempts/retries;
- robots, URL/private-network safety, crawl budgets and provenance remain under the existing crawler policy;
- alpha10 does not change the SQLite schema.

Validation:

- async foundation tests cover coordinator fairness, transport isolation and deterministic wave planning;
- retry/politeness coverage verifies `Retry-After`, exponential backoff, hard retry budgets, non-retryable HTTP and domain independence;
- crawler integration verifies async main-page fetch without sync fallback, deterministic `PageVisit` ordering and auditable failures;
- sequential/async comparison over an identical URL set proves equivalent observable crawl semantics plus measurable parallel-I/O speedup;
- complete regression gate: **60/60 deterministic tests pass**.

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
