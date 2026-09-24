# Izmaiņu vēsture / Changelog

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
