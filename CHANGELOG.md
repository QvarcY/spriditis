# Changelog

## [3.3.0-alpha.1]

### Added
- provider-neutral SearchProvider abstraction
- deterministic Expedition query generator
- SearXNG JSON API provider
- offline FakeSearchProvider
- true zero-seed Expedition bootstrap
- search-provider provenance in domain discoveries
- search query/result/activation/error run counters
- `queries` CLI command
- run overrides for search provider and domain/search budgets
- Windows-friendly direct test bootstrap

### Changed
- database schema version is now 3
- persistent Domain Registry protects sticky blocked/rejected states and avoids active → candidate downgrades
- report footer includes active-search counters

### Validation target
- a project with no seed URLs can generate a query, receive search results, activate a safe/relevant domain, and crawl it
- a second relevant domain remains a candidate when the domain budget is full
- blocked hosts remain blocked even when returned by SearchProvider
- provider and query provenance remain auditable
