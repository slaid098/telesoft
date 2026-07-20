"""Tests for Settings.from_env()."""

from telesoft.config import Settings


def test_settings_from_env_defaults(monkeypatch) -> None:
    for var in (
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
        "SECRET_KEY",
        "HOST",
        "PORT",
        "LOG_LEVEL",
        "DB_PATH",
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_BOT_TOKEN",
        "SESSION_PATH",
        "JOBS_MAX_CONCURRENCY",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings.from_env()
    assert settings.admin_username == "admin"
    assert settings.admin_password == "changeme"
    assert settings.secret_key == ""
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.db_path == "app_data/telesoft.db"
    assert settings.telegram_api_id == 0
    assert settings.telegram_api_hash == ""
    assert settings.telegram_bot_token == ""
    assert settings.session_path == "app_data/bot.session"
    assert settings.jobs_max_concurrency == 3


def test_settings_from_env_custom(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("ADMIN_PASSWORD", "p@ss")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DB_PATH", "/data/db.sqlite")
    monkeypatch.setenv("TELEGRAM_API_ID", "999")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok:abc")
    monkeypatch.setenv("SESSION_PATH", "/data/session")
    monkeypatch.setenv("JOBS_MAX_CONCURRENCY", "5")

    settings = Settings.from_env()
    assert settings.admin_username == "root"
    assert settings.admin_password == "p@ss"
    assert settings.secret_key == "secret"
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000
    assert settings.log_level == "DEBUG"
    assert settings.db_path == "/data/db.sqlite"
    assert settings.telegram_api_id == 999
    assert settings.telegram_api_hash == "hash123"
    assert settings.telegram_bot_token == "tok:abc"
    assert settings.session_path == "/data/session"
    assert settings.jobs_max_concurrency == 5


def test_settings_is_frozen() -> None:
    settings = Settings(
        admin_username="a",
        admin_password="b",
        secret_key="s",
        host="0.0.0.0",
        port=8000,
        log_level="INFO",
        db_path="db",
        telegram_api_id=0,
        telegram_api_hash="",
        telegram_bot_token="",
        session_path="sess",
        jobs_max_concurrency=3,
    )
    try:
        settings.host = "x"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        msg = "Settings should be frozen"
        raise AssertionError(msg)
