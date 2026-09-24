from __future__ import annotations

from spriditis.core.projects import ResearchProject

from .models import SearchQuery


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _memory_row_for_query(
    query: str,
    query_memory: list[dict],
    provider: str,
) -> dict | None:
    key = _clean(query).casefold()
    matches = [
        row
        for row in query_memory
        if _clean(str(row.get("query_text", ""))).casefold() == key
        and str(row.get("provider", "")) == provider
    ]
    if not matches:
        return None

    # query_memory is normally unique per provider/query. Keeping an explicit
    # deterministic fallback makes this safe for injected/test data too.
    return max(
        matches,
        key=lambda row: (
            float(row.get("productive_domain_rate", 0.0) or 0.0),
            int(row.get("productive_domains", 0) or 0),
            int(row.get("runs", 0) or 0),
        ),
    )


def build_search_queries(
    project: ResearchProject,
    *,
    query_memory: list[dict] | None = None,
    provider: str | None = None,
) -> list[SearchQuery]:
    """Build a deterministic, auditable query plan from project configuration."""
    limit = project.search.max_queries
    if limit <= 0:
        return []

    candidates: list[SearchQuery] = []
    seen: set[str] = set()

    def add(query: str, reason: str):
        query = _clean(query)
        key = query.casefold()
        if not query or key in seen:
            return
        seen.add(key)
        candidates.append(SearchQuery(query=query, reason=reason))

    for query in project.search.queries:
        add(query, "configured")

    keywords = []
    keyword_seen = set()
    for keyword in project.keywords:
        clean = _clean(keyword)
        key = clean.casefold()
        if clean and key not in keyword_seen:
            keyword_seen.add(key)
            keywords.append(clean)

    if len(keywords) >= 3:
        add(" ".join(keywords[:3]), "keyword_bundle")
    elif keywords:
        add(" ".join(keywords[:2]), "keyword_bundle")

    # Pairs are intentionally deterministic; no AI is needed to create the plan.
    for i in range(len(keywords)):
        for j in range(i + 1, len(keywords)):
            add(f"{keywords[i]} {keywords[j]}", "keyword_pair")

    for keyword in keywords:
        add(keyword, "keyword")

    memory_rows = list(query_memory or [])
    provider_name = (provider or "").strip()
    if memory_rows and provider_name:
        annotated: list[SearchQuery] = []
        for query in candidates:
            row = _memory_row_for_query(
                query.query,
                memory_rows,
                provider_name,
            )
            if row is None:
                annotated.append(query)
                continue

            productive_domains = int(
                row.get("productive_domains", 0) or 0
            )
            state = (
                "productive"
                if productive_domains > 0
                else "nonproductive"
            )
            annotated.append(
                query.model_copy(
                    update={
                        "memory_state": state,
                        "memory_productive_domain_rate": float(
                            row.get("productive_domain_rate", 0.0)
                            or 0.0
                        ),
                        "memory_productive_domains": productive_domains,
                        "memory_unique_domains": int(
                            row.get("unique_domains", 0) or 0
                        ),
                        "memory_runs": int(row.get("runs", 0) or 0),
                    }
                )
            )
        candidates = annotated

    configured = [
        query for query in candidates
        if query.reason == "configured"
    ]
    generated = [
        query for query in candidates
        if query.reason != "configured"
    ]

    # Explicit user queries always keep their configured order.
    # Generated queries use three transparent bands:
    # productive history -> untested exploration -> known nonproductive.
    def adaptive_key(item: tuple[int, SearchQuery]):
        index, query = item
        if query.memory_state == "productive":
            band = 0
        elif query.memory_state == "untested":
            band = 1
        else:
            band = 2

        rate = query.memory_productive_domain_rate or 0.0
        return (
            band,
            -rate if band == 0 else 0.0,
            -query.memory_productive_domains if band == 0 else 0,
            -query.memory_runs if band == 0 else 0,
            index,
        )

    generated = [
        query
        for _, query in sorted(
            enumerate(generated),
            key=adaptive_key,
        )
    ]

    return (configured + generated)[:limit]
