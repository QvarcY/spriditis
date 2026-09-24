from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import urlparse

import requests

from .base import SearchProvider, SearchProviderError
from .models import SearchHit


_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class SearXNGProvider(SearchProvider):
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 15,
        max_retries: int = 2,
        retry_base_seconds: float = 1.5,
        user_agent: str = "SpriditisResearchBot/3.3",
        session: requests.Session | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        base_url = base_url.strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SEARXNG_BASE_URL jābūt derīgam http/https URL.")

        self.base_url = base_url
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_retries = max(0, int(max_retries))
        self.retry_base_seconds = max(0.0, float(retry_base_seconds))
        self.session = session or requests.Session()
        self.sleep_func = sleep_func
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )

    @property
    def name(self) -> str:
        return "searxng"

    def search(
        self,
        query: str,
        *,
        language: str,
        limit: int,
        safesearch: int,
    ) -> list[SearchHit]:
        attempts_total = self.max_retries + 1
        response = None

        for attempt_index in range(attempts_total):
            attempt_no = attempt_index + 1
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
                if attempt_no < attempts_total:
                    self._sleep_before_retry(None, attempt_index)
                    continue
                raise SearchProviderError(
                    f"SearXNG HTTP kļūda pēc {attempt_no} mēģinājumiem: {exc}",
                    kind="network_error",
                    retryable=True,
                    attempts=attempt_no,
                ) from exc

            if response.status_code == 200:
                break

            if response.status_code == 403:
                raise SearchProviderError(
                    "SearXNG atgrieza 403. Pārbaudi, vai instancei ir atļauts JSON output format.",
                    kind="json_output_forbidden",
                    status_code=403,
                    retryable=False,
                    attempts=attempt_no,
                )

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt_no < attempts_total:
                    self._sleep_before_retry(response, attempt_index)
                    continue
                raise SearchProviderError(
                    f"SearXNG atgrieza HTTP {response.status_code} pēc {attempt_no} mēģinājumiem.",
                    kind="transient_http_error",
                    status_code=response.status_code,
                    retryable=True,
                    attempts=attempt_no,
                )

            raise SearchProviderError(
                f"SearXNG atgrieza HTTP {response.status_code}.",
                kind="http_error",
                status_code=response.status_code,
                retryable=False,
                attempts=attempt_no,
            )

        if response is None:
            raise SearchProviderError(
                "SearXNG neatgrieza atbildi.",
                kind="no_response",
                retryable=True,
                attempts=attempts_total,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            content_type = str(response.headers.get("Content-Type", ""))
            hint = (
                " Iespējams, instance neatļauj JSON output vai priekšā ir anti-bot lapa."
                if "json" not in content_type.lower()
                else ""
            )
            raise SearchProviderError(
                f"SearXNG neatgrieza derīgu JSON.{hint}",
                kind="invalid_json",
                status_code=200,
                retryable=False,
            ) from exc

        if not isinstance(payload, dict):
            raise SearchProviderError(
                "SearXNG JSON saknei nav gaidītā objekta formāta.",
                kind="invalid_payload",
                status_code=200,
                retryable=False,
            )

        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                "SearXNG JSON laukam 'results' nav gaidītā saraksta formāta.",
                kind="invalid_payload",
                status_code=200,
                retryable=False,
            )

        hits: list[SearchHit] = []
        seen_urls: set[str] = set()

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            url = str(item.get("url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue

            # Provider-level exact duplicate protection. The crawler performs
            # a second normalized-URL dedupe across all Expedition queries.
            if url in seen_urls:
                continue
            seen_urls.add(url)

            engines = item.get("engines") or []
            if isinstance(engines, list):
                engine = ",".join(str(x) for x in engines[:4])
            else:
                engine = str(item.get("engine") or engines or "")

            provider_score = item.get("score")
            try:
                provider_score = (
                    float(provider_score)
                    if provider_score is not None
                    else None
                )
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

    def _sleep_before_retry(self, response, attempt_index: int):
        delay = self._retry_delay(response, attempt_index)
        if delay > 0:
            self.sleep_func(delay)

    def _retry_delay(self, response, attempt_index: int) -> float:
        if response is not None:
            raw = str(response.headers.get("Retry-After", "")).strip()
            if raw:
                try:
                    return max(0.0, min(float(raw), 120.0))
                except ValueError:
                    try:
                        retry_at = parsedate_to_datetime(raw)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
                        return max(0.0, min(seconds, 120.0))
                    except (TypeError, ValueError, OverflowError):
                        pass

        delay = self.retry_base_seconds * (2 ** attempt_index)
        return max(0.0, min(delay, 120.0))
