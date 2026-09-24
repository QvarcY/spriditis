from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from spriditis.core.projects import ResearchProject
from spriditis.search.models import SearchHit


_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall((value or "").casefold())


def _unique_terms(value: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for token in _tokens(value):
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


@dataclass(frozen=True)
class LocalRelevance:
    hit: SearchHit
    provider_index: int
    bm25: float
    title_matches: int
    path_matches: int
    domain_matches: int
    negative_matches: int

    @property
    def audit_label(self) -> str:
        return (
            f"bm25={self.bm25:.3f}"
            f" title={self.title_matches}"
            f" path={self.path_matches}"
            f" domain={self.domain_matches}"
            f" negative={self.negative_matches}"
        )


def local_relevance_signals(
    project: ResearchProject,
    query_text: str,
    hits: list[SearchHit],
) -> list[LocalRelevance]:
    """
    Compute deterministic local relevance signals for one provider result set.

    BM25 is corpus-local: document frequency is calculated only across the
    hits returned for the current query. Field matches remain separate so the
    ranking stays auditable rather than collapsing into one opaque score.
    """
    if not hits:
        return []

    query_terms = _unique_terms(query_text)
    if not query_terms:
        query_terms = _unique_terms(" ".join(project.keywords))

    documents: list[list[str]] = []
    parsed_parts: list[tuple[str, str, str, str]] = []

    for hit in hits:
        parsed = urlparse(hit.url)
        domain = (parsed.hostname or "").casefold()
        path = unquote(parsed.path or "").casefold()
        title = (hit.title or "").casefold()
        snippet = (hit.snippet or "").casefold()
        parsed_parts.append((title, snippet, path, domain))
        documents.append(
            _tokens(" ".join([title, snippet, path, domain]))
        )

    document_count = len(documents)
    average_length = (
        sum(len(document) for document in documents) / document_count
        if document_count else 0.0
    )

    document_frequency: dict[str, int] = {}
    for term in query_terms:
        document_frequency[term] = sum(
            1 for document in documents if term in document
        )

    k1 = 1.5
    b = 0.75
    signals: list[LocalRelevance] = []

    negative_phrases = [
        item.strip().casefold()
        for item in project.negative_keywords
        if item.strip()
    ]

    for index, (hit, document, parts) in enumerate(
        zip(hits, documents, parsed_parts)
    ):
        title, snippet, path, domain = parts
        frequencies = Counter(document)
        document_length = len(document)
        bm25 = 0.0

        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if frequency <= 0:
                continue

            df = document_frequency.get(term, 0)
            idf = math.log(
                1.0
                + (
                    document_count - df + 0.5
                )
                / (df + 0.5)
            )
            length_ratio = (
                document_length / average_length
                if average_length > 0
                else 1.0
            )
            denominator = frequency + k1 * (
                1.0 - b + b * length_ratio
            )
            bm25 += idf * (
                frequency * (k1 + 1.0)
            ) / denominator

        title_tokens = set(_tokens(title))
        path_tokens = set(_tokens(path))
        domain_tokens = set(_tokens(domain.replace(".", " ")))

        haystack = " ".join([title, snippet, path, domain])
        negative_matches = sum(
            1 for phrase in negative_phrases if phrase in haystack
        )

        signals.append(
            LocalRelevance(
                hit=hit,
                provider_index=index,
                bm25=bm25,
                title_matches=sum(
                    1 for term in query_terms if term in title_tokens
                ),
                path_matches=sum(
                    1 for term in query_terms if term in path_tokens
                ),
                domain_matches=sum(
                    1 for term in query_terms if term in domain_tokens
                ),
                negative_matches=negative_matches,
            )
        )

    return signals
