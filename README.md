<p align="center">
  <img src="assets/spriditis-banner.png" alt="Sprīdītis — configurable market-research crawler and AI-assisted research engine" width="100%">
</p>

<h1 align="center">Sprīdītis</h1>

<p align="center">
  <strong>Pielāgojams tirgus izpētes crawleris un MI atbalstīts pētniecības dzinējs.</strong><br>
  <strong>Configurable market-research crawler and AI-assisted research engine.</strong>
</p>

<p align="center">
  <a href="https://buymeacoffee.com/craftin">☕ Support the project</a>
  &nbsp;•&nbsp;
  <a href="#latviski">Latviski</a>
  &nbsp;•&nbsp;
  <a href="#english">English</a>
</p>

---
## ✨ Projekts īsumā / Project at a glance

> **Mazs pētniecības dzinējs ar lielu ceļu priekšā:** tas dodas tīmeklī, seko pierādījumiem, atceras, kā atrada noderīgo, un tiek veidots tā, lai katrs nākamais pētījums būtu gudrāks par iepriekšējo.  
> **A small research engine with a big journey:** it goes out into the web, follows evidence, remembers how it found things, and is being built to make every next research run smarter than the previous one.

| | Status |
|---|---|
| **Publiskā versija / Public baseline** | ✅ `v3.3.0-alpha.10` — Async crawler + adaptive politeness |
| **Šobrīd / Current work** | 🧭 Nākamais numurētais posms vēl nav izvēlēts / Next numbered milestone not selected yet |
| **Galvenais virziens / North star** | 🧠 **Research Memory + Adaptive Discovery** |
| **Pamatprincips / Core principle** | 🔎 **source-backed facts > AI guesses** |
| **Izmaksu princips / Cost direction** | 🌱 Priekšroka lokāliem, atvērtiem, pašhostējamiem un bezmaksas risinājumiem / Prefer local, open, self-hostable and zero-cost building blocks |

### Statusu leģenda / Status legend

**✅ Publicēts / Released** — publiski pieejams un ieviests / public and implemented  
**🧪 Validēšana / Validating** — lokāli ieviests, tiek pārbaudīts vai gatavots publicēšanai / implemented locally, under validation or publication preparation  
**🚧 Nākamais darbā / Next in progress** — nākamais aktīvais izstrādes posms / next active development step  
**🧭 Plānots / Planned** — apstiprināts attīstības virziens / accepted roadmap direction

## 🧭 Attīstības ceļš / Development journey

> Šis ir dzīvs attīstības plāns, nevis fiksētu izlaišanas datumu solījums. Versiju robežas var mainīties, ja testēšana atklāj labāku arhitektūras risinājumu.  
> This is a working roadmap, not a promise of fixed release dates. Version boundaries may move as testing reveals better architecture.

| Statuss / Status | Versija / Version | Posms / Milestone | Galvenais ieguvums / What it adds |
|---|---|---|---|
| ✅ | **3.1** | Configurable research core | `ResearchProject`, generic entities, structured extraction, optional AI enrichment |
| ✅ | **3.2** | Domain Registry + Discovery Engine | persistent domain memory, sitemap discovery, controlled multi-domain crawling, DB migrations |
| ✅ | **3.3.0-alpha.1** | SearchProvider + zero-seed Expedition | provider abstraction, query generation, search provenance, search → activation → crawl |
| ✅ | **3.3.0-alpha.2** | SearchProvider hardening | retry/backoff, `Retry-After`, structured provider errors, result dedupe, `search-check`, schema v4 |
| ✅ | **3.3.0-alpha.3** | Feed Discovery & Incremental Monitoring | RSS 2.0, Atom, JSON Feed, autodiscovery, ETag / Last-Modified, feed provenance, repeat-run domain persistence |
| ✅ | **3.3.0-alpha.4** | Research Memory | query/source yield, source profiles, search duplication, provenance, `memory` + `explain` + `trace`, freshness/staleness |
| ✅ | **3.3.0-alpha.5** | Adaptive Expedition | Research Memory-driven query/source priority, local BM25, adaptive stopping, multi-hop budgets, source diversity, persisted Decision Trace |
| ✅ | **3.3.0-alpha.6** | Entity Resolution | deterministic cross-source identity, canonical clusters, resolution audit, guarded merge, review queue, cluster explain |
| ✅ | **3.3.0-alpha.7** | Fallback Extraction + Evidence Confidence | JSON-LD → microdata → OpenGraph → conservative DOM fallback, field provenance/confidence, schema v11, evidence-quality inspection |
| ✅ | **3.3.0-alpha.8** | Change Detection | entity/price/field/source/domain/feed lifecycle events, historical provenance, `diff` between runs, schema v12 |
| ✅ | **3.3.0-alpha.9** | Watch mode | coverage-aware repeated research, change-only JSONL, hooks, ETag/304 + Research Memory reuse |
| ✅ | **3.3.0-alpha.10** | Async crawler | bounded async prefetch, retry budgets, adaptive per-domain politeness, deterministic processing |

<details>
<summary><strong>🔭 Longer-term backlog / Ilgtermiņa plāns</strong></summary>

### Discovery and research intelligence
- additional SearchProvider adapters, prioritizing no-cost/self-hostable options;
- query-yield learning and automatic reuse of productive searches;
- source-value scoring;
- coverage saturation / diminishing-returns stopping;
- controlled multi-hop research;
- reusable research templates.

### Extraction and data quality
- richer price normalization;
- images and specification-table extraction;
- source adapters for high-value marketplaces/sites where appropriate;
- entity resolution by GTIN/EAN, manufacturer + model, normalized title and fuzzy signals;
- field-level provenance and confidence.

### Monitoring and analytics
- longitudinal price/category trends;
- “new on market” / “disappeared” events;
- source recovery/failure events;
- CSV / JSONL / Parquet export;
- project-to-project comparisons.

### Product and automation layers
- REST API;
- project/run UI;
- scheduler and background jobs;
- webhooks / notifications;
- additional export surfaces such as CSV / Parquet.

### Engineering quality
- stronger typing and static checks;
- broader automated test coverage;
- CI/CD;
- Docker / docker-compose;
- project JSON Schema;
- plugin entry points for providers and adapters.

### Optional future AI
- additional AI providers behind the existing abstraction;
- local-model support where practical;
- structured AI output;
- cost tracking;
- evaluation datasets;
- RAG over collected observations only when the deterministic data layer is mature.

</details>

## 📖 Kāpēc “Sprīdītis”? / Why the name “Sprīdītis”?

Nosaukums ir apzināta atsauce uz **Annas Brigaderes “Sprīdīti”** — mazu, apņēmīgu un atjautīgu ceļotāju, kurš dodas pasaulē, sastop pārbaudījumus un katrā nākamajā solī izmanto iepriekš gūto pieredzi. Sprīdīša tēls šajā projektā nav “jautrs dārznieks ar lāpstu”; tas ir **mazs pētnieks, kurš dodas plašajā pasaulē un mācās no ceļa**.

Šis ceļš ir projekta metafora: **mazs pētniecības dzinējs dodas plašajā tīmeklī, krāj noderīgus rīkus un pieredzi, atceras ceļu un atgriežas ar strukturētiem pierādījumiem, nevis minējumiem.**

The project name is inspired by **Anna Brigadere’s “Sprīdītis”**. In the play, Sprīdītis is a small boy who leaves home to search for happiness, meets one trial after another, and grows through the experience gained on the road. His determination and ingenuity matter, and what he learns or receives in earlier encounters helps him in later ones.

That journey is the project metaphor: **a small research engine goes out into the wider web, gathers useful tools and experience, remembers the path, and comes back with structured evidence instead of guesses.**

Avots / Background: [Nacionālā enciklopēdija — “Sprīdītis”](https://enciklopedija.lv/skirklis/128907-%E2%80%9CSpr%C4%ABd%C4%ABtis%E2%80%9D)

## 🧠 Galvenais virziens: Research Memory / North star: Research Memory

Sprīdītim jāatceras ne tikai **ko** tas atrada, bet arī **kā** tas to atrada.  
Sprīdītis is intended to remember not only **what** it found, but **how** it found it:

```text
ResearchProject
      ↓
Query / Seed
      ↓
SearchProvider
      ↓
Domain
      ↓
HTML link / Sitemap / RSS / Atom / JSON Feed
      ↓
Page
      ↓
Extraction method + confidence
      ↓
MarketEntity
      ↓
Observation
      ↓
Change event
      ↓
Research Memory
      ↓
next run becomes more selective
```

Tāpēc ilgtermiņa atšķirība nav “pārmeklēt vairāk lapu”, bet:

> **atrast noderīgus avotus, atcerēties, kuri ceļi strādāja, izvairīties no atkārtota darba, pamanīt nozīmīgas izmaiņas un apstāties, kad turpmāka pārmeklēšana vairs nedod pietiekami daudz jaunu pierādījumu.**

The long-term differentiator is therefore not “crawl more pages”. It is:

> **find useful sources, remember which paths worked, avoid repeated work, detect meaningful change, and stop when additional crawling no longer adds enough new evidence.**

**Arhitektūras princips / Architecture principle:** **katram svarīgam lēmumam jābūt izskaidrojamam / every important decision should be explainable.**

---

## Latviski

### Kas ir Sprīdītis?

Sprīdītis ir eksperimentāls tirgus izpētes dzinējs, kas publiski pieejamu tīmekļa informāciju pārvērš strukturētos un pārbaudāmos datos.

Tā vietā, lai vienkārši iedotu MI milzīgu lapas tekstu ar uzdevumu "saproti, kas te notiek", Sprīdītis darbu sadala vairākos slāņos:

```text
Pētījuma jautājums
      ↓
ResearchProject
      ↓
Crawler / URL rinda
      ↓
Strukturēta datu ieguve
(JSON-LD / OpenGraph / avotu adapteri)
      ↓
MarketEntity
      ↓
Izvēles MI analīze
      ↓
SQLite novērojumi
      ↓
HTML atskaite
```

Crawleris un ekstraktori iegūst avotā pārbaudāmus faktus — piemēram, URL, nosaukumu vai cenu. MI tiek izmantots klasifikācijai, apkopošanai un papildu pazīmju noteikšanai, nevis kā vienīgais patiesības avots.

### Kur to var izmantot?

Sprīdītis ir noderīgs situācijās, kur desmitiem vai simtiem lapu manuāla pārskatīšana būtu lēna, monotona vai grūti atkārtojama.

Piemēri:

- **Produktu tirgus salīdzināšanai** — savākt produktus, cenas, pārdevējus un kategorijas no publiskiem avotiem.
- **Cenu izmaiņu novērošanai** — atkārtoti palaist vienu un to pašu pētījumu un uzkrāt vēsturi.
- **Nišas izpētei pirms jauna produkta vai pakalpojuma ieviešanas** — saprast, kas jau tiek piedāvāts un kādi modeļi atkārtojas.
- **Hobiju tirgu novērošanai** — piemēram, 3D drukas piederumi, velosipēdu detaļas, elektronika vai kolekcionējami priekšmeti.
- **Vietējo pakalpojumu salīdzināšanai** — pielāgot modeli pakalpojumu veidiem, cenām un publiski pieejamiem nosacījumiem.
- **Konkurentu novērošanas pamata izveidei** — atkārtojams process pārlūka grāmatzīmju un manuālu tabulu vietā.
- **Datu savākšanai atskaitei vai analīzei** — saglabājot avota URL un ieguves metadatus.
- **Savām pētniecības idejām** — definēt atslēgvārdus, izslēdzamos vārdus, sākuma avotus, crawl limitus un analizējamos laukus.

Sprīdītis nav piesaistīts vienai nozarei. Ideja ir vienu un to pašu kodolu pielāgot dažādiem tirgus izpētes uzdevumiem ar konfigurāciju.

### Pašlaik pieejams

- konfigurējami `ResearchProject` JSON faili
- universāls `MarketEntity`
- viena domēna pārmeklēšana
- kontrolēts vairāku domēnu discovery režīms
- īsts zero-seed Expedition starts
- provider-neatkarīgs `SearchProvider` slānis
- deterministisks Expedition vaicājumu ģenerators
- SearXNG JSON API provideris un offline fake provideris atkārtojamiem testiem
- persistējošs Domain Registry ar `candidate`, `active`, `blocked`, `rejected` un `failed` statusiem
- ārējo domēnu un search rezultātu audita vēsture ar providera/vaicājuma izcelsmi
- search vaicājumu, rezultātu, aktivizāciju un kļūdu skaitītāji
- sitemap atklāšana no `robots.txt` un `/sitemap.xml`
- RSS 2.0, Atom un JSON Feed discovery no HTML `rel="alternate"`
- kontekstuāla feed prioritizācija, lai sekcijas feeds būtu priekšā generic/comment feediem
- persistējošs feed state ar `ETag`, `Last-Modified`, `304 Not Modified`, `last_entry_id` un `last_published`
- `feeds` CLI komanda feed stāvokļa pārbaudei
- Domain Registry stāvokļa hidratācija pirms atkārtota run; `blocked`/`rejected` dzīves cikla stāvokļi paliek sticky
- Research Memory ar query yield, source profiles, HTTP success un productive-run signāliem
- Adaptive Expedition ar vēsturisku query/source prioritizāciju bez opaque quality score
- lokāls BM25 ar atsevišķiem title/path/domain/negative-keyword signāliem
- adaptīvs stopping ar auditējamu `STOP_REASON`, saturation un diminishing-returns logiem
- kontrolēts multi-hop discovery ar atsevišķu `discovery_depth`, per-depth budžetiem un depth limitu
- soft source-diversity frontier penalty, nezaudējot atrastās entity
- persistēts Adaptive Decision Trace (DB schema v7) query/source/diversity/depth/stop lēmumiem
- Entity Resolution ar GTIN/EAN, maker+model, maker+MPN un source-scoped SKU strong identity signāliem
- canonical entity clusteri virs source-specific `MarketEntity`/observations, nezaudējot avota provenance
- DB schema v10 ar resolution/cluster/merge audita slāņiem
- `clusters`, `explain-cluster`, `merge-clusters`, `cluster-merges` un `review-queue` CLI
- ambiguity/conflict review workflow ar guarded explicit merge; title-only un identity conflict merge netiek pieļauts
- schema.org microdata ekstrakcija starp JSON-LD un OpenGraph prioritātē
- konservatīvs DOM fallback tikai pēc strukturēto ekstraktoru neveiksmes, ar explicit valūtas un produkta-konteksta prasību
- field-level `ExtractionEvidence` ar value/source/method/confidence/evidence/extracted_at
- DB schema v11 ar `field_evidence_json` current entity provenance un nemainīgiem historical observation snapshots
- `evidence-quality` CLI ar high/medium/low, missing, mismatched/stale un default/inferred lauku auditu bez opaque score
- target-cluster-aware GTIN hard veto automātiskajā Entity Resolution, saglabājot matched + conflicting signālus
- `diff` CLI divu research run jēgpilnu izmaiņu salīdzināšanai ar before/after/evidence detaļām
- Change Detection entity, price, seller/description/image, source, domain un feed lifecycle izmaiņām
- DB schema v12 ar vēsturiskiem run-scoped `feed_snapshots` un trace sasaisti
- `watch` CLI inkrementālai atkārtotai izpētei ar `--once`, `--interval-seconds` un `--max-cycles`
- coverage-aware Watch presence/source-change filtrēšana ar auditējamu `suppressed_uncertain`
- change-only `spriditis.watch.change.v1` JSONL eksports
- cycle/change hook kontrakti ārējiem scheduling/notifikāciju adapteriem; change hook saņem verificētu event payload
- Watch feed refresh atkārtoti izmanto DB saglabātos `ETag` / `Last-Modified` un korekti apstrādā `304 Not Modified`
- Watch atkārtoti izmanto Research Memory query/source prioritizācijai un saglabā lēmumus Decision Trace
- opt-in async crawler ar bounded global/per-domain concurrency un bounded pending/backpressure
- deterministisks async fetch-wave planneris, kas saglabā frontier prioritāti un crawl budžetus
- thread-local `requests` transports caur `asyncio.to_thread()`, nepievienojot jaunu HTTP dependency
- bounded retry budžeti transient HTTP/network kļūdām ar `Retry-After` un exponential backoff
- run-scoped adaptive per-domain politeness ar pressure-up / success-down delay semantiku
- async diagnostika: logical fetch jobs, HTTP attempts, retries, exhausted retries, pressure events, wait time, peak concurrency un final domain delay
- sequential/async semantic parity tests un izmērāms paralēla I/O ātruma ieguvums
- search duplicate rate ar atsevišķiem raw / unique / duplicate / filtered skaitītājiem
- freshness/staleness signāli ar skaidru `last_useful_at → last_crawled → last_seen` pamatu un konfigurējamu stale slieksni
- page lineage `page_visits` audita dati ar source type, source URL, depth, outcome un HTTP statusu
- `memory`, `explain` un `trace` CLI komandas Research Memory inspekcijai
- URL līmeņa safety bloķēšana vairs nepārvērš visu domēnu par sticky `blocked`
- URL prioritizācija un crawl budžeti katram domēnam
- `robots.txt` pārbaude
- drošības filtri crawlerim
- JSON-LD `Product` datu ieguve
- OpenGraph produktu datu ieguve
- avotu adapteru arhitektūra
- Gemini provideris
- lokāls fallback klasifikators
- MI batch analīze
- retry/backoff Gemini `429` un `503` gadījumiem
- SQLite projekti, skrējieni, objekti, novērojumi, domēni un discovery vēsture
- versiju neitrāla `data/spriditis.db` ar migrāciju pamatu
- HTML atskaites
- CLI
- servisa slānis nākotnes UI/API

### Kas vēl nav gatavs?

Pieņemtais attīstības virziens ir redzams README sākumā sadaļā **Development journey / Attīstības ceļš**. Publiskā bāze ir `3.3.0-alpha.10` Async crawler + adaptive politeness. Nākamais numurētais milestone vēl nav izvēlēts; kandidāti paliek detalizētajā backlogā. Iebūvēts daemon scheduler, background-job rinda un webhook serveris joprojām apzināti nav daļa no publiskā kodola.

Detalizēti skatīt [ROADMAP.md](ROADMAP.md).

### Ātrais sākums

Nepieciešams Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Apskati pieejamos šablonus:

```powershell
python main.py templates
```

Izveido universālu produktu tirgus pētījumu:

```powershell
python main.py create --preset generic_products --output projects\mans_tirgus.json
```

Pielāgo failā:

- nosaukumu
- atslēgvārdus
- izslēdzamos atslēgvārdus
- sākuma URL
- kategorijas
- analizējamos atribūtus
- crawl limitus

Pārbaudi konfigurāciju:

```powershell
python main.py validate --project projects\mans_tirgus.json
```

Palaid bez MI:

```powershell
python main.py run --project projects\mans_tirgus.json --max-pages 10 --no-ai --no-email
```

Palaid ar Gemini:

```powershell
python main.py run --project projects\mans_tirgus.json --max-pages 10 --no-email
```

Palaid vienu inkrementālu Watch ciklu bez MI:

```powershell
python main.py watch --project projects\mans_tirgus.json --once --no-ai --jsonl data\watch_changes.jsonl
```

Atkārtotam Watch režīmam:

```powershell
python main.py watch --project projects\mans_tirgus.json --interval-seconds 3600 --max-cycles 6 --no-ai --jsonl data\watch_changes.jsonl
```

Watch JSONL satur tikai verificētus change eventus; baseline un no-change cikli nerada tukšus heartbeat ierakstus. Presence/source-change kandidāti bez salīdzināma URL coverage tiek auditējami apspiesti kā `suppressed_uncertain`.

Apskati Domain Registry:

```powershell
python main.py domains --project projects\mans_tirgus.json
python main.py domains --project projects\mans_tirgus.json --status candidate
python main.py domains --project projects\mans_tirgus.json --details
```

Apskati discovery lēmumu auditu:

```powershell
python main.py discoveries --project projects\mans_tirgus.json
python main.py discoveries --project projects\mans_tirgus.json --action activated
```

Apskati deterministiski ģenerēto Expedition meklēšanas plānu:

```powershell
python main.py queries --project projects\expedition_example.json
```

Apskati Research Memory:

```powershell
python main.py memory --project projects\mans_tirgus.json
python main.py explain --project projects\mans_tirgus.json --domain example.com
python main.py trace --project projects\mans_tirgus.json --run 1
```

`memory` rāda query yield, search deduplikāciju, source profiles un freshness signālus. `explain` apkopo viena domēna auditējamo vēsturi, bet `trace` sasaista viena run page lineage, discovery eventus un observations. Alpha4 šos signālus **krāj un izskaidro**. Alpha5 tos izmanto query/source prioritizācijai, lokālai relevance izvēlei, controlled multi-hop, source diversity un stopping lēmumiem; šie lēmumi tiek saglabāti arī Adaptive Decision Trace.

Pilno zero-seed Expedition plūsmu bez ārēja meklētāja var pārbaudīt ar:

```powershell
python tests\expedition_integration_test.py
```

Sprīdītis tagad izmanto versiju neitrālu SQLite datubāzi:

```text
data/spriditis.db
```

Vecāku datubāzi var droši pārnest ar:

```powershell
python main.py migrate-db --from-db ..\vecaka_versija\data\spriditis_v31.db
```

Migrācija izmanto SQLite backup mehānismu un pēc kopēšanas piemēro aktuālo shēmas migrāciju.

### Vienkāršs piemērs

Pieņemsim, ka gribi izpētīt ergonomisko darba krēslu tirgu.

```json
{
  "id": "darba_kresli",
  "name": "Ergonomisko darba krēslu tirgus",
  "research_type": "product_market",
  "entity_type": "product",
  "languages": ["lv"],
  "countries": ["LV"],
  "keywords": [
    "ergonomisks krēsls",
    "biroja krēsls",
    "jostasvietas atbalsts",
    "mesh"
  ],
  "negative_keywords": [
    "remonta instrukcija",
    "rezerves daļas"
  ],
  "seed_urls": [
    "https://example.com/biroja-kresli"
  ]
}
```

Ar citu konfigurāciju tas pats kodols var pētīt tīkla iekārtas, velosipēdu piederumus, vietējos pakalpojumus, rokdarbu tirgu, programmatūras abonementus vai pavisam citu publiski pieejamu tirgu.

### MI darbība

Gemini nav obligāts.

Sprīdītis vispirms savāc un strukturē tirgus objektus un tikai pēc tam nodod tos batch analīzei.

Ja Gemini pēc atkārtotiem mēģinājumiem nav pieejams, Sprīdītis izmanto lokālo fallback klasifikatoru un pētījumu pabeidz.

```env
GEMINI_MODEL=gemini-3.8-flash
GEMINI_BATCH_SIZE=10
GEMINI_REQUESTS_PER_MINUTE=5
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=5
```

### Atbildīga pārmeklēšana

Sprīdītis paredzēts likumīgai publiski pieejamas informācijas izpētei.

Crawlerī ir `robots.txt` atbalsts, pauzes starp pieprasījumiem, lapu un domēnu limiti, URL filtrēšana un aizsardzība pret privātiem/localhost mērķiem.

Lietotājs pats ir atbildīgs par vietņu noteikumu, piemērojamo tiesību aktu un datu izmantošanas prasību ievērošanu.

Sprīdīti nevajadzētu izmantot autentifikācijas, piekļuves kontroles, paywall, CAPTCHA vai citu tehnisku ierobežojumu apiešanai.

### Projekta statuss

Pašreizējais publiskais atskaites punkts ir **Sprīdītis 3.3.0-alpha.9 — Watch mode**.

**3.3.0-alpha.9 — Watch mode** ir pilnībā validēts. Tas pievieno coverage-aware inkrementālu atkārtotu izpēti, change-only JSONL, cycle/change hook kontraktus ar verificētu event payload, DB-persistētu ETag/Last-Modified/304 feed refresh un Research Memory atkārtotu izmantošanu nākamajos Watch ciklos.

Pilnais alpha9 regression gate ir izpildīts: **55/55 deterministiskie testi iziet**. Reālā 60-lapu Watch pārbaudē coverage-aware slānis apspieda 42 nepietiekami pierādītus presence kandidātus un neizveidoja nevienu viltus change eventu.

Alpha9 neievieš iebūvētu daemon scheduler, background-job rindu vai webhook serveri; publiskā kodola integrācijas virsmas ir CLI loop, JSONL un hook kontrakti.

Šis ir alpha projekts, tāpēc līdz stabilai versijai iespējamas arī nesavietojamas izmaiņas.

### Open-core virziens

Publiskais repozitorijs paredzēts kā patstāvīgi lietojams pētniecības kodols. Nākotnē hostētas, komerciālas vai operacionālas funkcijas var tikt attīstītas atsevišķi.

Skatīt [docs/OPEN_CORE.md](docs/OPEN_CORE.md).

### Atbalsti projektu

Ja Sprīdītis tev šķiet noderīgs un vēlies atbalstīt tā tālāku attīstību:

☕ **[Buy Me a Coffee](https://buymeacoffee.com/craftin)**

### Drošība un iesaiste

Nekad nepublicē `.env`, API atslēgas, SMTP app paroles, cookies vai citus piekļuves datus.

- [Drošības politika](SECURITY.md)
- [Iesaisties projektā](CONTRIBUTING.md)
- [Izmaiņu vēsture](CHANGELOG.md)
- [Attīstības plāns](ROADMAP.md)

### Licence

Apache License 2.0. Skatīt [LICENSE](LICENSE).

---

## English

### What is Sprīdītis?

Sprīdītis is an experimental research engine for turning public web information into structured, traceable market data.

Instead of asking an AI model to "read the whole internet and figure it out", Sprīdītis separates the work into clear stages:

```text
Research question
      ↓
ResearchProject
      ↓
Crawler / URL frontier
      ↓
Structured extraction
(JSON-LD / OpenGraph / source adapters)
      ↓
MarketEntity
      ↓
Optional AI enrichment
      ↓
SQLite observations
      ↓
HTML report
```

The crawler and extractors are responsible for source-backed facts such as URLs, product names and prices. AI is used as an optional classification and enrichment layer, not as the primary source of truth.

### Why would I use it?

Sprīdītis is designed for situations where opening dozens or hundreds of pages manually would be slow, repetitive or inconsistent.

Examples:

- **Compare a product market** — collect products, prices, sellers and categories from public sources.
- **Monitor price changes** — run the same research repeatedly and build an observation history.
- **Explore a niche before launching something** — discover what already exists, how offers differ, and where patterns appear.
- **Track a fast-moving hobby market** — watch public listings for new models, accessories or recurring price ranges.
- **Research local services** — adapt the project model to compare providers, service types and publicly listed pricing.
- **Build a competitor watchlist** — use repeatable research projects instead of keeping scattered browser bookmarks.
- **Collect structured evidence for a report** — preserve source URLs and extraction metadata instead of relying on AI summaries alone.
- **Experiment with your own research workflow** — define keywords, negative keywords, seed sources, crawl budgets and analysis attributes.

Sprīdītis is not tied to one industry. The same core is intended to support very different research projects through configuration.

### Current capabilities

- configurable `ResearchProject` JSON files
- generic `MarketEntity` model
- single-domain crawling
- controlled multi-domain discovery mode
- true zero-seed Expedition bootstrap
- provider-neutral `SearchProvider` abstraction
- deterministic Expedition query generator
- SearXNG JSON API provider plus offline fake provider for repeatable tests
- persistent Domain Registry with `candidate`, `active`, `blocked`, `rejected` and `failed` states
- external-domain and search-result discovery audit trail with provider/query provenance
- search query/result/activation/error run counters
- sitemap discovery from `robots.txt` and `/sitemap.xml`
- RSS 2.0, Atom and JSON Feed discovery from HTML `rel="alternate"`
- context-aware feed ordering so section feeds outrank generic/comment feeds
- persistent feed state with `ETag`, `Last-Modified`, `304 Not Modified`, `last_entry_id` and `last_published`
- `feeds` CLI inspection
- Domain Registry hydration before repeated runs, preserving sticky `blocked`/`rejected` lifecycle states
- opt-in async crawler with bounded global/per-domain concurrency and bounded pending/backpressure
- deterministic async fetch-wave planning that preserves frontier priority and crawl budgets
- thread-local `requests` transport via `asyncio.to_thread()` without adding a second HTTP dependency
- bounded retry budgets for transient HTTP/network failures with `Retry-After` and exponential backoff
- run-scoped adaptive per-domain politeness with pressure-up / success-down delay behavior
- async diagnostics for logical fetch jobs, HTTP attempts, retries, exhausted retries, pressure events, wait time, peak concurrency and final domain delay
- sequential/async semantic-parity coverage plus measurable parallel-I/O speedup
- Research Memory with query yield, source profiles, HTTP success and productive-run signals
- search duplicate rate with separate raw / unique / duplicate / filtered counters
- freshness/staleness signals with an explicit `last_useful_at → last_crawled → last_seen` basis and configurable stale threshold
- auditable `page_visits` lineage with source type, source URL, depth, outcome and HTTP status
- `memory`, `explain` and `trace` CLI inspection
- URL-scoped safety blocks no longer make the whole domain sticky `blocked`
- URL prioritization and per-domain crawl budgets
- `robots.txt` checks
- crawler safety filters
- JSON-LD `Product` extraction
- OpenGraph product extraction
- source-specific adapters
- Gemini provider abstraction
- local fallback classifier
- batched AI analysis
- retry/backoff for Gemini `429` and `503`
- SQLite projects, runs, entities, observations, domains and discovery history
- version-neutral `data/spriditis.db` with migration foundation
- HTML reports
- CLI
- service boundary prepared for future UI/API clients

### What is not implemented yet?

The public alpha deliberately does not pretend unfinished features are complete.

The accepted direction is shown in the **Development journey** above. The public baseline is `3.3.0-alpha.10` Async crawler + adaptive politeness. The next numbered milestone has not been selected yet; candidates remain in the detailed backlog. A built-in daemon scheduler, background-job queue and webhook server are still deliberately outside the public core.

See the detailed [ROADMAP.md](ROADMAP.md).

### Quick start

Requires Python 3.11+.

#### Windows / PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

List available templates:

```powershell
python main.py templates
```

Create a generic product-research project:

```powershell
python main.py create --preset generic_products --output projects\my_market.json
```

Edit `projects\my_market.json` and set your own:

- project name
- keywords
- negative keywords
- seed URLs
- categories
- desired attributes
- crawl limits

Validate it:

```powershell
python main.py validate --project projects\my_market.json
```

Run without AI:

```powershell
python main.py run --project projects\my_market.json --max-pages 10 --no-ai --no-email
```

Run with Gemini:

```powershell
python main.py run --project projects\my_market.json --max-pages 10 --no-email
```

Run one incremental Watch cycle without AI:

```powershell
python main.py watch --project projects\my_market.json --once --no-ai --jsonl data\watch_changes.jsonl
```

For bounded repeated Watch execution:

```powershell
python main.py watch --project projects\my_market.json --interval-seconds 3600 --max-cycles 6 --no-ai --jsonl data\watch_changes.jsonl
```

Watch JSONL contains only verified change events; baseline and no-change cycles do not emit empty heartbeat records. Presence/source-change candidates without comparable URL coverage are audited separately as `suppressed_uncertain`.

Inspect the Domain Registry:

```powershell
python main.py domains --project projects\my_market.json
python main.py domains --project projects\my_market.json --status candidate
python main.py domains --project projects\my_market.json --details
```

Inspect discovery decisions:

```powershell
python main.py discoveries --project projects\my_market.json
python main.py discoveries --project projects\my_market.json --action activated
```

Preview deterministic Expedition search queries:

```powershell
python main.py queries --project projects\expedition_example.json
```

Inspect Research Memory:

```powershell
python main.py memory --project projects\my_market.json
python main.py explain --project projects\my_market.json --domain example.com
python main.py trace --project projects\my_market.json --run 1
```

`memory` exposes query yield, search deduplication, source profiles and freshness signals. `explain` summarizes auditable history for one domain, while `trace` connects page lineage, discovery events and observations for one run. Alpha4 **records and explains** these signals; adaptive prioritization based on memory is deliberately deferred to alpha5.

The included Expedition integration test validates a complete zero-seed bootstrap without depending on a live search service:

```powershell
python tests\expedition_integration_test.py
```

Sprīdītis now uses a version-neutral SQLite database:

```text
data/spriditis.db
```

To migrate an older database safely:

```powershell
python main.py migrate-db --from-db ..\older_build\data\spriditis_v31.db
```

The migration uses SQLite's backup API and applies the current schema migration automatically.

### Example research project

```json
{
  "id": "home_office_chairs",
  "name": "Home office chair market",
  "research_type": "product_market",
  "entity_type": "product",
  "languages": ["en"],
  "countries": ["LV"],
  "keywords": [
    "ergonomic chair",
    "office chair",
    "lumbar support",
    "mesh chair"
  ],
  "negative_keywords": [
    "repair manual",
    "spare parts"
  ],
  "seed_urls": [
    "https://example.com/category/office-chairs"
  ]
}
```

A different project could just as easily target bicycle accessories, local printing services, home networking gear, handmade products, software subscriptions or another public market.

### AI behavior

Gemini is optional.

Sprīdītis crawls and extracts entities first. Only then are already-extracted entities sent in batches for classification/enrichment.

This matters for two reasons:

1. AI outages do not stop the crawling stage.
2. A batch can classify multiple entities with fewer API requests.

If Gemini remains unavailable after retry/backoff, Sprīdītis falls back to a local classifier and completes the research run.

Example `.env` settings:

```env
GEMINI_MODEL=gemini-3.8-flash
GEMINI_BATCH_SIZE=10
GEMINI_REQUESTS_PER_MINUTE=5
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=5
```

Provider limits and model availability are external dependencies and may change.

### Responsible crawling

Sprīdītis is intended for legitimate research on publicly accessible information.

The crawler includes `robots.txt` support, crawl delays, page/domain limits, URL filtering, and protections against private/localhost targets.

Users are responsible for complying with applicable laws, website terms and data-use requirements.

Do not use Sprīdītis to bypass authentication, access controls, paywalls, CAPTCHAs or other technical restrictions.

### Architecture

```text
spriditis/
├── api/          # service boundary for future UI/API clients
├── ai/           # AI provider abstraction and implementations
├── core/         # ResearchProject, MarketEntity, run models
├── crawler/      # frontier, policies, robots, crawl engine
├── extraction/   # structured-data extractors
├── reports/      # report generation
├── search/       # SearchProvider, query generation, SearXNG/fake providers
├── sources/      # source-specific adapters
└── storage/      # persistence layer

projects/         # research project configurations
tests/            # smoke / schema / batch checks
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Project status

The current public baseline is **Sprīdītis 3.3.0-alpha.9 — Watch mode**.

**3.3.0-alpha.9 — Watch mode** is fully validated. It adds coverage-aware incremental repeated research, change-only JSONL, cycle/change hook contracts with verified event payloads, persisted ETag/Last-Modified/304 feed refresh, and Research Memory reuse across Watch cycles.

The complete alpha9 regression gate passed: **55/55 deterministic tests**. In a real 60-page Watch validation, coverage-aware comparison suppressed 42 insufficiently proven presence candidates and emitted zero false change events.

Alpha9 does not include a built-in daemon scheduler, background-job queue or webhook server; the public-core integration surfaces are the CLI loop, JSONL and hook contracts.

This is alpha software. Expect breaking changes before a stable release.

### Open-core direction

The public repository is intended to remain useful as a standalone research engine. Future hosted, commercial or operational capabilities may be developed separately.

See [docs/OPEN_CORE.md](docs/OPEN_CORE.md).

### Support the project

If Sprīdītis is useful to you, you can support continued development here:

☕ **[Buy Me a Coffee](https://buymeacoffee.com/craftin)**

### Security and contributing

Never commit `.env`, API keys, SMTP app passwords, cookies or other credentials.

- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)

### License

Apache License 2.0. See [LICENSE](LICENSE).

---
