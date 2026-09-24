# Izmaiņu vēsture / Changelog

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
