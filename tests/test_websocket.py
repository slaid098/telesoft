"""Tests for the WebSocket job-progress endpoint (``WS /api/ws``).

Covers: auth-gated connect (close 4001 when unauthenticated), end-to-end event
stream (job_started + progress + completed), and disconnect cleanup (subscriber
queue removed from the bus).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from telesoft.core.events import Event, EventBus
from telesoft.core.runner import JobRunner
from telesoft.main import app


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))
    monkeypatch.setenv("JOBS_MAX_CONCURRENCY", "2")


@pytest.fixture
def ws_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """An authenticated TestClient with a temp DB and a started JobRunner."""
    _set_env(monkeypatch, tmp_path)
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": "secret"})
        yield c


@pytest.fixture
def anon_ws_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """An unauthenticated TestClient sharing the same env setup."""
    _set_env(monkeypatch, tmp_path)
    with TestClient(app) as c:
        yield c


def _create_channel(client: TestClient) -> dict[str, object]:
    resp = client.post(
        "/api/channels",
        json={
            "telegram_id": -1001234567890,
            "title": "ws channel",
            "username": "ws_channel",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pump_loop(client: TestClient, rounds: int = 3) -> None:
    """Run a few cheap HTTP requests so pending WS coroutines progress."""
    for _ in range(rounds):
        client.get("/health")


# ── Auth gating ───────────────────────────────────────────────────────────


def test_ws_requires_auth(anon_ws_client: TestClient) -> None:
    """An unauthenticated WS connect is closed with code 4001."""
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        anon_ws_client.websocket_connect("/api/ws") as ws,
    ):
        ws.receive_text()
    assert exc_info.value.code == 4001


# ── End-to-end event stream ───────────────────────────────────────────────


def test_ws_receives_events(
    ws_client: TestClient,
    mock_telethon_get_message: AsyncMock,
    mock_telethon_edit_message: AsyncMock,
) -> None:
    """A successful replace-link job emits job_started, progress, completed."""
    received: list[dict[str, Any]] = []
    channel = _create_channel(ws_client)
    with ws_client.websocket_connect("/api/ws") as ws:
        ws_client.post(
            f"/api/channels/{channel['id']}/replace-link",
            json={
                "post_urls": ["https://t.me/ws_channel/1"],
                "pattern": r"https://old\.example\.com",
                "new_link": "https://new.example.com",
            },
        )
        seen_completed = False
        for _ in range(20):
            if seen_completed:
                break
            msg = ws.receive_json()
            received.append(msg)
            if msg["type"] == "completed":
                seen_completed = True
        assert seen_completed, f"missing completed in {received}"

    types = [m["type"] for m in received]
    assert "job_started" in types
    assert "completed" in types
    assert "progress" in types


def test_ws_disconnect_unsubscribes(ws_client: TestClient) -> None:
    """After the WS closes, the subscriber queue is removed from the bus."""
    bus: EventBus = app.state.event_bus  # type: ignore[assignment]
    initial_subscribers = len(bus._subscribers)
    with ws_client.websocket_connect("/api/ws") as ws:
        ws.send_text("ping")
        _pump_loop(ws_client)
        assert len(bus._subscribers) == initial_subscribers + 1
    _pump_loop(ws_client)
    assert len(bus._subscribers) == initial_subscribers


def test_ws_publish_event_directly(ws_client: TestClient) -> None:
    """Publishing an Event from the bus reaches the connected client."""
    with ws_client.websocket_connect("/api/ws") as ws:
        bus: EventBus = app.state.event_bus  # type: ignore[assignment]
        asyncio.run(bus.publish(Event(type="ping", data={"n": 1})))
        msg = ws.receive_json()
    assert msg["type"] == "ping"
    assert msg["data"] == {"n": 1}


# ── EventBus unit tests ───────────────────────────────────────────────────


async def test_event_bus_subscribe_publish_unsubscribe() -> None:
    """Direct unit test of the EventBus fan-out."""
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    assert len(bus._subscribers) == 2
    await bus.publish(Event(type="a", data={"n": 1}))
    e1 = await q1.get()
    e2 = await q2.get()
    assert e1.type == "a"
    assert e1.data == {"n": 1}
    assert e2.type == "a"
    bus.unsubscribe(q1)
    assert len(bus._subscribers) == 1
    await bus.publish(Event(type="b", data={"n": 2}))
    assert q1.empty()
    e2b = await q2.get()
    assert e2b.type == "b"
    bus.unsubscribe(q2)
    assert len(bus._subscribers) == 0


async def test_event_bus_unsubscribe_idempotent() -> None:
    """Unsubscribing an unknown queue is a no-op."""
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.unsubscribe(q)
    assert len(bus._subscribers) == 0


# ── JobRunner unit tests ──────────────────────────────────────────────────


async def test_runner_start_idempotent() -> None:
    """start() is idempotent; calling twice does not replace the semaphore."""
    runner = JobRunner(max_concurrency=3)
    runner.start()
    sem1 = runner._semaphore
    runner.start()
    sem2 = runner._semaphore
    assert sem1 is sem2
    await runner.stop()


async def test_runner_cancel_returns_false_for_unknown_job() -> None:
    """cancelling an unknown job returns False."""
    runner = JobRunner(max_concurrency=2)
    runner.start()
    assert runner.cancel(999) is False
    await runner.stop()
