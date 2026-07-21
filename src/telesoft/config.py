"""Application settings loaded from environment variables.

A frozen dataclass serving as the single source of truth for configuration.
Access via dependency injection: construct with ``Settings.from_env()`` at
startup and pass to services that need it.
"""

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable application settings populated from environment variables."""

    admin_username: str
    admin_password: str
    secret_key: str
    host: str
    port: int
    log_level: str
    db_path: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_bot_token: str
    session_path: str
    telegram_session_string: str
    jobs_max_concurrency: int
    telegram_request_delay: float
    telegram_edit_delay: float

    @classmethod
    def from_env(cls) -> "Settings":
        """Build Settings from current environment variables."""
        return cls(
            admin_username=_get_str("ADMIN_USERNAME", "admin"),
            admin_password=_get_str("ADMIN_PASSWORD", "changeme"),
            secret_key=_get_str("SECRET_KEY", ""),
            host=_get_str("HOST", "0.0.0.0"),  # noqa: S104
            port=_get_int("PORT", 8000),
            log_level=_get_str("LOG_LEVEL", "INFO"),
            db_path=_get_str("DB_PATH", "app_data/telesoft.db"),
            telegram_api_id=_get_int("TELEGRAM_API_ID", 0),
            telegram_api_hash=_get_str("TELEGRAM_API_HASH", ""),
            telegram_bot_token=_get_str("TELEGRAM_BOT_TOKEN", ""),
            session_path=_get_str("SESSION_PATH", "app_data/bot.session"),
            telegram_session_string=_get_str("TELEGRAM_SESSION_STRING", ""),
            jobs_max_concurrency=_get_int("JOBS_MAX_CONCURRENCY", 3),
            telegram_request_delay=_get_float("TELEGRAM_REQUEST_DELAY", 1.0),
            telegram_edit_delay=_get_float("TELEGRAM_EDIT_DELAY", 5.0),
        )
