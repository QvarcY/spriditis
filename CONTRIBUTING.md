# Contributing to Sprīdītis

Thanks for your interest in improving Sprīdītis.

Sprīdītis is currently alpha software. The public repository is the research core, so contributions should keep the crawler configurable, auditable, safe by default, and useful without requiring a hosted product.

## Good contributions

Useful contributions include:

- crawler and discovery reliability fixes;
- structured-data extractors and source adapters;
- Domain Registry improvements;
- tests for crawl budgets, URL safety, robots handling, and migrations;
- generic research presets and documentation;
- AI-provider abstractions that preserve a non-AI fallback;
- performance improvements that do not remove traceability.

Please avoid hard-coding one business, seller, market, or private workflow into the core.

## Development setup

Python 3.11+ is recommended.

### Windows / PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Do not commit your `.env` file.

## Run the checks

At minimum, run the relevant tests for your change. The current discovery baseline includes:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python tests\discovery_integration_test.py
python tests\domain_registry_test.py
python tests\db_migration_test.py
python tests\schema_test.py
python tests\batch_test.py
python tests\smoke_test.py
```

A change that affects crawling, URL handling, storage, migrations, or discovery should include a regression test when practical.

## Pull requests

Keep pull requests focused and explain:

1. what problem is being solved;
2. what changed;
3. how it was tested;
4. whether the change affects database schema, crawl behavior, safety rules, or public configuration.

Prefer small, reviewable changes over large unrelated refactors.

## Security and crawler safety

Never commit:

- API keys;
- SMTP/app passwords;
- cookies or session tokens;
- private datasets;
- credentials in example configuration.

Changes must not intentionally bypass authentication, paywalls, CAPTCHAs, robots restrictions, private-network protections, or other access controls.

If your finding is security-sensitive, follow [SECURITY.md](SECURITY.md) instead of opening a public issue with exploit details.

## Coding direction

The core architecture intentionally separates:

- research configuration;
- crawling and discovery;
- structured extraction;
- optional AI enrichment;
- persistence;
- reports;
- future API/UI consumers.

New features should preserve those boundaries when possible.

## License

By contributing, you agree that your contribution may be distributed under the repository's Apache License 2.0.

---

## Latviski

Sprīdītis pašlaik ir alpha stadijā. Īpaši noderīgi ir labojumi crawlera stabilitātei, Domain Registry, discovery loģikai, strukturēto datu ieguvei, testiem un dokumentācijai.

Publiskajā kodolā nevajadzētu iešūt viena konkrēta uzņēmuma vai tirgus loģiku. Nekad nepublicē `.env`, API atslēgas, paroles, cookies vai citus piekļuves datus.

Drošības problēmas nepublicē ar pilnām ekspluatācijas detaļām publiskā issue — izmanto [SECURITY.md](SECURITY.md) aprakstīto procesu.
