# Sprīdītis

**A configurable market-research crawler and AI-assisted research engine.**  
**Pielāgojams tirgus izpētes crawleris un MI atbalstīts pētniecības dzinējs.**

[English](#english) · [Latviski](#latviski)

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
- URL prioritization and crawl budgets
- `robots.txt` checks
- crawler safety filters
- JSON-LD `Product` extraction
- OpenGraph product extraction
- source-specific adapters
- Gemini provider abstraction
- local fallback classifier
- batched AI analysis
- retry/backoff for Gemini `429` and `503`
- SQLite projects, runs, entities and observations
- HTML reports
- CLI
- service boundary prepared for future UI/API clients

### What is not implemented yet?

The public alpha deliberately does not pretend unfinished features are complete.

Planned directions include:

- richer Domain Registry
- stronger Discovery Engine
- sitemap discovery
- active SearchProvider integrations
- full Expedition mode
- competitor-research extractors
- service-market extractors
- longitudinal price/trend analysis
- web UI
- REST API
- scheduler and background jobs

See [ROADMAP.md](ROADMAP.md).

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
├── sources/      # source-specific adapters
└── storage/      # persistence layer

projects/         # research project configurations
tests/            # smoke / schema / batch checks
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Project status

Current public baseline: **Sprīdītis 3.1.0-alpha.3**.

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
- URL prioritizācija un crawl budžeti
- `robots.txt` pārbaude
- drošības filtri crawlerim
- JSON-LD `Product` datu ieguve
- OpenGraph produktu datu ieguve
- avotu adapteru arhitektūra
- Gemini provideris
- lokāls fallback klasifikators
- MI batch analīze
- retry/backoff Gemini `429` un `503` gadījumiem
- SQLite projekti, skrējieni, objekti un novērojumi
- HTML atskaites
- CLI
- servisa slānis nākotnes UI/API

### Kas vēl nav gatavs?

Plānotie attīstības virzieni:

- pilnvērtīgs Domain Registry
- jaudīgāks Discovery Engine
- sitemap atklāšana
- SearchProvider integrācijas
- pilnvērtīgs Expedition režīms
- konkurentu izpētes ekstraktori
- pakalpojumu tirgus ekstraktori
- cenu un tendenču analīze laikā
- web UI
- REST API
- scheduleris un background jobs

Skatīt [ROADMAP.md](ROADMAP.md).

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

Pašreizējais publiskais atskaites punkts: **Sprīdītis 3.1.0-alpha.3**.

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
