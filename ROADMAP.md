# Sprīdītis — attīstības plāns / Roadmap

> **Virziens, nevis termiņu solījums.** Sprīdītis tiek attīstīts iteratīvi. Posms tiek uzskatīts par pabeigtu tikai tad, kad tā uzvedība ir pārbaudāma un iepriekšējie slāņi paliek stabili.  
> **Direction, not deadlines.** Sprīdītis is developed iteratively. A milestone is complete only when its behavior is testable and previous layers remain stable.

## Statusi / Status

- ✅ **Publicēts / Released** — publiski pieejams un ieviests / public implementation
- 🧪 **Validēšana / Validating** — lokāli ieviests, tiek pārbaudīts vai gatavots publicēšanai / implemented locally, under validation or publication preparation
- 🚧 **Nākamais darbā / Next in progress** — nākamais aktīvais posms / next active milestone
- 🧭 **Plānots / Planned** — apstiprināts attīstības virziens / accepted direction
- 🔭 **Vēlāk / Later** — noderīgs, bet apzināti atlikts / useful but deliberately deferred

## Pamatprincipi / Guiding principles

1. **Avotos balstīti fakti pirms MI interpretācijas / Source-backed facts before AI interpretation.**
2. **Research Memory pirms brute-force crawling.**
3. **Drošība, provenance un auditējamība ir arhitektūras īpašības / Safety, provenance and auditability are architectural features.**
4. **Katram svarīgam lēmumam jābūt izskaidrojamam / Every important decision should be explainable.**
5. **Priekšroka lokāliem, atvērtiem, pašhostējamiem un bezmaksas risinājumiem / Prefer local, open, self-hostable and zero-cost building blocks.**
6. **Maksas API var būt izvēles provideri, bet publiskais kodols nedrīkst būt no tiem atkarīgs / Paid APIs may be optional providers, never mandatory for the public core.**
7. **Vispirms gudrāks crawleris, tikai pēc tam masīva paralelizācija / Make the crawler smarter before making it massively distributed.**
8. **Labam pētījumam jāzina, kad apstāties / A good research run should know when to stop.**

---

# Latviski

## ✅ Pašreizējā publiskā bāze — 3.3.0-alpha.2

Ieviests un publiski pieejams:

- konfigurējams `ResearchProject`;
- universāls `MarketEntity`;
- JSON-LD un OpenGraph ekstrakcija;
- avotu adapteri;
- izvēles batch MI analīze ar lokālu fallback;
- SQLite observations;
- Domain Registry;
- kontrolēts vairāku domēnu discovery;
- sitemap discovery;
- URL/SSRF drošības politika;
- `robots.txt`;
- crawl budžeti;
- discovery audits;
- provider-neatkarīgs `SearchProvider`;
- deterministisks Expedition query ģenerators;
- FakeSearchProvider testiem;
- SearXNG provideris;
- zero-seed Expedition;
- query/provider provenance;
- search skaitītāji;
- integrācijas tests `search → activation → crawl`.

## ✅ 3.3.0-alpha.2 — SearchProvider stabilizācija

Publicēts un validēts.

- retry/backoff transient kļūdām;
- `Retry-After`;
- strukturētas SearchProvider kļūdas;
- HTTP status/retryability metadata;
- search rezultātu dedupe starp query;
- raw / unique / duplicate skaitītāji;
- nederīgu non-HTTP(S) rezultātu agrīna atmešana;
- DB schema v4;
- `search-check`;
- reliability un dedupe testi.

## 🚧 3.3.0-alpha.3 — Feed Discovery & Incremental Monitoring

Mērķis: pārvērst katru vērtīgu domēnu par iespējamu efektīvu atkārtotas discovery avotu.

- RSS 2.0;
- Atom;
- JSON Feed;
- HTML `<link rel="alternate">` autodiscovery;
- konservatīvi biežāko feed URL fallbacki;
- atsevišķs feed state modelis;
- feed provenance;
- feed → safety → relevance → dedupe → frontier plūsma;
- per-resource `ETag` / `Last-Modified` pamats;
- `304 Not Modified`;
- `last_entry_id`, `last_published`, `last_checked`, `last_success`;
- incremental repeated-run testi.

## 🧭 3.3.0-alpha.4 — Research Memory

Mērķis: atcerēties ne tikai atrastos datus, bet arī pētījuma procesa efektivitāti.

- query yield;
- source/domain yield;
- useful-entity yield;
- duplicate rate;
- source success rate;
- freshness/staleness;
- discovery provenance metrics;
- source profiles;
- source/query value signāli;
- `spriditis explain` — kāpēc domēns/query/entity tika aktivizēts, noraidīts vai iegūts;
- `spriditis trace` — query → provider → domain → discovery path → page → extraction → entity → observation.

Jaunajām metrikām jābūt izskaidrojamām; viens “mistisks score” nedrīkst aizstāt atsevišķos signālus.

## 🧭 3.3.0-alpha.5 — Adaptive Expedition

Mērķis: izvēlēties labākos pētījuma ceļus bez obligāta maksas MI.

- BM25/lokāla teksta relevance;
- title/path/domain signāli;
- vēsturiskā query yield prioritizācija;
- source profile signāli;
- coverage saturation;
- diminishing-returns stopping;
- `STOP_REASON`: `max_pages`, `max_domains`, `diminishing_returns`, `saturation_reached`, `budget_exhausted`;
- kontrolēts multi-hop discovery;
- `max_discovery_depth`;
- per-depth budgets;
- soft entity diversity limits, lai viens milzu avots neaizēnotu pārējos.

## 🧭 3.3.0-alpha.6 — Entity Resolution

Mērķis: vienu un to pašu reālās pasaules produktu/pakalpojumu attēlot kā vienu entity ar vairākiem avotiem.

Primārie signāli:
- GTIN / EAN;
- manufacturer + model;
- SKU, kur tas ir jēgpilni;
- normalized title.

Papildu signāli:
- cenu diapazons;
- fuzzy title similarity, piemēram, ar `rapidfuzz`, tikai kā papildsignāls.

## 🧭 3.3.0-alpha.7 — Fallback Extraction + Evidence Confidence

Ekstrakcijas prioritāte:

1. JSON-LD;
2. schema.org microdata;
3. OpenGraph;
4. avota adapteris;
5. deterministiskas DOM heuristikas;
6. izvēles MI ekstraktors tikai kā pēdējais variants.

Katram faktam jāspēj saglabāt:
- value;
- source URL;
- extraction method;
- confidence;
- extracted_at;
- evidence/provenance.

## 🧭 3.3.0-alpha.8 — Change Detection

Mērķis: pārvērst observations jēgpilnos notikumos.

- `PRICE_DROP`;
- `PRICE_INCREASE`;
- `NEW_ENTITY`;
- `ENTITY_DISAPPEARED`;
- `SOURCE_CHANGED`;
- `DOMAIN_FAILED`;
- `DOMAIN_RECOVERED`;
- feed parādījās/pazuda;
- `spriditis diff --run A --run B`.

Secība paliek apzināta: **Entity Resolution → Evidence Confidence → Change Detection**.

## 🧭 3.3.0-alpha.9 — Watch mode

- incremental repeated research;
- `spriditis watch`;
- change-only kopsavilkumi;
- scheduling hooks;
- notification hooks;
- feed/ETag-aware refresh;
- Research Memory atkārtota izmantošana;
- JSONL eksports kā vienkāršs integrācijas formāts.

## 🧭 3.3.0-alpha.10 — Async crawler + adaptive politeness

Tikai pēc tam, kad research loģika jau prot būt selektīva.

- bounded async requests;
- per-domain semaphore 1–2 kā konservatīvs sākumpunkts;
- global concurrency cap;
- adaptive delay;
- retry budgets;
- backpressure;
- bez drošības/robots/private-network aizsardzības vājināšanas.

## 🔭 Vēlāk / Backlog

- papildu bezmaksas/self-hostable SearchProvider adapteri;
- papildu price/currency/VAT normalizācija;
- attēli un specifikāciju tabulas;
- augstas vērtības avotu adapteri;
- CSV/Parquet eksports;
- FastAPI;
- projektu/run UI;
- scheduler/background jobs;
- webhooks/notifikācijas;
- stricter typing;
- plašāks testu pārklājums;
- CI/CD;
- Docker;
- projekta JSON Schema;
- plugin entry points;
- papildu MI provideri un lokālie modeļi kā izvēles slānis.

## Ko apzināti neprioritizējam

- Redis/RabbitMQ/distributed queue pirms ir reāla vajadzība;
- PostgreSQL, kamēr SQLite nav izmērīts bottleneck;
- Playwright kā noklusējuma risinājumu visām lapām;
- smagus agent framework;
- hostētus dashboardus pirms research kodola nobriešanas;
- obligātus maksas search vai AI API.

## Sprīdīša paredzētā atšķirība

> **Iedod man pētījuma mērķi. Es atradīšu avotus, atcerēšos, kuri ceļi bija vērtīgi, izvairīšos no atkārtota darba, pamanīšu nozīmīgas izmaiņas un nākamajā reizē pētīšu selektīvāk.**

Tas ir **Research Memory + Adaptive Discovery + Evidence Confidence + Incremental Monitoring**.

---

# English

## ✅ Current public baseline — 3.3.0-alpha.2

Implemented and public:

- configurable `ResearchProject`;
- generic `MarketEntity`;
- JSON-LD and OpenGraph extraction;
- source adapters;
- optional batched AI enrichment with local fallback;
- SQLite observations;
- Domain Registry;
- controlled multi-domain discovery;
- sitemap discovery;
- URL/SSRF safety policy;
- `robots.txt`;
- crawl budgets;
- discovery audit trail;
- provider-neutral `SearchProvider`;
- deterministic Expedition query generation;
- offline fake provider;
- SearXNG provider;
- zero-seed Expedition;
- query/provider provenance;
- search counters;
- `search → activation → crawl` integration coverage.

## ✅ 3.3.0-alpha.2 — SearchProvider hardening

Published and validated.

- retry/backoff for transient provider failures;
- `Retry-After`;
- structured SearchProvider errors;
- HTTP status/retryability metadata;
- result dedupe across queries;
- raw / unique / duplicate counters;
- early rejection of invalid non-HTTP(S) results;
- database schema v4;
- `search-check`;
- reliability and dedupe tests.

## 🚧 3.3.0-alpha.3 — Feed Discovery & Incremental Monitoring

Goal: turn every useful domain into a possible efficient recurring discovery source.

- RSS 2.0;
- Atom;
- JSON Feed;
- HTML `<link rel="alternate">` autodiscovery;
- conservative common-feed-path fallback;
- dedicated feed-state model;
- feed provenance;
- feed → safety → relevance → dedupe → frontier;
- per-resource `ETag` / `Last-Modified` foundation;
- `304 Not Modified`;
- `last_entry_id`, `last_published`, `last_checked`, `last_success`;
- incremental repeated-run tests.

## 🧭 3.3.0-alpha.4 — Research Memory

Goal: remember not only collected data, but the effectiveness of the research process itself.

- query yield;
- source/domain yield;
- useful-entity yield;
- duplicate rate;
- source success rate;
- freshness/staleness;
- discovery provenance metrics;
- source profiles;
- source/query value signals;
- `spriditis explain`;
- `spriditis trace` for query → provider → domain → discovery path → page → extraction → entity → observation.

Metrics should stay explainable; one opaque “magic score” must not replace the underlying signals.

## 🧭 3.3.0-alpha.5 — Adaptive Expedition

Goal: choose better research paths without requiring paid AI.

- BM25/local text relevance;
- title/path/domain signals;
- historical query-yield prioritization;
- source-profile signals;
- coverage saturation;
- diminishing-returns stopping;
- `STOP_REASON`: `max_pages`, `max_domains`, `diminishing_returns`, `saturation_reached`, `budget_exhausted`;
- controlled multi-hop discovery;
- `max_discovery_depth`;
- per-depth budgets;
- soft entity-diversity limits so one giant source does not dominate coverage.

## 🧭 3.3.0-alpha.6 — Entity Resolution

Goal: represent the same real-world product/service as one entity with multiple source observations.

Primary signals:
- GTIN / EAN;
- manufacturer + model;
- SKU where meaningful;
- normalized title.

Supporting signals:
- price range;
- fuzzy title similarity, e.g. `rapidfuzz`, only as a supporting signal.

## 🧭 3.3.0-alpha.7 — Fallback Extraction + Evidence Confidence

Extraction priority:

1. JSON-LD;
2. schema.org microdata;
3. OpenGraph;
4. source adapter;
5. deterministic DOM heuristics;
6. optional AI extractor only as a last resort.

Each fact should be able to preserve:
- value;
- source URL;
- extraction method;
- confidence;
- extracted_at;
- evidence/provenance.

## 🧭 3.3.0-alpha.8 — Change Detection

Goal: turn observations into meaningful events.

- `PRICE_DROP`;
- `PRICE_INCREASE`;
- `NEW_ENTITY`;
- `ENTITY_DISAPPEARED`;
- `SOURCE_CHANGED`;
- `DOMAIN_FAILED`;
- `DOMAIN_RECOVERED`;
- feed appeared/disappeared;
- `spriditis diff --run A --run B`.

The sequence is intentional: **Entity Resolution → Evidence Confidence → Change Detection**.

## 🧭 3.3.0-alpha.9 — Watch mode

- incremental repeated research;
- `spriditis watch`;
- change-only summaries;
- scheduling hooks;
- notification hooks;
- feed/ETag-aware refresh;
- reuse of Research Memory;
- JSONL export as a simple integration format.

## 🧭 3.3.0-alpha.10 — Async crawler + adaptive politeness

Only after the research logic is selective enough.

- bounded async requests;
- per-domain semaphore 1–2 as a conservative starting point;
- global concurrency cap;
- adaptive delay;
- retry budgets;
- backpressure;
- no weakening of robots/URL/private-network protections.

## 🔭 Later backlog

- additional free/self-hostable SearchProvider adapters;
- stronger price/currency/VAT normalization;
- images and specification tables;
- carefully isolated high-value source adapters;
- CSV/Parquet exports;
- FastAPI;
- project/run UI;
- scheduler/background jobs;
- webhooks/notifications;
- stricter typing;
- broader test coverage;
- CI/CD;
- Docker;
- project JSON Schema;
- plugin entry points;
- additional AI providers and local models as optional layers.

## Deliberately not near-term priorities

- Redis/RabbitMQ/distributed queues before measured need;
- PostgreSQL before SQLite becomes a measured bottleneck;
- Playwright as the default for every page;
- heavy agent frameworks;
- hosted dashboards before the research core is mature;
- mandatory paid search or AI APIs.

## Intended differentiator

> **Give me a research goal. I will find sources, remember which paths were useful, avoid repeated work, detect meaningful change, and make the next run more selective than the previous one.**

That is **Research Memory + Adaptive Discovery + Evidence Confidence + Incremental Monitoring**.

See also [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/OPEN_CORE.md](docs/OPEN_CORE.md).
