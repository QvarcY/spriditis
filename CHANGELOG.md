# Izmaiņu vēsture / Changelog

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
