"""Background job runner for replace-link operations.

The :class:`JobRunner` owns an :class:`asyncio.Semaphore` to cap the number of
jobs running simultaneously and a registry mapping job ids to their
``asyncio.Task`` objects. Job state is persisted in the SQLite ``edit_jobs``
table; the runner updates status/progress counters and writes per-post logs to
``edit_logs`` as the work progresses.

The runner is bound to a single asyncio event loop (the one uvicorn runs the
app on). One instance is created at app startup (see ``main.py`` lifespan) and
shared across requests via ``app.state.job_runner``.

Job lifecycle:
- ``submit(job_id, chat_id, limit, pattern, new_link, max_id)`` schedules a task.
  The DB row must already exist with ``status='pending'``.
- The worker acquires the semaphore, marks the job ``running``, then fetches
  the last ``limit`` channel posts ending at ``max_id`` via
  :func:`telesoft.core.telegram.get_last_messages`, filters them by *pattern*
  via :func:`telesoft.core.link_replacer.find_posts_with_pattern`, updates
  ``total`` in the DB to the number of matching posts, and edits each one via
  :func:`replace_link_in_post`. Per-post results are persisted to
  ``edit_logs`` and progress counters on ``edit_jobs`` are updated. Progress
  events are published to the :class:`EventBus`.
- On completion the job is marked ``done``; on cancellation ``cancelled``;
  on unexpected error ``failed``.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from loguru import logger

from telesoft.core import telegram as telegram_module
from telesoft.core.events import Event, EventBus
from telesoft.core.link_replacer import find_posts_with_pattern, replace_link_in_post
from telesoft.db.connection import get_db
from telesoft.db.models import job as job_model
from telesoft.db.models import log as log_model
from telesoft.schemas.job import now_iso


class JobRunner:
    """Manages async replace-link job execution with a concurrency limit."""

    def __init__(
        self,
        *,
        max_concurrency: int = 3,
        event_bus: EventBus | None = None,
        edit_delay: float = 5.0,
        pre_edit_delay: float = 2.0,
    ) -> None:
        self._max_concurrency = max_concurrency
        self._semaphore: asyncio.Semaphore | None = None
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._event_bus = event_bus
        self._cancelled: set[int] = set()
        self._edit_delay = edit_delay
        self._pre_edit_delay = pre_edit_delay

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Create the concurrency semaphore. Idempotent if already started."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)

    async def stop(self) -> None:
        """Cancel every running task, await cleanup, and clear the registry."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        self._cancelled.clear()
        self._semaphore = None

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    def active_count(self) -> int:
        """Number of tasks currently tracked (pending or running)."""
        return len(self._tasks)

    def is_running(self, job_id: int) -> bool:
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    # ── Submission / control ─────────────────────────────────────────────

    def submit(  # noqa: PLR0913
        self,
        job_id: int,
        chat_id: int,
        limit: int,
        pattern: str,
        new_link: str,
        max_id: int = 0,
        link_preview: bool = False,
    ) -> None:
        """Schedule a background task for *job_id* (must already exist in the DB)."""
        if self._semaphore is None:
            self.start()
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            existing.cancel()
        self._cancelled.discard(job_id)
        assert self._semaphore is not None
        task = asyncio.create_task(
            self._run_job(job_id, chat_id, limit, pattern, new_link, max_id, link_preview)
        )
        self._tasks[job_id] = task
        logger.bind(job_id=job_id, max_concurrency=self._max_concurrency).info(
            "replace-link job submitted to runner"
        )

    def cancel(self, job_id: int) -> bool:
        """Request cancellation of a tracked job. Returns True if a task was cancelled."""
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        self._cancelled.add(job_id)
        task.cancel()
        return True

    # ── Execution ────────────────────────────────────────────────────────

    async def _run_job(  # noqa: PLR0913
        self,
        job_id: int,
        chat_id: int,
        limit: int,
        pattern: str,
        new_link: str,
        max_id: int = 0,
        link_preview: bool = False,
    ) -> None:
        """Wrap the replace-link work with semaphore + status transitions."""
        sem = self._semaphore
        assert sem is not None
        async with sem:
            try:
                await self._mark_running(job_id)
                messages = await telegram_module.get_last_messages(chat_id, limit, max_id)
                matching = await find_posts_with_pattern(messages, pattern)
                total = len(matching)
                logger.info(
                    "discovery: fetched={}, matched={}",
                    len(messages),
                    total,
                )
                await self._set_total(job_id, total)
                await self._publish(
                    Event(type="job_started", data={"job_id": job_id, "total": total})
                )
                if total > 0:
                    await asyncio.sleep(self._pre_edit_delay)
                edited = 0
                failed = 0
                for message in matching:
                    if job_id in self._cancelled:
                        raise asyncio.CancelledError  # noqa: TRY301
                    message_id = int(message.id)
                    result = await replace_link_in_post(
                        chat_id, message, pattern, new_link, link_preview=link_preview
                    )
                    if result.get("success"):
                        if result.get("edited"):
                            edited += 1
                    else:
                        failed += 1
                    await self._write_log(job_id, message_id, result)
                    await self._update_progress(job_id, edited, failed)
                    await self._publish(
                        Event(
                            type="progress",
                            data={
                                "job_id": job_id,
                                "edited": edited,
                                "failed": failed,
                                "total": total,
                                "message_id": message_id,
                            },
                        )
                    )
                    if result.get("edited"):
                        await asyncio.sleep(self._edit_delay)
            except asyncio.CancelledError:
                await self._mark_final(job_id, "cancelled")
                await self._publish(Event(type="cancelled", data={"job_id": job_id}))
                raise
            except Exception as exc:
                error = str(exc) or repr(exc)
                await self._mark_final(job_id, "failed")
                await self._publish(Event(type="failed", data={"job_id": job_id, "error": error}))
                logger.bind(job_id=job_id, error=str(exc)).warning("replace-link job failed")
                return
            else:
                await self._mark_final(job_id, "done")
                await self._publish(
                    Event(
                        type="completed",
                        data={
                            "job_id": job_id,
                            "edited": edited,
                            "failed": failed,
                            "total": total,
                        },
                    )
                )
            finally:
                self._tasks.pop(job_id, None)
                self._cancelled.discard(job_id)

    # ── DB / event helpers ───────────────────────────────────────────────

    async def _mark_running(self, job_id: int) -> None:
        async with get_db() as db:
            row = await job_model.get_job(db, job_id=job_id)
            if row is None:
                msg = f"job {job_id} not found"
                raise RuntimeError(msg)
            await job_model.update_job_status(db, job_id=job_id, status="running")

    async def _set_total(self, job_id: int, total: int) -> None:
        async with get_db() as db:
            await job_model.update_job_status(db, job_id=job_id, status="running", total=total)

    async def _update_progress(self, job_id: int, edited: int, failed: int) -> None:
        async with get_db() as db:
            await job_model.update_job_status(
                db, job_id=job_id, status="running", edited=edited, failed=failed
            )

    async def _write_log(self, job_id: int, message_id: int, result: dict[str, Any]) -> None:
        async with get_db() as db:
            await log_model.create_log(
                db,
                job_id=job_id,
                message_id=message_id,
                old_text=result.get("old_text"),
                success=bool(result.get("success")),
                error=result.get("error"),
                edited_at=now_iso(),
            )

    async def _mark_final(self, job_id: int, status: str) -> None:
        async with get_db() as db:
            await job_model.update_job_status(
                db, job_id=job_id, status=status, completed_at=now_iso()
            )

    async def _publish(self, event: Event) -> None:
        if self._event_bus is not None:
            await self._event_bus.publish(event)
