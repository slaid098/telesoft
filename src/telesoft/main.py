"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from telesoft.config import Settings
from telesoft.core.telegram import start_client, stop_client
from telesoft.db.connection import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    settings = Settings.from_env()
    if settings.telegram_bot_token:
        try:
            await start_client()
        except Exception as exc:
            logger.warning("Telegram client start failed, continuing without it: {}", exc)
    try:
        yield
    finally:
        try:
            await stop_client()
        except Exception as exc:
            logger.warning("Telegram client stop failed: {}", exc)
        await close_db()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
