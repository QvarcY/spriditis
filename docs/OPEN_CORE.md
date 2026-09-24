# Sprīdītis — open-core virziens / Open-core direction

---

# Latviski

Sprīdītis tiek attīstīts open-core virzienā. Šis dokuments apraksta iecerēto projekta robežu un **neievieš papildu ierobežojumus Apache License 2.0**.

## Publiskais kodols

Publiskajam repozitorijam jāpaliek patstāvīgi lietojamam pētniecības dzinējam.

Publiskajā kodolā ietilpst vai ir paredzēts ietvert:
- research project konfigurāciju;
- crawler un URL frontier;
- URL drošību un robots policy;
- Domain Registry un discovery;
- SearchProvider abstrakciju;
- Feed Discovery;
- strukturēto ekstrakciju;
- avotu adapterus;
- Research Memory signālus;
- evidence/provenance;
- AI provider abstrakciju un non-AI fallback;
- SQLite persistence/migrations;
- observations/change events;
- reports;
- CLI;
- servisa robežu nākotnes API/UI;
- publiskās uzvedības testus.

Pamata research workflow nedrīkst prasīt komerciālu hostētu servisu vai obligātu maksas API.

## Iespējamais produkta slānis

Atsevišķi nākotnē var tikt attīstīti:
- hostēts web UI;
- autentifikācija/organizācijas;
- managed job queues;
- recurring schedules;
- managed SearchProvider infrastruktūra;
- centralizēts monitorings;
- komandu sadarbība;
- billing;
- hostēta datu glabāšana/retention;
- operacionālie dashboardi.

Tie ir virzieni, nevis solījums vai fiksēts komerciālais plāns.

## Licences robeža

Kods, kas jau publicēts ar Apache License 2.0, paliek pieejams ar šo licenci. Nākotnes privāts produkta slānis retroaktīvi nemaina publisko relīžu tiesības.

Skatīt [LICENSE](../LICENSE).

## Contribution robeža

Publiskā repozitorija uzlabojumiem parasti jāstiprina reusable research core, nevis jāievieš viena privāta deployment/customer/business pieņēmumi.

Vēlamais modelis:
```text
public interface / reusable core
            ↓
optional provider or product implementation
```

---

# English

Sprīdītis is being developed with an open-core direction. This document describes the intended project boundary and **does not add restrictions to the Apache License 2.0**.

## Public core

The public repository should remain a useful standalone research engine.

The public core includes or is intended to include:
- research project configuration;
- crawler and URL frontier;
- URL safety and robots policy;
- Domain Registry and discovery;
- SearchProvider abstraction;
- Feed Discovery;
- structured extraction;
- source adapters;
- Research Memory signals;
- evidence/provenance;
- AI-provider abstraction and non-AI fallback;
- SQLite persistence/migrations;
- observations/change events;
- reports;
- CLI;
- service boundary for future API/UI;
- tests for public behavior.

The basic research workflow should not require a commercial hosted service or mandatory paid API.

## Possible product layer

Future separate product/hosted capabilities may include:
- hosted web UI;
- authentication/organizations;
- managed job queues;
- recurring schedules;
- managed SearchProvider infrastructure;
- centralized monitoring;
- team collaboration;
- billing;
- hosted storage/retention;
- operational dashboards.

These are directions, not promises or a fixed commercial plan.

## License boundary

Code already released under Apache License 2.0 remains available under that license. Future private product-layer work does not retroactively change rights granted for public releases.

See [LICENSE](../LICENSE).

## Contribution boundary

Public-repository contributions should generally improve the reusable research core rather than hard-code one private deployment/customer/business.

Preferred model:
```text
public interface / reusable core
            ↓
optional provider or product implementation
```
