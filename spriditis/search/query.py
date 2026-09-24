from __future__ import annotations

from spriditis.core.projects import ResearchProject

from .models import SearchQuery


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def build_search_queries(project: ResearchProject) -> list[SearchQuery]:
    """Build a deterministic, auditable query plan from project configuration."""
    limit = project.search.max_queries
    if limit <= 0:
        return []

    result: list[SearchQuery] = []
    seen: set[str] = set()

    def add(query: str, reason: str):
        query = _clean(query)
        key = query.casefold()
        if not query or key in seen or len(result) >= limit:
            return
        seen.add(key)
        result.append(SearchQuery(query=query, reason=reason))

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
            if len(result) >= limit:
                return result

    for keyword in keywords:
        add(keyword, "keyword")
        if len(result) >= limit:
            break

    return result
