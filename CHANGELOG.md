# Changelog

## [3.2.0-alpha.3]

### Added
- persistent CLI view of the discovery audit trail
- `discoveries --action ...` filtering
- activated-domain count in run summaries
- controlled offline multi-domain crawler integration test

### Validated
- relevant external domain can move from unseen → active → crawled
- domain-budget overflow remains a candidate with `domain_budget_reached`
- blocked social domains cannot activate even with high relevance
- per-domain page budget prevents extra pages from being crawled
- discovery activation is preserved as an auditable event

## [3.2.0-alpha.2]

### Added
- schema migration foundation (`PRAGMA user_version` + schema metadata)
- safe SQLite backup migration command
- sitemap URL counts per domain
- detailed Domain Registry view

### Changed
- default DB path is now version-neutral: `data/spriditis.db`
- copied legacy default `DB_PATH=data/spriditis_v31.db` is treated as a migration source
- run summary distinguishes observed domains from crawled domains
- filtered Domain Registry empty states now identify the requested status
- README examples are generic and bilingual

### Fixed
- ambiguous `Domēni: N` run summary
- ambiguous empty-state message for `domains --status ...`

## [3.2.0-alpha.1]

### Added
- first-class Domain Registry
- candidate/active/blocked/failed domain states
- external-domain discovery lineage
- per-domain relevance score and crawl statistics
- robots/sitemap status tracking
- sitemap discovery from robots.txt and `/sitemap.xml`
- sitemap URL injection into the frontier
- persistent `domains` and `domain_discoveries` SQLite tables
- `python main.py domains --project ...` CLI view
- external candidates are recorded even when domain mode prevents crawling them

### Architecture
- domain discovery remains crawler-side and DB-agnostic
- persistence happens through the service/storage layer
- this creates the foundation for a future UI and active SearchProvider/Expedition mode
