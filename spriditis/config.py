from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "ja", "jā"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class AppSettings:
    gemini_api_key: str
    gemini_model: str
    gemini_batch_size: int
    gemini_requests_per_minute: int
    gemini_max_retries: int
    gemini_retry_base_seconds: float

    db_path: Path
    report_dir: Path

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    report_to: str
    send_email: bool

    user_agent: str
    request_timeout_seconds: int


def load_settings() -> AppSettings:
    load_dotenv()

    return AppSettings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        gemini_batch_size=max(1, _int("GEMINI_BATCH_SIZE", 10)),
        gemini_requests_per_minute=max(
            1, _int("GEMINI_REQUESTS_PER_MINUTE", 5)
        ),
        gemini_max_retries=max(0, _int("GEMINI_MAX_RETRIES", 3)),
        gemini_retry_base_seconds=max(
            0.5, _float("GEMINI_RETRY_BASE_SECONDS", 5.0)
        ),
        db_path=Path(os.getenv("DB_PATH", "data/spriditis_v31.db")),
        report_dir=Path(os.getenv("REPORT_DIR", "reports")),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        smtp_port=_int("SMTP_PORT", 465),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_app_password=os.getenv("SMTP_APP_PASSWORD", "").strip(),
        report_to=os.getenv("REPORT_TO", "").strip(),
        send_email=_bool("SEND_EMAIL", False),
        user_agent=os.getenv(
            "USER_AGENT",
            "SpriditisResearchBot/3.1 (+market research)",
        ).strip(),
        request_timeout_seconds=_int("REQUEST_TIMEOUT_SECONDS", 15),
    )
