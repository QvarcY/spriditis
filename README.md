# Sprīdītis 3.1 alpha — Research Core

Šī versija ir arhitektūras pāreja no viena CraftIN crawlera uz universālu tirgus izpētes dzinēju.

## Galvenā atšķirība no 3.0

3.0 kods pēc būtības zināja: "es meklēju CraftIN produktus".

3.1 ievieš:

- `ResearchProject` — pētījuma konfigurācija;
- `MarketEntity` — universāls tirgus objekts;
- atsevišķu crawler / extraction / AI / storage / report slāni;
- API/service slāni, kuru vēlāk izmantos UI;
- `domain`, `discovery`, `expedition` režīmu modeli;
- generisku SQLite struktūru projektiem, skrējieniem, objektiem un novērojumiem;
- projektu JSON failus, kurus nākotnē veidos UI.

`expedition` 3.1 alpha vēl pats neveic web search. Šobrīd tas uzvedas kā discovery attiecībā uz atrastām saitēm.
SearchProvider būs nākamais atsevišķais modulis.

## Instalācija

PowerShell projekta mapē:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Ja `.env` no vecās 3.0 versijas jau ir, vari pārnest tikai jaunās API/SMTP vērtības.

## 1. Pārbaudi gatavos template tipus

```powershell
python main.py templates
```

## 2. Pārbaudi presetus

```powershell
python main.py presets
```

## 3. Validē CraftIN projekta konfigurāciju

```powershell
python main.py validate --project projects\craftin_gifts.json
```

## 4. Pirmais offline/fallback tests

```powershell
python main.py run --project projects\craftin_gifts.json --max-pages 10 --no-ai --no-email
```

Tas saglabā 3.0 funkcionalitāti, bet jau caur jauno Research Core.

## 5. Ar Gemini

`.env`:

```env
GEMINI_API_KEY=JAUNĀ_ATSLĒGA
GEMINI_MODEL=gemini-3.8-flash
```

Palaid:

```powershell
python main.py run --project projects\craftin_gifts.json --max-pages 10 --no-email
```

## 6. Discovery režīms

Tagad projekts var konceptuāli iziet ārpus sākuma domēna:

```powershell
python main.py run --project projects\craftin_gifts.json --mode discovery --max-pages 30 --no-ai --no-email
```

Svarīgi: `projects\craftin_gifts.json` noklusējumā ir `max_domains: 1`.

Ja gribi reāli atļaut vairāk domēnu, projektā nomaini, piemēram:

```json
"crawl": {
  "mode": "discovery",
  "max_pages_total": 100,
  "max_pages_per_domain": 25,
  "max_domains": 10,
  "max_depth": 5,
  "delay_seconds": 2.0,
  "respect_robots": true,
  "external_link_threshold": 45
}
```

Tad:

```powershell
python main.py run --project projects\craftin_gifts.json --no-ai --no-email
```

Ārējai saitei ir jāsasniedz relevance slieksnis. Sociālie tīkli, login/cart/admin ceļi,
binārie faili, localhost un privāti IP ir bloķēti.

## 7. Jauna tirgus projekta izveide

Izveido universālu produktu presetu:

```powershell
python main.py create --preset generic_products --output projects\mans_tirgus.json
```

Tad atver `projects\mans_tirgus.json` un maini:

- `name`;
- `description`;
- `keywords`;
- `negative_keywords`;
- `seed_urls`;
- `categories`;
- `desired_attributes`;
- crawler limitus.

Kodols nav jāmaina.

## UI gatavība

Nākotnes UI nedrīkst zvanīt `crawler.engine` tieši.

Tam jāizmanto:

```python
from spriditis.api.service import run_project
```

Tas ir apzināti izveidots kā stabils servisa slānis starp UI/API un sistēmas kodolu.

## DB

3.1 pēc noklusējuma izmanto atsevišķu DB:

```text
data/spriditis_v31.db
```

Tādēļ tas nesabojā 3.0 `data/spriditis.db`.

Tabulas:

- `projects`
- `runs`
- `entities`
- `observations`

`observations` ir pamats cenu vēsturei un izmaiņu analīzei nākamajā versijā.

## Kas ir pilnībā gatavs 3.1 alpha

- produktu tirgus pētījumi;
- cenu novērojumu uzkrāšana;
- viena domēna crawl;
- kontrolēts multi-domain discovery;
- JSON-LD Product;
- OpenGraph Product;
- Meistardarbs.lv adapteris;
- fallback klasifikators;
- Gemini klasifikators;
- generisks HTML reports;
- UI-ready service boundary.

## Kas vēl ir tikai arhitektūrā/plānā

- SearchProvider, kas pats atrod jaunus seed domēnus;
- īsts `expedition` web-search režīms;
- konkurentu/uzņēmumu ekstraktors;
- pakalpojumu ekstraktors;
- trendu analītika starp vairākiem run;
- REST API;
- web UI.

Tas ir apzināti: 3.1 vispirms nostiprina pareizu kodolu, nevis samet visas funkcijas vienā monolītā.

## 3.1.0-alpha.2 — Gemini structured-output labojums

Šī versija labo Gemini Developer API kļūdu:

```text
additionalProperties is only supported in Gemini Enterprise Agent Platform mode
```

Iemesls bija AI-facing Pydantic lauks `attributes: dict[str, Any]`, kas JSON Schema ģenerēja `additionalProperties`.
Tagad Gemini-facing shēmā dinamiskie atribūti ir fiksēta tipa saraksts:

```json
[
  {"name": "materials", "value": "[\"koks\", \"akrils\"]"},
  {"name": "personalization", "value": "true"},
  {"name": "engraving_likelihood", "value": "0.85"}
]
```

Pēc saņemšanas Sprīdītis tos konvertē atpakaļ uz iekšējo `attributes` struktūru.

AFC brīdinājums no `google-genai` nav šīs kļūdas cēlonis un var parādīties pat bez function tools.


## Alpha.3 — Gemini batching, 429/503 recovery

`3.1.0-alpha.3` maina AI izpildes plūsmu.

Iepriekš:
1. crawleris atrod vienu produktu;
2. uzreiz veic vienu Gemini request;
3. atrod nākamo produktu;
4. atkal viens request.

Tas ātri iztērē free-tier requests/minute limitu.

Tagad:
1. crawleris pabeidz lapu apmeklēšanu un strukturēto datu ieguvi;
2. visi atrastie objekti nonāk analīzes rindā;
3. Gemini analizē vairākus objektus vienā batch request;
4. tikai pēc tam rezultāti tiek saglabāti un reportēti.

Noklusējums:

```env
GEMINI_BATCH_SIZE=10
GEMINI_REQUESTS_PER_MINUTE=5
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=5
```

Tātad 9 atrasti produkti parasti nozīmē **1 Gemini request**, nevis 9.

### 429

Ja API atgriež `RESOURCE_EXHAUSTED / 429`, Sprīdītis:
- nolasa `retryDelay` / `Please retry in ...s`, ja tas ir kļūdas datos;
- pagaida;
- mēģina batch vēlreiz;
- tikai pēc retry izsmelšanas izmanto lokālo fallback.

### 503

Ja modelim ir īslaicīgs `UNAVAILABLE / 503`, Sprīdītis izmanto exponential backoff:

```text
5s → 10s → 20s
```

(pēc noklusējuma; bāzi var mainīt `.env`).

### Svarīga arhitektūras izmaiņa

AI vairs nebloķē pašu crawling procesu pie katra atrastā objekta.
Tas ir būtiski nākotnes multi-domain un UI/job-queue arhitektūrai.

### Tests

```powershell
python tests\schema_test.py
python tests\batch_test.py
python tests\smoke_test.py
```

Pēc tam:

```powershell
python main.py run --project projects\craftin_gifts.json --max-pages 10 --no-email
```

Pie 9 produktiem sagaidāms aptuveni:

```text
🧠 Analīzes posms: 9 atrasti tirgus objekti.
🧠 Gemini analizēs 9 objektus 1 batch pieprasījumā(-os) (batch_size=10).
```
