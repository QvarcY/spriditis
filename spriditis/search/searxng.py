from __future__ import annotations

from urllib.parse import urlparse

import requests

from .base import SearchProvider, SearchProviderError
from .models import SearchHit


class SearXNGProvider(SearchProvider):
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 15,
        user_agent: str = "SpriditisResearchBot/3.3",
        session: requests.Session | None = None,
    ):
        base_url = base_url.strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SEARXNG_BASE_URL jābūt derīgam http/https URL.")

        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    @property
    def name(self) -> str:
        return "searxng"

    def search(self, query: str, *, language: str, limit: int, safesearch: int) -> list[SearchHit]:
        try:
            response = self.session.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "language": language or "all",
                    "safesearch": safesearch,
                },
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SearchProviderError(f"SearXNG HTTP kļūda: {exc}") from exc

        if response.status_code == 403:
            raise SearchProviderError(
                "SearXNG atgrieza 403. Pārbaudi, vai instancei ir atļauts JSON output format."
            )
        if response.status_code != 200:
            raise SearchProviderError(f"SearXNG atgrieza HTTP {response.status_code}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchProviderError("SearXNG neatgrieza derīgu JSON.") from exc

        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise SearchProviderError("SearXNG JSON laukam 'results' nav gaidītā formāta.")

        hits: list[SearchHit] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            engines = item.get("engines") or []
            if isinstance(engines, list):
                engine = ",".join(str(x) for x in engines[:4])
            else:
                engine = str(item.get("engine") or engines or "")

            provider_score = item.get("score")
            try:
                provider_score = float(provider_score) if provider_score is not None else None
            except (TypeError, ValueError):
                provider_score = None

            hits.append(
                SearchHit(
                    url=url,
                    title=str(item.get("title") or ""),
                    snippet=str(item.get("content") or ""),
                    engine=engine,
                    provider_score=provider_score,
                )
            )
            if len(hits) >= limit:
                break
        return hits
