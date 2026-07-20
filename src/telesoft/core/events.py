"""In-process pub/sub event bus for real-time job progress updates.

A single :class:`EventBus` instance is attached to ``app.state.event_bus`` at
lifespan startup (see ``main.py``). The :class:`telesoft.core.runner.JobRunner`
publishes :class:`Event` objects as jobs progress; the WebSocket router
subscribes a per-client :class:`asyncio.Queue` and forwards events to the
connected client.

The bus is intentionally minimal — no persistence, no backpressure beyond the
per-subscriber queue size, no filtering. Subscribers receive every event and
decide what to forward. This keeps the runner oblivious to the number of
connected clients.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class Event:
    """A single event published to the bus.

    Attributes:
        type: Event discriminator (e.g. ``job_started``, ``progress``,
            ``completed``, ``failed``).
        data: Arbitrary JSON-serialisable payload.
    """

    type: str
    data: dict[str, object]


class EventBus:
    """Fan-out event bus backed by one :class:`asyncio.Queue` per subscriber.

    The bus is bound to a single event loop (the one uvicorn runs the app on).
    Subscribe from within the loop's coroutines only.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def subscribe(self) -> asyncio.Queue[Event]:
        """Register a new subscriber and return its dedicated queue."""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Remove a subscriber queue. Safe to call multiple times."""
        self._subscribers.discard(queue)

    async def publish(self, event: Event) -> None:
        """Fan *event* out to every active subscriber's queue."""
        for queue in self._subscribers:
            queue.put_nowait(event)
