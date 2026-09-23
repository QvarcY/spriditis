from __future__ import annotations

from spriditis.config import AppSettings
from spriditis.core.projects import ResearchProject

from .base import AIProvider
from .fallback import FallbackProvider
from .gemini import GeminiProvider


def build_ai_provider(
    settings: AppSettings,
    project: ResearchProject,
    *,
    force_no_ai: bool = False,
) -> AIProvider:
    if force_no_ai or not project.analysis.ai_enabled:
        return FallbackProvider()

    if project.analysis.ai_provider == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            batch_size=settings.gemini_batch_size,
            requests_per_minute=settings.gemini_requests_per_minute,
            max_retries=settings.gemini_max_retries,
            retry_base_seconds=settings.gemini_retry_base_seconds,
        )

    return FallbackProvider()
