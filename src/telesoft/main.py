"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from starlette.middleware.sessions import SessionMiddleware

from telesoft.api.routers.auth import router as auth_router
from telesoft.api.routers.channels import router as channels_router
from telesoft.api.routers.jobs import router as jobs_router
from telesoft.api.routers.ws import router as ws_router
from telesoft.config import Settings
from telesoft.core.events import EventBus
from telesoft.core.runner import JobRunner
from telesoft.core.telegram import start_client, stop_client
from telesoft.db.connection import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    settings = Settings.from_env()
    event_bus = EventBus()
    runner = JobRunner(max_concurrency=settings.jobs_max_concurrency, event_bus=event_bus)
    runner.start()
    app.state.event_bus = event_bus
    app.state.job_runner = runner
    if settings.telegram_bot_token:
        try:
            await start_client()
        except Exception as exc:
            logger.warning("Telegram client start failed, continuing without it: {}", exc)
    try:
        yield
    finally:
        try:
            await runner.stop()
        except Exception as exc:
            logger.warning("Job runner stop failed: {}", exc)
        try:
            await stop_client()
        except Exception as exc:
            logger.warning("Telegram client stop failed: {}", exc)
        await close_db()


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=Settings.from_env().secret_key)
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(jobs_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
