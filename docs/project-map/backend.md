---
module: src/telesoft
purpose: FastAPI backend — Telegram channel post editor
key_files:
  - src/telesoft/main.py — FastAPI app: lifespan + GET /health
  - src/telesoft/config.py — Settings frozen dataclass with from_env()
  - src/telesoft/__init__.py — package marker (empty)
  - src/telesoft/py.typed — PEP 561 marker (empty)
dependencies: []
last_updated: 2026-07-20
---

# backend — src/telesoft/

## Structure

```
src/telesoft/
├── __init__.py   # Пустой — package marker
├── py.typed      # Пустой — PEP 561 marker (типы доступны внешним потребителям)
├── main.py       # FastAPI app: lifespan (init_db/close_db placeholder), GET /health → {"status":"ok"}
└── config.py     # Settings frozen dataclass + from_env() classmethod + helpers (_get_int/_get_str/_get_list)
```

## Patterns

- **src layout** (`src/telesoft/` вместо `telesoft/`) — изолирует пакет от корня репо
- **Frozen dataclass** для конфига — иммутабельный `Settings`, `from_env()` читает переменные окружения
- **Lifespan** для инициализации/закрытия ресурсов (пока placeholder для DB)
- **Health endpoint** `GET /health` — стандартный liveness probe
- **Env-префиксы**: `ADMIN_`, `SECRET_KEY`, `TELEGRAM_`

## Dependencies

- fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru
- dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, httpx (для TestClient)