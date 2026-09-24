from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


LEGACY_DEFAULT_DB_PATHS = {
    "data/spriditis_v31.db",
    r"data\spriditis_v31.db",
}


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


def _database_paths() -> tuple[Path, Path | None]:
    """
    Sprīdītis 3.2 moves to a version-neutral database name.

    A copied 3.1/3.2-alpha1 .env can still contain:
        DB_PATH=data/spriditis_v31.db

    That legacy default is treated as a migration source while the active
    target becomes data/spriditis.db. Custom DB_PATH values remain untouched.
    """
    raw = os.getenv("DB_PATH", "").strip()

    if not raw:
        return Path("data/spriditis.db"), Path("data/spriditis_v31.db")

    normalized = raw.replace("\\", "/")

    if normalized == "data/spriditis_v31.db":
        return Path("data/spriditis.db"), Path(raw)

    return Path(raw), None


@dataclass(frozen=True)
class AppSettings:
    gemini_api_key: str
    gemini_model: str
    gemini_batch_size: int
    gemini_requests_per_minute: int
    gemini_max_retries: int
    gemini_retry_base_seconds: float

    db_path: Path
    legacy_db_path: Path | None
    report_dir: Path

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    report_to: str
    send_email: bool

    user_agent: str
    request_timeout_seconds: int

    searxng_base_url: str = ""
    searxng_timeout_seconds: int = 15


def load_settings() -> AppSettings:
    load_dotenv()
    db_path, legacy_db_path = _database_paths()

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
        db_path=db_path,
        legacy_db_path=legacy_db_path,
        report_dir=Path(os.getenv("REPORT_DIR", "reports")),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        smtp_port=_int("SMTP_PORT", 465),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_app_password=os.getenv("SMTP_APP_PASSWORD", "").strip(),
        report_to=os.getenv("REPORT_TO", "").strip(),
        send_email=_bool("SEND_EMAIL", False),
        user_agent=os.getenv(
            "USER_AGENT",
            "SpriditisResearchBot/3.3 (+market research)",
        ).strip(),
        request_timeout_seconds=_int("REQUEST_TIMEOUT_SECONDS", 15),
        searxng_base_url=os.getenv("SEARXNG_BASE_URL", "").strip(),
        searxng_timeout_seconds=max(1, _int("SEARXNG_TIMEOUT_SECONDS", 15)),
    )
