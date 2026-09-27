from __future__ import annotations

from spriditis.core.projects import ResearchProject

from .models import SearchQuery


_QUERY_STOPWORDS = {
    "atrodi",
    "mekle",
    "meklē",
    "salidzini",
    "salīdzini",
    "piedavajumus",
    "piedāvājumus",
    "piedavajumi",
    "piedāvājumi",
    "cena",
    "cenas",
    "latvija",
    "latvijā",
    "latvijas",
    "veikals",
    "veikali",
    "veikalos",
    "find",
    "compare",
    "offers",
    "offer",
    "price",
    "prices",
    "shop",
    "shops",
    "store",
    "stores",
    "latvia",
    "un",
    "and",
    "the",
    "in",
}


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _dedupe_terms(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean = _clean(value)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)

    return result


def _target_identity_queries(
    project: ResearchProject,
    keywords: list[str],
) -> list[tuple[str, str]]:
    target_terms = _dedupe_terms(project.analysis.target_identity_terms)
    anchor_terms = {
        term.casefold()
        for term in _dedupe_terms(
            project.analysis.target_identity_anchor_terms
        )
    }
    if not target_terms or not anchor_terms:
        return []

    anchor_index = next(
        (
            index
            for index, keyword in enumerate(keywords)
            if keyword.casefold() in anchor_terms
        ),
        -1,
    )

    prefix: list[str] = []
    if anchor_index > 0:
        for keyword in reversed(keywords[:anchor_index]):
            key = keyword.casefold()
            if key in _QUERY_STOPWORDS:
                continue
            if len(prefix) >= 3:
                break
            prefix.append(keyword)
        prefix.reverse()

    target_phrase = " ".join(_dedupe_terms(
        prefix + target_terms + project.analysis.required_evidence_terms
    ))
    if not target_phrase:
        return []

    language = project.languages[0].casefold() if project.languages else ""
    locale_terms = [
        ("Latvija" if language == "lv" else "Latvia")
        if country.upper() == "LV" else country
        for country in project.countries if country.strip()
    ]
    price_term = "cena" if language == "lv" else "price"
    shop_terms = (
        ["veikals"] if language == "lv" else ["shop"]
    )

    queries: list[tuple[str, str]] = []

    if locale_terms:
        queries.append(
            (
                " ".join([target_phrase, *locale_terms]),
                "target_identity_locale",
            )
        )

    queries.append(
        (
            " ".join([target_phrase, price_term]),
            "target_identity_price",
        )
    )

    if locale_terms:
        queries.append(
            (
                " ".join([target_phrase, *shop_terms, *locale_terms]),
                "target_identity_shop",
            )
        )

    queries.append((target_phrase, "target_identity_bundle"))

    return queries


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
    recovery: bool = False,
    exclude_queries: set[str] | None = None,
) -> list[SearchQuery]:
    """Build a deterministic, auditable query plan from project configuration."""
    limit = (
        project.search.max_recovery_queries
        if recovery else project.search.max_queries
    )
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

    keywords = _dedupe_terms(project.keywords)

    target_queries = _target_identity_queries(project, keywords)
    for query, reason in target_queries:
        add(query, reason)

    required_terms = [
        _clean(term).casefold()
        for term in project.analysis.required_evidence_terms
        if _clean(term)
    ]

    if required_terms:
        constraint_keywords: list[str] = []
        constraint_keys: set[str] = set()

        for term in required_terms:
            matched = next(
                (
                    keyword
                    for keyword in keywords
                    if keyword.casefold() == term
                    or keyword.casefold().startswith(term)
                ),
                None,
            )

            value = matched or term
            key = value.casefold()

            if key not in constraint_keys:
                constraint_keys.add(key)
                constraint_keywords.append(value)

        anchors = [
            keyword
            for keyword in keywords
            if not any(
                keyword.casefold() == term
                or keyword.casefold().startswith(term)
                for term in required_terms
            )
        ]

        # Keep hard constraints in the first generated discovery query.
        # Try progressively smaller anchor sets so even a short configured
        # query gets a distinct constraint-preserving fallback.
        for anchor_count in (2, 1, 0):
            before = len(candidates)

            add(
                " ".join(
                    anchors[:anchor_count]
                    + constraint_keywords
                ),
                "required_evidence_bundle",
            )

            if len(candidates) > before:
                break

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

    if target_queries:
        candidates = [
            query for query in candidates
            if query.reason == "configured"
            or query.reason.startswith("target_identity_")
        ]
    if recovery:
        candidates = [
            query for query in candidates
            if query.reason.startswith("target_identity_")
        ]
    excluded = {_clean(query).casefold() for query in (exclude_queries or set())}
    candidates = [query for query in candidates if query.query.casefold() not in excluded]

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
