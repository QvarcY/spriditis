# Izmaiņu vēsture / Changelog

## [3.3.0-alpha.9]

> **Statuss / Status:** release baseline pilnībā validēts; pilnais regression gate izpildīts ar 55/55 testiem.  
> Release baseline fully validated; the complete regression gate passed 55/55 tests.

### Pievienots / Added

- `watch --project ... --once` vienam inkrementālam research ciklam / single-cycle incremental Watch execution
- atkārtots Watch režīms ar `--interval-seconds` un izvēles `--max-cycles`; minimums 60 sekundes un bez pārklājošiem cikliem / bounded repeated Watch loop with a 60-second minimum and no overlapping cycles
- graceful `Ctrl+C` apstāšanās, nepieskaitot nepabeigtu ciklu kā pabeigtu / graceful interruption without counting an unfinished cycle
- change-only JSONL eksports ar shēmu `spriditis.watch.change.v1`; baseline un no-change cikli neveido tukšus heartbeat ierakstus / change-only JSONL export with no baseline/no-change noise
- coverage-aware Watch salīdzināšana entity presence/source-set eventiem / coverage-aware Watch comparison for entity-presence and source-set events
- auditējams `suppressed_uncertain` slānis, kas atdala nepietiekami pārbaudītu coverage churn no pierādītām izmaiņām / auditable suppression of coverage uncertainty
- `WatchCycleResult`, cycle hooks un change hooks kā stabils integrācijas līgums / stable cycle/change hook contract
- change hooks saņem pašus verificētos change eventus, ne tikai skaitītājus / verified change-event payloads are available to notification adapters
- Watch-specifiska ETag/`Last-Modified`/304 validācija pāri DB-persistētam feed state / persisted conditional-feed refresh validated across Watch cycles
- Watch-specifiska Research Memory reuse validācija: query memory un source profiles ietekmē nākamā cikla prioritizāciju un paliek Decision Trace / repeated Watch cycles reuse Research Memory and preserve the decision trail

### Uzlabots / Improved

- `compare_with_previous_run(...)` Watch ceļā izmanto konservatīvu coverage-aware semantiku, kamēr tiešais alpha8 `compare_runs(...)` noklusējums paliek backward-compatible raw historical diff / Watch uses conservative coverage-aware comparison while direct historical diff semantics stay backward-compatible
- `NEW_ENTITY` Watch režīmā prasa iepriekšējā runā salīdzināmi pārbaudītu source URL; `ENTITY_DISAPPEARED` prasa vēlākajā runā pārbaudītu source URL / entity presence changes require comparable URL rechecks
- `SOURCE_CHANGED` prasa salīdzināmi pārbaudītus pievienotos/noņemtos avotus / source-set changes require comparable source coverage
- feed `304 Not Modified` paliek `active`, saglabā iepriekšējo successful state un nerada viltus feed lifecycle eventu / 304 is a fetch outcome, not a failure/lifecycle transition
- Watch atkārtoti izmanto DB `query_memory`, `source_profiles`, Domain Registry un feed state, nevis sāk katru ciklu no nulles / repeated runs consume persisted research state
- hook kļūmes ir izolētas un nepadara jau pabeigtu research ciklu par neveiksmīgu / hook-adapter failures are isolated and non-fatal to completed research runs

### Dizaina robežas / Design boundaries

- alpha9 neievieš iebūvētu daemon scheduler, background-job sistēmu vai webhook serveri; tas dod CLI loopu un stabilus integrācijas hookus ārējiem adapteriem / no built-in daemon scheduler, job queue or webhook server
- coverage uncertainty netiek pārdēvēta par market change; nepārbaudīts URL nav pierādījums pazušanai vai jaunam tirgus objektam / unvisited coverage is not treated as market change evidence
- change hooks saņem tikai jau coverage-filtrētus/verificētus eventus / notification adapters receive only verified Watch events
- JSONL ir vienkāršs integrācijas formāts, nevis pilna event-bus infrastruktūra / JSONL remains a simple integration surface
- Watch saglabā alpha8 Change Detection pierādījumu/provenance semantiku un nepārraksta vēsturiskos observation/page/feed faktus / historical evidence remains immutable

### Validācija / Validation

- `watch_incremental_test.py`
- `watch_loop_test.py`
- `watch_jsonl_test.py`
- `watch_coverage_test.py`
- `watch_hooks_test.py`
- `watch_feed_refresh_test.py`
- `watch_research_memory_test.py`
- visi alpha8 Change Detection, alpha5 Adaptive Expedition, Research Memory, Search/Discovery/Feed, Entity Resolution un Evidence Quality regression testi paliek zaļi
- reāls Watch crawl ar mainīgu 60-lapu coverage suppressēja 42 nepietiekami pierādītus presence kandidātus un eksportēja 0 viltus change eventus
- pilnais **55/55** testu regression gate izpildīts sekmīgi / complete **55/55** regression gate passed

---

## [3.3.0-alpha.8]

> **Statuss / Status:** release baseline pilnībā validēts; pilnais regression gate izpildīts ar 48/48 testiem.  
> Release baseline fully validated; the complete regression gate passed 48/48 tests.

### Pievienots / Added

- auditējams `ChangeEvent` modelis un deterministisks run-to-run salīdzinājums
- `NEW_ENTITY`, `ENTITY_DISAPPEARED`, `PRICE_DROP`, `PRICE_INCREASE` un `SOURCE_CHANGED`
- evidence-gated `SELLER_CHANGED`, `DESCRIPTION_CHANGED` un `IMAGE_CHANGED` ar minimum confidence `0.70`
- konservatīvs `DOMAIN_FAILED` / `DOMAIN_RECOVERED` no historical page visits
- DB schema v12 ar run-scoped `feed_snapshots`
- `FEED_APPEARED`, `FEED_DISAPPEARED`, `FEED_NEW_ENTRIES`, `FEED_FAILED`, `FEED_RECOVERED`
- feed change evidence linkage uz historical snapshot ID run trace
- `diff --project ... --run-a ... --run-b ... [--details]` CLI

### Drošības un pierādījumu robežas / Safety and evidence boundaries

- price eventus salīdzina tikai vienam source entity un vienādā valūtā
- low-confidence, missing un mismatched field evidence tiek apspiests
- HTTP 4xx pats par sevi nav domain failure
- robots/safety-only page outcomes paliek `unknown`
- jaukts successful + 5xx domēna rezultāts paliek reachable
- feed disappearance tiek emitēts tikai tad, ja vēlākajā runā feed domēns tiešām bija reachable
- nepārbaudīts domēns nerada viltus feed disappearance
- canonical identity izmanto current membership, bet vēsturiskie observation/page/feed fakti paliek nemainīti

### Validācija / Validation

- `change_detection_diff_test.py`
- `change_detection_canonical_merge_test.py`
- `change_detection_field_changes_test.py`
- `change_detection_domain_health_test.py`
- `change_detection_feed_test.py`
- feed storage/incremental/crawler/parser regressions
- Entity Resolution, Evidence Quality un Adaptive Decision Trace regresijas paliek zaļas
- pilnais **48/48** testu regression gate izpildīts sekmīgi / complete **48/48** regression gate passed

---

## [3.3.0-alpha.7]

> **Statuss / Status:** release baseline pilnībā validēts; pilnais regression gate izpildīts ar 43/43 testiem.  
> Release baseline fully validated; the complete regression gate passed 43/43 tests.

### Pievienots / Added

- field-level `ExtractionEvidence` ar value, source URL, extraction method, confidence, evidence un extracted_at
- schema.org microdata product extractor ar nested Product/Offer/Brand/Organization scope atbalstu
- konservatīvs `dom-fallback` extractor kā pēdējais deterministiskais slānis
- DOM fallback false-positive aizsargi: explicit valūta + semantic price + product context
- Meistardarbs source adapterim tas pats field-level evidence līgums
- DB schema v11 ar `entities.field_evidence_json` current provenance glabāšanai
- historical field provenance saglabājas nemainīgs `observations.snapshot_json`
- `evidence-quality --project ... [--details]` CLI
- `explain-cluster` field evidence un Evidence Quality summary
- Evidence Quality high/medium/low bandi
- missing evidence, mismatched/stale evidence un default/inferred lauku audits
- pieci jauni alpha7 deterministiski testi: extraction evidence, microdata, DOM fallback, field-evidence persistence un evidence-quality summary

### Uzlabots / Improved

- extraction prioritāte paplašināta no JSON-LD/OpenGraph uz JSON-LD → microdata → source adapter/OpenGraph → konservatīvu DOM fallback
- direct structured vērtības un default/fallback vērtības vairs nesaņem vienādu extraction confidence
- current entity evidence tiek atjaunināts neatkarīgi no vēsturiskajiem observation snapshots
- schema-version testi izmanto `CURRENT_SCHEMA_VERSION`, lai schema bump neizraisītu stale hardcoded regresijas
- automatic Entity Resolution GTIN konflikts tagad ir target-cluster-aware
- nesaistīts produkts ar citu valid GTIN vairs netiek kļūdaini auditēts kā identity conflict
- strong match + GTIN conflict tajā pašā target clusterī tagad ir hard veto
- hard-veto auditā tiek saglabāti gan matched, gan conflicting identity signāli
- review queue atbalsta gan legacy `identity_conflict`, gan jauno `target_cluster_identity_conflict` reason

### Dizaina robežas / Design boundaries

- `MarketEntity.confidence` joprojām nozīmē AI/enrichment confidence; extraction confidence dzīvo tikai field evidence
- Evidence Quality neveido `score` vai `average_confidence`
- vecām migrētām rindām netiek izdomāts vēsturisks provenance — `field_evidence_json` sākas kā `{}`
- DOM fallback nekad neaizēno veiksmīgu structured extraction
- cena bez explicit valūtas DOM fallbackā tiek noraidīta
- parastas rakstu/pricing lapas bez produkta konteksta netiek pārvērstas par produktu

### Validācija / Validation

- `extraction_evidence_test.py`
- `microdata_extraction_test.py`
- `dom_fallback_extraction_test.py`
- `field_evidence_persistence_test.py`
- `evidence_quality_summary_test.py`
- Entity Resolution target-cluster conflict safety regressions
- DB migration schema v11
- Adaptive Decision Trace schema v11 SQLite round-trip
- fokusētie alpha7 un alpha6/core regression testi paliek zaļi
- pilnais **43/43** testu regression gate izpildīts sekmīgi / complete **43/43** regression gate passed

---
## [3.3.0-alpha.6]

> **Statuss / Status:** release baseline pilnībā validēts; pilnais regression gate izpildīts ar 38/38 testiem.  
> Release baseline fully validated; the complete regression gate passed 38/38 tests.

### Pievienots / Added

- deterministisks Entity Resolution resolveris ar valid GTIN, maker+model, maker+MPN un source-scoped SKU strong signāliem
- JSON-LD identity lauku saglabāšana: brand/manufacturer, model, MPN, SKU un GTIN/EAN
- canonical `entity_clusters` un `entity_cluster_members` virs source-specific `MarketEntity`/observations
- DB schema v10 ar resolution/cluster/merge audita slāņiem
- persistēti `entity_resolution_events` ambiguity/conflict lēmumiem
- guarded explicit cluster merge ar `entity_cluster_merge_events` auditu
- vēsturisks `merged_into_cluster_key` / `merged_at` source clusteriem
- unresolved `review-queue` ambiguity un identity-conflict gadījumiem
- `clusters`, `explain-cluster`, `merge-clusters`, `cluster-merges`, `review-queue` CLI
- cluster explain skats ar members, source observations, identity signāliem, resolution/merge history un review items
- seši jauni deterministiski Entity Resolution testi

### Drošības un identitātes robežas / Identity safety boundaries

- nederīgs GTIN tiek atmests pēc check-digit validācijas
- title-only un cross-source SKU vieni paši neveic cross-source merge
- bridge entity, kas strong-matcho vairākus clusterus, tiek atlikta kā `deferred_ambiguous`
- explicit merge prasa strong identity match
- GTIN/strong identity konflikts bloķē arī manuālu merge
- rejected merge membership nemaina
- source-specific entity un observation pierādījumi netiek dzēsti vai sapludināti vienā source rindā
- review queue aizveras no reāla cluster stāvokļa, nevis manuāla checkbox/statusa

### Validācija / Validation

- `entity_identity_resolution_test.py`
- `entity_cluster_persistence_test.py`
- `entity_resolution_audit_test.py`
- `entity_cluster_merge_test.py`
- `entity_resolution_review_queue_test.py`
- `entity_cluster_explain_test.py`
- DB migration v10 testi
- Adaptive Decision Trace schema-version regression salabots uz `CURRENT_SCHEMA_VERSION`
- fokusētie alpha6 un alpha5/core regression testi paliek zaļi
- pilnais **38/38** testu regression gate izpildīts sekmīgi / complete **38/38** regression gate passed

---

## [3.3.0-alpha.5]

> **Statuss / Status:** release baseline pilnībā validēts; pilnais regression gate izpildīts ar 32/32 testiem.  
> Release baseline fully validated; the complete regression gate passed 32/32 tests.

### Pievienots / Added

- Research Memory balstīta automātiska query prioritizācija ar explicit `configured > productive > untested > nonproductive` secību / Research Memory-driven query prioritization with an explicit ordering
- source-profile prioritizācija ar atsevišķiem productive/fresh/stale/untested/nonproductive stāvokļiem / source-profile priority bands without an opaque aggregate score
- lokāls BM25 search-result relevance slānis ar title/path/domain un negative-keyword signāliem / local BM25 result relevance with separate title/path/domain and negative-keyword signals
- konfigurējami `diminishing_returns_window` un `saturation_window`, pēc noklusējuma `0 = disabled`
- auditējams `STOP_REASON`: `max_pages`, `max_domains`, `diminishing_returns`, `saturation_reached`, `budget_exhausted`
- atsevišķs `discovery_depth` starpdomēnu hopiem, `max_discovery_depth` un per-depth activation budgets
- soft source-diversity frontier penalty ar konfigurējamu entity soft-cap; atrastās entity netiek dzēstas / soft source-diversity prioritization without dropping collected entities
- DB schema v7 ar `adaptive_decisions` tabulu / database schema v7 with a persisted adaptive-decision audit table
- `AdaptiveDecision` modelis query priority, search-result priority, source-diversity, discovery-depth un stop lēmumiem
- `trace --run N` Adaptive Decision Trace skats ar lēmumu secību un atsevišķiem signāliem

### Uzlabots / Improved

- alpha4 Research Memory vairs nav tikai inspekcijas slānis: alpha5 to patērē nākamā run prioritizācijai / Research Memory now directly informs the next run
- provider sākotnējā rezultātu secība kļūst par tie-breaker pēc izskaidrojamiem source/local relevance signāliem
- viena liela avota same-domain frontier dominance var tikt mīksti samazināta, saglabājot visus jau atrastos datus
- controlled multi-hop discovery neizmanto parasto page depth kā domēnu hop aizstājēju
- CLI run kopsavilkums rāda STOP_REASON, adaptive streaks, diversity diagnostiku un adaptive-decision skaitu
- feed discovery depth ierobežojumi tiek auditēti tajā pašā Decision Trace kā HTML linku discovery

### Dizaina robeža / Milestone boundary

- alpha5 prioritizē un aptur deterministiski; obligāts maksas MI nav vajadzīgs / adaptive behavior remains deterministic and does not require paid AI
- Research Memory, BM25, freshness, productivity, diversity un depth signāli netiek sapludināti vienā opaque “magic score”
- soft limits maina izpētes secību, nevis slēpj atrastus pierādījumus
- Adaptive Decision Trace saglabā lēmumu iemeslus SQLite un ļauj tos pārbaudīt pēc run

### Validācija / Validation

- `adaptive_query_priority_test.py`
- `adaptive_source_priority_test.py`
- `adaptive_local_relevance_test.py`
- `adaptive_stopping_test.py`
- `adaptive_multihop_test.py`
- `adaptive_source_diversity_test.py`
- `adaptive_decision_trace_test.py`
- DB migration v7 tests
- iepriekšējie Research Memory testi paliek zaļi / existing Research Memory regressions remain green
- pilnais 32 testu regression gate izpildīts sekmīgi / complete 32-test regression gate passed

---

## [3.3.0-alpha.4]

### Pievienots / Added

- DB schema v6 ar `page_visits` tabulu page lineage auditam / database schema v6 with a `page_visits` table for page-lineage auditing
- `PageVisit` modelis ar URL/final URL, domain, source URL/type, depth, priority, outcome, HTTP statusu, content type un timestamp / `PageVisit` model with auditable fetch/discovery lineage metadata
- `memory` CLI query yield, search duplication, source profiles un freshness signāliem / `memory` CLI for query yield, search duplication, source profiles and freshness signals
- `explain` CLI viena domēna Research Memory izskaidrošanai / `explain` CLI for one-domain Research Memory evidence
- `trace` CLI viena run provenance ķēdei, ar grupētu noklusējuma skatu un `--full` raw discovery auditu / `trace` CLI for one-run provenance, grouped by default with `--full` raw discovery audit
- query `productive_domain_rate`, kas saglabā jēgpilnu yield arī tad, kad atkārtotā run labs domēns ir `known`, nevis atkārtoti `activated` / stable query `productive_domain_rate` across repeated runs
- source profiles ar entity yield, HTTP success, crawl runs, observations, productive runs un `productive_run_rate` / source profiles with entity yield, HTTP success, crawl runs, observations and productive-run signals
- search duplicate memory ar raw / unique / duplicate / filtered skaitītājiem un duplicate rate / search duplicate memory with explicit raw / unique / duplicate / filtered counters and duplicate rate
- freshness/staleness signāli ar `last_useful_at → last_crawled → last_seen` pamatu, konfigurējamu `--stale-days` slieksni un redzamu freshness basis / freshness/staleness signals with explicit basis and configurable threshold

### Uzlabots / Improved

- atkārtotu query vērtība vairs netiek vērtēta tikai pēc first-activation notikumiem / repeated-query value no longer depends only on first-activation events
- source lietderība tiek atdalīta no tīkla tehniskās stabilitātes: 100% HTTP success var pastāvēt kopā ar 0 productive runs / source usefulness is separated from transport success
- URL-scoped safety iemesli, piemēram, `blocked_path`, bloķē konkrēto URL, bet vairs nepadara visu domēnu sticky `blocked` / URL-scoped safety reasons no longer poison the whole domain lifecycle
- Research Memory CLI freshness tabulai pievienots `BASIS`, lai `fresh seen`, `fresh crawl` un `fresh useful` būtu nepārprotami / freshness output exposes its basis explicitly
- discovery audita raw dati paliek pilni SQLite, kamēr cilvēkam lasāmais `trace` pēc noklusējuma grupē atkārtotus eventus / raw discovery audit remains complete while default trace output groups repeated events

### Dizaina robeža / Milestone boundary

- alpha4 **krāj un izskaidro** Research Memory signālus / alpha4 **records and explains** Research Memory signals
- alpha4 neveic automātisku query/source prioritizāciju pēc vēsturiskās atmiņas / alpha4 does not automatically prioritize queries or sources from historical memory
- adaptīva prioritizācija, saturation un stopping lēmumi paliek 3.3.0-alpha.5 Adaptive Expedition uzdevums / adaptive prioritization, saturation and stopping remain alpha5 work
- netiek ieviests viens opaque source/query “quality score”; pamatā paliek atsevišķi auditējami signāli / no single opaque source/query quality score replaces the underlying signals

### Validācija / Validation

- `research_memory_test.py`
- `research_memory_repeat_query_test.py`
- `research_memory_source_profile_test.py`
- `research_memory_freshness_test.py`
- `research_memory_duplicate_rate_test.py`
- pilns regression gate izpildīts pret schema, DB migration, Domain Registry, controlled discovery, sitemap, SearchProvider, SearXNG reliability, Expedition, Feed Discovery un smoke slāņiem / full regression gate passed across schema, DB migration, Domain Registry, controlled discovery, sitemap, SearchProvider, SearXNG reliability, Expedition, Feed Discovery and smoke coverage
- reālā GitHub Changelog smoke datubāzē `github.blog` saglabā 100% HTTP success ar 0 productive runs un freshness basis=`last_crawled`, demonstrējot tehniskās pieejamības un research lietderības atdalīšanu / real GitHub Changelog smoke data demonstrates separation of transport success, research productivity and freshness

---

## [3.3.0-alpha.3]

### Pievienots / Added

- RSS 2.0, Atom un JSON Feed parseri / RSS 2.0, Atom and JSON Feed parsers
- HTML `<link rel="alternate">` feed autodiscovery
- kontekstuāla feed kandidātu prioritizācija / context-aware feed candidate ordering
- atsevišķs `FeedState` modelis un `feeds` SQLite tabula / dedicated `FeedState` model and SQLite `feeds` table
- `ETag`, `Last-Modified`, `If-None-Match`, `If-Modified-Since`
- `304 Not Modified` incremental monitoring
- `last_entry_id`, `last_published`, `last_checked`, `last_success`
- feed provenance caur Domain Registry / feed provenance through Domain Registry
- `feeds` CLI komanda
- feed kandidātu, ierakstu, jauno ierakstu, 304 un kļūdu run skaitītāji / feed run counters
- UTF-8 BOM toleranta project JSON ielāde / UTF-8 BOM tolerant project JSON loading

### Uzlabots / Improved

- feed ierakstu URL izmanto esošo safety → relevance → Domain Registry → frontier plūsmu / feed-entry URLs use the existing safety → relevance → Domain Registry → frontier path
- sekcijai specifiski feedi tiek prioritizēti pirms generic/comment feediem / section-specific feeds outrank generic/comment feeds
- feed redirect gadījumā persistentā resursa identitāte saglabā discovery URL, lai nezaudētu conditional-request state / persistent feed identity keeps the discovered URL across same-host redirects
- `304` ir fetch iznākums, nevis feed lifecycle statuss / `304` is a fetch outcome, not a feed lifecycle state
- Domain Registry tiek hidratēts no SQLite pirms atkārtota run discovery lēmumiem / Domain Registry is hydrated from SQLite before repeated-run discovery decisions
- `blocked` un `rejected` stāvokļi paliek sticky; `active` tiek atpazīts kā zināms / sticky lifecycle behavior for `blocked`, `rejected`, and known `active`
- vēsturiskie `pages_seen`/`entities_found` netiek replayoti jaunā run / historical run counters are not replayed

### Mainīts / Changed

- DB schema version 5
- Feed Discovery ir pilnvērtīgs discovery slānis blakus SearchProvider, HTML linkiem un sitemap / Feed Discovery is a first-class discovery layer alongside SearchProvider, HTML links and sitemaps

### Validācija / Validation

- deterministiski RSS, Atom un JSON Feed parseru testi / deterministic RSS, Atom and JSON Feed parser tests
- feed storage un DB migration testi / feed storage and DB migration tests
- feed → frontier crawler integrācijas tests / feed-to-frontier crawler integration test
- conditional request / `304` tests
- repeat-run Domain Registry persistence tests
- visi SearchProvider, Expedition, discovery, sitemap un smoke regression testi paliek zaļi / existing SearchProvider, Expedition, discovery, sitemap and smoke regressions remain green
- reālā publiskā GitHub Changelog RSS pārbaudē divi feedi atkārtotā run atbildēja ar `304 Not Modified` / real public GitHub Changelog RSS validation confirmed `304 Not Modified` for both selected feeds

---

## [3.3.0-alpha.2]

### Pievienots / Added

- `search-check` CLI komanda SearchProvider konfigurācijas un savienojuma pārbaudei / CLI command for SearchProvider configuration and connectivity checks
- raw / unique / duplicate search rezultātu skaitītāji / search-result counters
- `expedition_dedupe_test.py`
- `searxng_reliability_test.py`

### Uzlabots / Improved

- SearXNG transient kļūdām pievienots retry/backoff / retry/backoff for transient SearXNG failures
- tiek ievērots `Retry-After` / `Retry-After` is honored
- SearchProvider kļūdas satur strukturētu tipu, HTTP statusu, retryable stāvokli un mēģinājumu skaitu / structured provider errors include type, HTTP status, retryability and attempt count
- viena un tā pati URL no vairākiem query tiek apstrādāta tikai vienreiz / duplicate URLs across queries are processed once
- nederīgi non-HTTP(S) search rezultāti tiek atmesti agrīni / invalid non-HTTP(S) results are rejected early
- report/run metrikas paplašinātas ar dedupe skaitītājiem / run/report metrics include dedupe counters

### Mainīts / Changed

- DB schema version 4
- SearchProvider reliability un dedupe kļūst par 3.3 publiskās bāzes daļu / SearchProvider reliability and dedupe are now part of the 3.3 public baseline

### Validācija / Validation

- SearXNG reliability tests iziet sekmīgi / reliability tests pass
- Expedition dedupe tests iziet sekmīgi / dedupe tests pass
- zero-seed Expedition regression tests iziet sekmīgi / zero-seed Expedition regression tests pass
- controlled discovery un DB migration testi joprojām iziet sekmīgi / controlled discovery and DB migration tests remain green

---

## [3.3.0-alpha.1]

### Pievienots / Added

- provider-neatkarīga `SearchProvider` abstrakcija / provider-neutral `SearchProvider` abstraction
- deterministisks Expedition query ģenerators / deterministic Expedition query generator
- SearXNG JSON API provideris / SearXNG JSON API provider
- offline `FakeSearchProvider`
- īsts zero-seed Expedition starts / true zero-seed Expedition bootstrap
- SearchProvider provenance domain discoveries
- search query/result/activation/error skaitītāji / counters
- `queries` CLI komanda
- run overrides SearchProvider un domain/search budgets
- Windows-friendly direct test bootstrap

### Mainīts / Changed

- DB schema version 3
- persistent Domain Registry saglabā sticky `blocked`/`rejected` stāvokļus un nepieļauj `active → candidate` downgrade
- report footer satur active-search counters

### Validācijas mērķis / Validation target

- projekts bez seed URL var ģenerēt query, saņemt search rezultātus, aktivizēt drošu/relevantu domēnu un to crawlēt;
- otrs relevants domēns paliek `candidate`, ja domain budget ir pilns;
- blocked hosts paliek blocked arī tad, ja tos atgriež SearchProvider;
- provider/query provenance paliek auditējama.

---

> Nākamo versiju ieraksti tiks dokumentēti latviski vispirms un angliski kā paralēls tehniskais tulkojums.  
> Future release entries will be documented Latvian first with English technical equivalents.
