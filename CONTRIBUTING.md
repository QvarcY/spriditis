# Iesaistīšanās Sprīdīša attīstībā / Contributing to Sprīdītis

---

# Latviski

Paldies par interesi palīdzēt Sprīdīša attīstībā.

Sprīdītis ir alpha stadijā. Publiskais repozitorijs ir research core, tāpēc izmaiņām jāsaglabā konfigurējamība, auditējamība, drošība pēc noklusējuma un lietojamība bez obligāta hostēta produkta.

## Īpaši noderīgi uzlabojumi

- crawler/discovery stabilitāte;
- Feed Discovery;
- strukturētie ekstraktori un avotu adapteri;
- Domain Registry / Research Memory;
- `explain` / `trace` auditability;
- crawl budgets, URL safety, robots un migration testi;
- generic research presets;
- dokumentācija;
- AI provider abstrakcijas ar non-AI fallback;
- veiktspējas uzlabojumi, kas nezaudē traceability.

Publiskajā kodolā nevajadzētu hard-code viena uzņēmuma, pārdevēja, tirgus vai privāta workflow pieņēmumus.

## Izstrādes vide

Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Nekad necommitē savu `.env`.

## Testi

Palaid vismaz ar izmaiņām saistītos testus. Izmaiņām crawling, URL handling, storage, migrations, search/discovery vai safety loģikā, kur praktiski iespējams, jāpievieno regression tests.

## Pull request aprakstā iekļauj

1. kāda problēma tiek risināta;
2. kas mainīts;
3. kā testēts;
4. vai ietekmē DB shēmu, crawl behavior, safety rules vai public configuration.

Priekšroka maziem un pārskatāmiem PR.

## Drošība

Nekad nepublicē:
- API keys;
- SMTP/app paroles;
- cookies/session tokens;
- privātus datasets;
- credentials piemēru konfigurācijās.

Izmaiņas nedrīkst apzināti apiet authentication, paywalls, CAPTCHA, robots restrictions, private-network protections vai citas piekļuves kontroles.

Security-sensitive problēmām izmanto [SECURITY.md](SECURITY.md).

## Licence

Iesniedzot contribution, tu piekrīti, ka tas var tikt izplatīts ar repozitorija Apache License 2.0.

---

# English

Thanks for your interest in improving Sprīdītis.

Sprīdītis is alpha software. The public repository is the research core, so contributions should keep it configurable, auditable, safe by default and useful without requiring a hosted product.

## Especially useful contributions

- crawler/discovery reliability;
- Feed Discovery;
- structured extractors and source adapters;
- Domain Registry / Research Memory;
- `explain` / `trace` auditability;
- tests for crawl budgets, URL safety, robots handling and migrations;
- generic research presets;
- documentation;
- AI-provider abstractions with non-AI fallback;
- performance improvements that preserve traceability.

Do not hard-code one business, seller, market or private workflow into the public core.

## Development setup

Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Never commit your `.env`.

## Tests

Run at least the tests relevant to your change. Changes affecting crawling, URL handling, storage, migrations, search/discovery or safety should include regression coverage when practical.

## Pull request description

Explain:
1. the problem;
2. what changed;
3. how it was tested;
4. whether it affects DB schema, crawl behavior, safety rules or public configuration.

Prefer small, reviewable PRs.

## Security

Never publish:
- API keys;
- SMTP/app passwords;
- cookies/session tokens;
- private datasets;
- credentials in example config.

Changes must not intentionally bypass authentication, paywalls, CAPTCHAs, robots restrictions, private-network protections or other access controls.

Use [SECURITY.md](SECURITY.md) for security-sensitive findings.

## License

By contributing, you agree that your contribution may be distributed under the repository's Apache License 2.0.
