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

## ✅ Pašreizējā publiskā bāze — 3.3.0-alpha.5

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

## ✅ 3.3.0-alpha.3 — Feed Discovery & Incremental Monitoring

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
- kontekstuāla feed kandidātu prioritizācija;
- DB schema v5 ar atsevišķu `feeds` tabulu;
- `feeds` CLI inspekcija;
- atkārtotu run Domain Registry hidratācija;
- sticky `blocked`/`rejected` stāvokļi pirms discovery lēmumiem;
- vēsturisko run skaitītāju ne-replay;
- deterministiski RSS/Atom/JSON Feed, storage, 304 un repeat-run testi;
- reāls publiska RSS tests ar apstiprinātu `304 Not Modified`.

## ✅ 3.3.0-alpha.4 — Research Memory

Mērķis: atcerēties ne tikai atrastos datus, bet arī pētījuma procesa efektivitāti.

**Statuss:** publicēts un pilnībā regresijas testēts.

Ieviests:

- DB schema v6 ar `page_visits` lineage auditu;
- query yield ar stabilu `productive_domain_rate` pāri atkārtotiem runiem;
- source/domain yield un entity yield;
- source profiles ar HTTP success, crawl run, observation un productive-run signāliem;
- search duplicate rate ar raw / unique / duplicate / filtered numeratoriem;
- freshness/staleness ar `last_useful_at → last_crawled → last_seen` pamatu un konfigurējamu stale slieksni;
- discovery provenance un page lineage metrikas;
- URL-scoped safety semantika, kas vairs nepārvērš visu domēnu par sticky `blocked`;
- `memory` CLI Research Memory kopsavilkumam;
- `explain` domēna vēstures un lēmumu izskaidrošanai;
- `trace` viena run provenance ķēdei; pēc noklusējuma discovery eventi tiek grupēti, bet `--full` saglabā raw auditu;
- deterministiski Research Memory, repeat-query, source-profile, freshness un duplicate-rate testi;
- pilns alpha4 regression gate pret iepriekšējiem discovery/search/feed/core slāņiem.

Alpha4 **krāj un izskaidro** pieredzi. Tā vēl neveic automātisku source/query prioritizāciju.

Jaunajām metrikām jābūt izskaidrojamām; viens “mistisks score” nedrīkst aizstāt atsevišķos signālus.

## ✅ 3.3.0-alpha.5 — Adaptive Expedition

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
- soft entity diversity limits, lai viens milzu avots neaizēnotu pārējos;
- persistēts Adaptive Decision Trace ar query priority, search-result priority, source-diversity, discovery-depth un stop lēmumiem;
- DB schema v7 ar `adaptive_decisions` audita tabulu;
- pilnais alpha5 regression gate izpildīts: 32/32 deterministiskie testi iziet.

## ✅ 3.3.0-alpha.6 — Entity Resolution

Mērķis: vienu un to pašu reālās pasaules produktu/pakalpojumu attēlot kā vienu canonical entity ar vairākiem source observations.

**Statuss:** publicēts un pilnībā validēts.

Ieviests:

- JSON-LD identity signālu saglabāšana: GTIN/EAN, brand/manufacturer, model, MPN un SKU;
- deterministisks resolveris ar strong-signal secību: valid GTIN → maker+model → maker+MPN → source-scoped SKU;
- vienāds title un cross-source SKU vieni paši nav pietiekami automātiskam merge;
- source-specific `MarketEntity` un observations paliek kā pierādījumu slānis;
- canonical `entity_clusters` + `entity_cluster_members`;
- ambiguity/conflict resolution audits un `entity_resolution_events`;
- guarded explicit cluster merge ar identity conflict/no-strong-match noraidīšanu;
- merge audit un vēsturiskais `merged_into` statuss;
- dzīva unresolved review queue ambiguity/conflict gadījumiem;
- `clusters`, `explain-cluster`, `merge-clusters`, `cluster-merges`, `review-queue` CLI;
- DB schema v10;
- 6 jauni deterministiski Entity Resolution testi.

Dizaina robežas:

- normalized title ir supporting signāls, nevis standalone cross-source merge identitāte;
- fuzzy title un price-range heuristikas netika ieviestas kā automātiska merge loģika šajā milestone;
- bridge entity, kas strong-matcho vairākus clusterus, tiek atlikta review queue, nevis automātiski sapludina clusterus;
- rejected explicit merge nemaina membership un paliek auditējams.

Pilnais regression gate ir izpildīts: **38/38 deterministiskie testi iziet**.

## 🧪 3.3.0-alpha.7 — Fallback Extraction + Evidence Confidence

**Statuss:** feature-complete release candidate stabilizācijas posmā.

Ieviests:

- ekstrakcijas prioritāte: JSON-LD → schema.org microdata → source adapter/OpenGraph → konservatīvs DOM fallback;
- schema.org microdata ar nested Product/Offer/Brand/Organization scope apstrādi;
- DOM fallback tikai tad, ja strukturētie ekstraktori neko nav atraduši;
- DOM fallback prasa produkta virsrakstu, semantisku cenu, explicit valūtu un produkta konteksta signālu;
- `ExtractionEvidence` katram laukam: value, source URL, extraction method, confidence, evidence un extracted_at;
- direct un default/fallback vērtībām atšķirīgi confidence līmeņi;
- source adapteri izmanto to pašu field-level evidence līgumu;
- DB schema v11 ar `field_evidence_json` current entity provenance glabāšanai;
- observation snapshots saglabā vēsturisko provenance nemainītu;
- `explain-cluster` rāda current field evidence un evidence-quality kopsavilkumu;
- `evidence-quality --project ... [--details]` projekta/entity inspekcijai;
- auditējami high/medium/low confidence bandi bez `score` vai `average_confidence`;
- missing evidence, mismatched/stale evidence un default/inferred lauku uzskaite;
- automatic Entity Resolution GTIN conflict semantika padarīta target-cluster-aware: nesaistīts atšķirīgs GTIN nav conflict, bet strong match + GTIN conflict tajā pašā target clusterī ir hard veto;
- review queue ir backward-compatible ar veco `identity_conflict` reason un jauno `target_cluster_identity_conflict`.

Dizaina robežas:

- `MarketEntity.confidence` paliek AI/enrichment confidence un netiek jaukts ar extraction confidence;
- nav viena opaque Evidence Quality score;
- vecām migrētām entity rindām `field_evidence_json` ir `{}` — vēsturisks provenance netiek izdomāts;
- DOM heuristikas ir konservatīvs pēdējais deterministiskais slānis, nevis strukturēto avotu aizvietotājs;
- labāk palaist garām robežgadījumu nekā radīt viltus produktu no parastas lapas teksta.

Alpha7 fokusētie testi ir zaļi. Pirms merge/tag vēl jāizpilda pilnais **43 testu regression gate**.

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

## ✅ Current public baseline — 3.3.0-alpha.6

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

## ✅ 3.3.0-alpha.3 — Feed Discovery & Incremental Monitoring

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
- context-aware feed-candidate prioritization;
- database schema v5 with a dedicated `feeds` table;
- `feeds` CLI inspection;
- Domain Registry hydration for repeated runs;
- sticky `blocked`/`rejected` lifecycle states before discovery decisions;
- no replay of historical run counters;
- deterministic RSS/Atom/JSON Feed, storage, 304 and repeat-run tests;
- real public RSS validation confirming `304 Not Modified`.

## ✅ 3.3.0-alpha.4 — Research Memory

Goal: remember not only collected data, but the effectiveness of the research process itself.

**Status:** released and fully regression-tested.

Implemented:

- database schema v6 with `page_visits` lineage auditing;
- query yield with stable `productive_domain_rate` across repeated runs;
- source/domain yield and entity yield;
- source profiles with HTTP success, crawl-run, observation and productive-run signals;
- search duplicate rate with explicit raw / unique / duplicate / filtered numerators;
- freshness/staleness based on `last_useful_at → last_crawled → last_seen` with a configurable stale threshold;
- discovery provenance and page-lineage metrics;
- URL-scoped safety semantics that no longer turn an entire domain into sticky `blocked`;
- `memory` CLI for Research Memory summaries;
- `explain` for domain history and decision evidence;
- `trace` for one-run provenance; discovery events are grouped by default while `--full` preserves raw audit output;
- deterministic Research Memory, repeat-query, source-profile, freshness and duplicate-rate tests;
- a full alpha4 regression gate across the existing discovery/search/feed/core layers.

Alpha4 **records and explains** experience. It does not yet perform automatic source/query prioritization.

Metrics stay explainable; one opaque “magic score” must not replace the underlying signals.

## ✅ 3.3.0-alpha.5 — Adaptive Expedition

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
- soft entity-diversity limits so one giant source does not dominate coverage;
- persisted Adaptive Decision Trace for query priority, search-result priority, source-diversity, discovery-depth and stop decisions;
- database schema v7 with an `adaptive_decisions` audit table;
- the full alpha5 regression gate passed: 32/32 deterministic tests.

## 🚧 3.3.0-alpha.6 — Entity Resolution

Goal: represent the same real-world product/service as one canonical entity with multiple source observations.

**Status:** released and fully validated.

Implemented:

- JSON-LD identity preservation for GTIN/EAN, brand/manufacturer, model, MPN and SKU;
- deterministic strong-signal resolver: valid GTIN → maker+model → maker+MPN → source-scoped SKU;
- equal title and cross-source SKU are not sufficient by themselves for automatic merge;
- source-specific `MarketEntity` rows and observations remain the evidence layer;
- canonical `entity_clusters` + `entity_cluster_members`;
- ambiguity/conflict resolution audit through `entity_resolution_events`;
- guarded explicit cluster merge with conflict/no-strong-match rejection;
- merge audit with historical `merged_into` status;
- live unresolved review queue for ambiguity/conflict cases;
- `clusters`, `explain-cluster`, `merge-clusters`, `cluster-merges`, `review-queue` CLI;
- database schema v10;
- six new deterministic Entity Resolution tests.

Design boundaries:

- normalized title is a supporting signal, not standalone cross-source merge identity;
- fuzzy-title and price-range heuristics were deliberately not promoted to automatic merge logic in this milestone;
- a bridge entity matching multiple clusters is deferred to review instead of auto-merging clusters;
- a rejected explicit merge leaves membership unchanged and remains auditable.

The complete regression gate passed: **38/38 deterministic tests**.

## 🧪 3.3.0-alpha.7 — Fallback Extraction + Evidence Confidence

**Status:** feature-complete release candidate under stabilization.

Implemented:

- extraction priority: JSON-LD → schema.org microdata → source adapter/OpenGraph → conservative DOM fallback;
- schema.org microdata with nested Product/Offer/Brand/Organization scope handling;
- DOM fallback only when structured extraction produced no entity;
- DOM fallback requires a product title, semantic price, explicit currency and a product-context signal;
- field-level `ExtractionEvidence`: value, source URL, extraction method, confidence, evidence and extracted_at;
- separate confidence levels for direct vs default/fallback values;
- source adapters use the same field-evidence contract;
- database schema v11 with `field_evidence_json` for current entity provenance;
- observation snapshots preserve historical provenance unchanged;
- `explain-cluster` exposes current field evidence and evidence-quality summaries;
- `evidence-quality --project ... [--details]` for project/entity inspection;
- auditable high/medium/low confidence bands without a `score` or `average_confidence`; 
- missing evidence, mismatched/stale evidence and default/inferred field accounting;
- automatic Entity Resolution GTIN-conflict behavior is target-cluster-aware: an unrelated different GTIN is not a conflict, while strong match + GTIN conflict inside the same target cluster is a hard veto;
- review queue remains backward-compatible with legacy `identity_conflict` events and the new `target_cluster_identity_conflict` reason.

Design boundaries:

- `MarketEntity.confidence` remains AI/enrichment confidence and is not overloaded with extraction confidence;
- there is no opaque Evidence Quality score;
- migrated historical entity rows receive `field_evidence_json={}`; provenance is never invented retroactively;
- DOM heuristics are a conservative final deterministic layer, not a replacement for structured sources;
- missing a borderline product is preferable to manufacturing a false product from ordinary page text.

Focused alpha7 tests are green. The complete **43-test regression gate** still has to pass before merge/tag.

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
