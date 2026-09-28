# Sprīdītis documentation contract

This file defines which document is authoritative for which kind of information and when it must be updated.

## Source-of-truth map

| Document | Owns | Must not become |
|---|---|---|
| `README.md` | current capabilities, quick start, current baseline | historical release log |
| `ROADMAP.md` | milestone state: completed / active / next / later | deployment runbook |
| `CHANGELOG.md` | chronological release/main changes | current-status dashboard |
| `docs/ARCHITECTURE.md` | how current core works, invariants, boundaries | wishlist |
| `SECURITY.md` | supported security boundary and reporting | general architecture dump |
| `docs/T20_ACCEPTANCE.md` | immutable T20 acceptance snapshot | current production status |
| `docs/W6_9B_REVIEW.md` | W6.9B technical closeout | live roadmap |
| `docs/OPEN_CORE.md` | public-core vs hosted-product boundary | feature status tracker |

## Update triggers

Documentation is required in the **same PR** when a change affects any of these:

1. user-visible behavior or CLI/API semantics;
2. architecture, persistence, transport, discovery, extraction or stopping rules;
3. safety/security boundaries;
4. milestone status;
5. test/acceptance baseline;
6. public/private open-core boundary.

Production-only facts are different: a production SHA, release path or "deployed" flag is written **after** the real deploy and health check.

## Historical vs live documents

Acceptance/closeout documents are snapshots. Once closed, keep their accepted facts intact and add a short historical-snapshot note if later states could make old SHAs look current.

Live documents (`README`, `ROADMAP`, `ARCHITECTURE`) must never knowingly describe a superseded current state.

## PR closeout checklist

Before merge:

- [ ] README still describes the current product accurately.
- [ ] ROADMAP status moved if this PR completes/starts a milestone.
- [ ] CHANGELOG has the behavior change if it belongs to current main/release history.
- [ ] ARCHITECTURE changed if control flow, state, data or invariants changed.
- [ ] SECURITY changed if trust boundaries or safeguards changed.
- [ ] Acceptance docs are either updated before closure or explicitly marked historical after closure.
- [ ] Links and named SHAs are valid for the state they claim to describe.
- [ ] No document says "pending", "not deployed", "next" or "current" if that statement became false in this PR.

After production deploy:

- [ ] record the deployed SHA/release only after health validation;
- [ ] update any live production dashboard/status section;
- [ ] do not rewrite older acceptance snapshots to match the new production state.

## Current reconciliation checkpoint

Documentation was reconciled on **2026-09-28** after W6.9A/W6.9B production acceptance.

At that checkpoint:

- public release baseline: `v3.3.0-alpha.10`;
- current production core: `19833e95281eab5356ee35736fc2da99f01211ba`;
- W6.9A Target Identity Gate: accepted;
- W6.9B Target-aware Research Orchestration: accepted and deployed.

Future work should update documentation incrementally so another full archaeology pass is unnecessary.
