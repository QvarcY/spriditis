# Open-Core Direction

Sprīdītis is being developed with an open-core direction.

This document explains the intended project boundary. It does **not** add restrictions to the Apache License 2.0.

## Public core

The public repository is intended to remain a useful standalone research engine.

The public core currently includes or is intended to include:

- research project configuration;
- crawler and crawl frontier;
- URL-safety and robots policy;
- Domain Registry and controlled discovery;
- structured-data extraction;
- source adapters;
- AI-provider abstraction and non-AI fallback;
- SQLite persistence and migrations;
- research observations;
- reports;
- CLI;
- service boundary for future API/UI clients;
- tests for the public behavior.

The public core should not require a commercial hosted service to perform its basic research workflow.

## Possible product layer

Future product or hosted capabilities may be developed separately. Examples could include:

- hosted web UI;
- authentication and organizations;
- managed job queues;
- recurring schedules;
- managed SearchProvider infrastructure;
- centralized monitoring;
- team collaboration;
- billing;
- hosted storage and retention;
- operational dashboards.

These are directions, not promises or a fixed commercial plan.

## License boundary

Code already released in this repository under Apache License 2.0 remains available under that license.

Moving future product-layer development to a separate private repository does not retroactively change the rights granted for public releases.

See [LICENSE](../LICENSE).

## Contribution boundary

Contributions to the public repository should generally improve the reusable research core rather than add assumptions tied to one private deployment, customer, business, or hosted environment.

Where a feature needs both a generic core and a hosted implementation, the preferred design is:

```text
public interface / reusable core
            ↓
optional provider or product implementation
```

## Why this split?

The goal is to keep Sprīdītis useful for developers and researchers who want to run it themselves, while leaving room for more operational or hosted capabilities later.

---

## Latviski

Sprīdītis tiek veidots open-core virzienā.

Publiskais repozitorijs ir paredzēts kā patstāvīgi lietojams pētniecības kodols. Nākotnē hostētas, komandu darba, norēķinu, monitoringa vai citas produkta līmeņa funkcijas var tikt veidotas atsevišķi.

Tas nemaina jau publiskotā koda Apache License 2.0 tiesības. Publiski izlaistais kods paliek pieejams ar licenci, ar kuru tas tika publicēts.
