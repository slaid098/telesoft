"""WebSocket endpoint for real-time job progress updates.

A single ``WS /api/ws`` endpoint accepts authenticated clients (session cookie
checked via :func:`current_user`) and streams :class:`telesoft.core.events.Event`
objects from the process-wide :class:`EventBus` until the client disconnects.

Auth failure closes the socket with code 4001 (application-level unauthenticated).
The runner publishes events as job state transitions; this router only forwards
them to each connected client.

Disconnect detection: a separate sender task drains the bus queue and forwards
events to the client. The main coroutine awaits ``receive_text`` from the
client in a loop — when the client goes away, ``receive_text`` raises
:class:`WebSocketDisconnect` and the loop exits, after which the sender task is
cancelled and the subscriber queue is removed from the bus.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from telesoft.api.auth import ws_current_user
from telesoft.core.events import EventBus

router = APIRouter(tags=["ws"])

_UNAUTH_CLOSE_CODE = 4001


def _get_event_bus(websocket: WebSocket) -> EventBus:
    """Return the process-wide EventBus attached to app state."""
    bus: Any = getattr(websocket.app.state, "event_bus", None)
    return cast("EventBus", bus)


@router.websocket("/api/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """Stream job progress events to an authenticated client."""
    if ws_current_user(websocket) is None:
        await websocket.close(code=_UNAUTH_CLOSE_CODE)
        return

    await websocket.accept()
    bus = _get_event_bus(websocket)
    queue = bus.subscribe()
    logger.info("ws client connected")
    sender_task = asyncio.create_task(_forward_events(websocket, queue))
    try:
        await _drain_client(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        sender_task.cancel()
        await _silently_await(sender_task)
        bus.unsubscribe(queue)
        logger.info("ws client disconnected")


async def _forward_events(websocket: WebSocket, queue: Any) -> None:
    """Drain the bus queue and forward events to the client."""
    while True:
        event = await queue.get()
        await websocket.send_json({"type": event.type, "data": event.data})


async def _drain_client(websocket: WebSocket) -> None:
    """Consume incoming client messages until the client disconnects."""
    while True:
        await websocket.receive_text()


async def _silently_await(task: asyncio.Task[None]) -> None:
    """Await *task* swallowing CancelledError so cleanup doesn't propagate."""
    try:
        await task
    except (asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
        return
