"""Tests for the Patterns API (``/api/patterns`` CRUD) and the preview-replace
endpoint (``/api/channels/{id}/preview-replace``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from telesoft.db import connection
from telesoft.db.models import pattern as pattern_model
from telesoft.main import app
from tests.conftest import MockMessage


@pytest.fixture
async def db_handle(authed_client: TestClient) -> AsyncIterator[aiosqlite.Connection]:
    """Expose the shared DB connection used by the running app for direct queries."""
    db = connection._state.db
    assert db is not None
    yield db


def _create_channel(
    client: TestClient,
    *,
    telegram_id: int = -1001234567890,
    title: str = "Test channel",
    username: str | None = "test_channel",
) -> dict[str, Any]:
    response = client.post(
        "/api/channels",
        json={"telegram_id": telegram_id, "title": title, "username": username},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_patterns_list_empty(authed_client: TestClient) -> None:
    """Fresh DB has no patterns → empty list, total=0."""
    response = authed_client.get("/api/patterns")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["patterns"] == []


def test_patterns_create_and_list(
    authed_client: TestClient,
    db_handle: Any,
) -> None:
    """Created custom pattern appears in the list."""
    payload = {
        "name": "Basic bot link",
        "pattern": r"https://t\.me/bot\?start=\d+",
        "description": "Generic bot start link",
    }
    response = authed_client.post("/api/patterns", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Basic bot link"
    assert body["pattern"] == r"https://t\.me/bot\?start=\d+"
    assert body["is_builtin"] is False

    listing = authed_client.get("/api/patterns").json()
    assert listing["total"] == 1
    assert listing["patterns"][0]["name"] == "Basic bot link"


def test_patterns_create_invalid_regex_422(authed_client: TestClient) -> None:
    """Invalid regex → 422."""
    response = authed_client.post(
        "/api/patterns",
        json={"name": "Bad", "pattern": "[invalid", "description": None},
    )
    assert response.status_code == 422


def test_patterns_create_is_builtin_always_false(authed_client: TestClient) -> None:
    """Even if a client tries to set is_builtin=True, server forces is_builtin=0."""
    response = authed_client.post(
        "/api/patterns",
        json={
            "name": "Hacker",
            "pattern": r"https://x",
            "description": None,
            "is_builtin": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["is_builtin"] is False


def test_patterns_delete_custom(
    authed_client: TestClient,
    db_handle: Any,
) -> None:
    """Custom pattern can be deleted (204)."""
    response = authed_client.post(
        "/api/patterns",
        json={"name": "Temp", "pattern": r"https://x", "description": None},
    )
    pattern_id = int(response.json()["id"])
    delete = authed_client.delete(f"/api/patterns/{pattern_id}")
    assert delete.status_code == 204
    listing = authed_client.get("/api/patterns").json()
    assert listing["total"] == 0


async def test_patterns_delete_builtin_403(
    authed_client: TestClient,
    db_handle: Any,
) -> None:
    """Built-in pattern cannot be deleted → 403."""
    row = await pattern_model.create_pattern(
        db_handle,
        name="Built-in",
        pattern=r"https://x",
        description=None,
        is_builtin=1,
        created_at="2026-07-21T00:00:00Z",
    )
    pattern_id = int(row["id"])
    response = authed_client.delete(f"/api/patterns/{pattern_id}")
    assert response.status_code == 403


def test_patterns_delete_not_found_404(authed_client: TestClient) -> None:
    """Deleting a non-existent pattern → 404."""
    response = authed_client.delete("/api/patterns/9999")
    assert response.status_code == 404


def test_patterns_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """All /api/patterns endpoints require an authenticated session."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        assert unauthed.get("/api/patterns").status_code == 401
        assert unauthed.post("/api/patterns", json={"name": "x", "pattern": "x"}).status_code == 401
        assert unauthed.delete("/api/patterns/1").status_code == 401


def test_preview_replace_returns_previews(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """preview-replace returns up to 3 before→after pairs + compiled_pattern."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = [
        MockMessage(id=1, text="see https://old.example.com/a", chat_id=-1001234567890),
        MockMessage(id=2, text="see https://old.example.com/b", chat_id=-1001234567890),
        MockMessage(id=3, text="see https://old.example.com/c", chat_id=-1001234567890),
        MockMessage(id=4, text="no link here", chat_id=-1001234567890),
    ]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/preview-replace",
        json={
            "pattern": r"https://old\.example\.com",
            "new_link": "https://new.example.com",
            "mode": "advanced",
            "keep_tail": False,
            "limit": 100,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_matches"] == 3
    assert len(body["previews"]) == 3
    assert body["compiled_pattern"] == r"https://old\.example\.com"
    for entry in body["previews"]:
        assert entry["match_source"] == "text"
        assert "https://old.example.com" in entry["before"]
        assert "https://new.example.com" in entry["after"]


def test_preview_replace_simple_mode_compiles_wildcard(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """mode=simple compiles `*` to `.*` — compiled_pattern reflects that."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = [
        MockMessage(id=1, text="https://t.me/bot?start=flow-abc", chat_id=-1001234567890),
    ]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/preview-replace",
        json={
            "pattern": "https://t.me/bot?start=flow-*",
            "new_link": "https://new.example.com",
            "mode": "simple",
            "keep_tail": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_matches"] == 1
    assert r".*" in body["compiled_pattern"]


def test_preview_replace_keep_tail_strips_tail(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """keep_tail=True strips the trailing -s-* segment from compiled_pattern."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = []
    response = authed_client.post(
        f"/api/channels/{channel['id']}/preview-replace",
        json={
            "pattern": r"https://t\.me/bot\?start=flow-\d+(-s-\d+)?",
            "new_link": "https://new.example.com",
            "mode": "advanced",
            "keep_tail": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["compiled_pattern"] == r"https://t\.me/bot\?start=flow-\d+"


def test_preview_replace_invalid_channel_404(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """Preview for a non-existent channel → 404."""
    response = authed_client.post(
        "/api/channels/9999/preview-replace",
        json={"pattern": r"https://x", "new_link": "https://new.example.com"},
    )
    assert response.status_code == 404
    mock_telethon_get_last_messages.assert_not_awaited()


def test_preview_replace_invalid_pattern_422(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """Invalid regex → 422 (no Telegram fetch)."""
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/preview-replace",
        json={"pattern": "[invalid", "new_link": "https://new.example.com"},
    )
    assert response.status_code == 422
    mock_telethon_get_last_messages.assert_not_awaited()


def test_preview_replace_unknown_mode_422(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """Unknown mode → 422 (compile_pattern raises ValueError)."""
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/preview-replace",
        json={"pattern": "x", "new_link": "https://new.example.com", "mode": "regex"},
    )
    assert response.status_code == 422
    mock_telethon_get_last_messages.assert_not_awaited()


def test_preview_replace_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """preview-replace requires an authenticated session."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    with TestClient(app) as unauthed:
        response = unauthed.post(
            "/api/channels/1/preview-replace",
            json={"pattern": "x", "new_link": "https://new.example.com"},
        )
        assert response.status_code == 401


def test_replace_link_simple_mode_compiles_pattern(
    authed_client: TestClient,
    mock_runner: Any,
    mock_telethon_get_last_messages: Any,
) -> None:
    """replace-link with mode=simple saves the compiled regex to the DB."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = [
        MockMessage(id=1, text="https://t.me/bot?start=flow-abc", chat_id=-1001234567890),
    ]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": "https://t.me/bot?start=flow-*",
            "new_link": "https://new.example.com",
            "mode": "simple",
            "keep_tail": False,
            "limit": 100,
        },
    )
    assert response.status_code == 201, response.text
    # Verify the stored job has the compiled regex pattern
    jobs = authed_client.get("/api/jobs").json()
    assert jobs["total"] == 1
    stored = jobs["jobs"][0]["pattern"]
    assert r".*" in stored
    assert "https://t.me/bot" not in stored  # original wildcard form must be gone


def test_replace_link_unknown_mode_422(
    authed_client: TestClient,
    mock_telethon_get_last_messages: Any,
) -> None:
    """replace-link with unknown mode → 422 (no Telegram fetch)."""
    channel = _create_channel(authed_client)
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": "x",
            "new_link": "https://new.example.com",
            "mode": "regex",
        },
    )
    assert response.status_code == 422
    mock_telethon_get_last_messages.assert_not_awaited()


def test_replace_link_backward_compat_default_mode(
    authed_client: TestClient,
    mock_runner: Any,
    mock_telethon_get_last_messages: Any,
) -> None:
    """replace-link without mode/keep_tail still works (defaults advanced)."""
    channel = _create_channel(authed_client)
    mock_telethon_get_last_messages.return_value = [
        MockMessage(id=1, text="https://old.example.com", chat_id=-1001234567890),
    ]
    response = authed_client.post(
        f"/api/channels/{channel['id']}/replace-link",
        json={
            "pattern": r"https://old\.example\.com",
            "new_link": "https://new.example.com",
            "limit": 100,
        },
    )
    assert response.status_code == 201, response.text
    jobs = authed_client.get("/api/jobs").json()
    assert jobs["total"] == 1
    assert jobs["jobs"][0]["pattern"] == r"https://old\.example\.com"
