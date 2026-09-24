from __future__ import annotations

from spriditis.config import AppSettings
from spriditis.core.projects import ResearchProject

from .base import SearchProvider
from .searxng import SearXNGProvider


def build_search_provider(settings: AppSettings, project: ResearchProject) -> SearchProvider | None:
    if project.crawl.mode != "expedition":
        return None

    provider = project.search.provider
    if provider == "none":
        return None

    if provider == "searxng":
        if not settings.searxng_base_url:
            raise ValueError(
                "Expedition režīmam ar SearXNG jānorāda SEARXNG_BASE_URL .env failā."
            )
        return SearXNGProvider(
            settings.searxng_base_url,
            timeout_seconds=settings.searxng_timeout_seconds,
            max_retries=settings.searxng_max_retries,
            retry_base_seconds=settings.searxng_retry_base_seconds,
            user_agent=settings.user_agent,
        )

    raise ValueError(f"Neatbalstīts SearchProvider: {provider}")
