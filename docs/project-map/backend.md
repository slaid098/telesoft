---
module: src/telesoft
purpose: FastAPI backend — Telegram channel post editor
key_files:
  - src/telesoft/main.py — FastAPI app: lifespan (init_db/close_db) + GET /health
  - src/telesoft/config.py — Settings frozen dataclass with from_env()
  - src/telesoft/db/connection.py — aiosqlite connection layer (init_db/get_db/close_db)
  - src/telesoft/db/base.py — базовые execute/executemany/insert/fetchone/fetchall
  - src/telesoft/db/models/channel.py — CRUD для channels
  - src/telesoft/db/models/job.py — CRUD для edit_jobs
  - src/telesoft/db/models/log.py — CRUD для edit_logs
  - src/telesoft/__init__.py — package marker (empty)
  - src/telesoft/py.typed — PEP 561 marker (empty)
dependencies: []
last_updated: 2026-07-20
---

# backend — src/telesoft/

> **Note:** `scripts/` (standalone spike/PoC скрипты) — отдельный модуль, НЕ часть `src/telesoft/`. См. [scripts.md](scripts.md).

## Structure

```
src/telesoft/
├── __init__.py   # Пустой — package marker
├── py.typed      # Пустой — PEP 561 marker (типы доступны внешним потребителям)
├── main.py       # FastAPI app: lifespan (init_db/close_db из db.connection), GET /health → {"status":"ok"}
├── config.py     # Settings frozen dataclass + from_env() classmethod + helpers (_get_int/_get_str/_get_list)
└── db/           # Async SQLite layer (raw aiosqlite, без ORM)
    ├── __init__.py        # Пустой — package marker
    ├── base.py            # type Row = dict[str, Any] (PEP 695); execute/executemany/insert/fetchone/fetchall
    ├── connection.py      # @dataclass _State holder; init_db (WAL+foreign_keys=ON+_create_schema); get_db (async ctx mgr); close_db; get_db_path
    └── models/
        ├── __init__.py    # Реэкспорт CRUD функций (__all__ отсортирован по RUF022)
        ├── channel.py     # channels: telegram_id UNIQUE, title, username, is_active; CRUD + update whitelist
        ├── job.py         # edit_jobs: FK→channels CASCADE, status/total/edited/failed; CRUD + filters
        └── log.py         # edit_logs: FK→edit_jobs CASCADE, message_id/old_text/success/error; CRUD + pagination
```

## Patterns

- **src layout** (`src/telesoft/` вместо `telesoft/`) — изолирует пакет от корня репо
- **Frozen dataclass** для конфига — иммутабельный `Settings`, `from_env()` читает переменные окружения
- **Lifespan** для инициализации/закрытия ресурсов — `init_db()` на startup, `close_db()` на shutdown (try/finally)
- **Health endpoint** `GET /health` — стандартный liveness probe
- **Env-префиксы**: `ADMIN_`, `SECRET_KEY`, `TELEGRAM_`
- **Raw aiosqlite без ORM** (паттерн media-gen) — `CREATE TABLE IF NOT EXISTS` на startup, без миграций
- **`type Row = dict[str, Any]` (PEP 695)** — ruff UP040 запрещает `TypeAlias`
- **`@dataclass _State` holder** вместо `global` (ruff PLW0603) — singleton `_state.db`
- **`_CREATE_SQL` + `_CREATE_INDEXES_SQL`** константы на модуль — `init_db()` итерирует в порядке FK-зависимостей (channels → edit_jobs → edit_logs)
- **FK CASCADE** с `PRAGMA foreign_keys=ON` (default OFF в SQLite) — канал → job'ы → логи
- **WAL mode** для конкурентного чтения при write-операциях
- **`update_channel` whitelist** (`title`/`username`/`is_active`) — `ValueError` на неизвестном поле
- **CRUD функции принимают `aiosqlite.Connection` первым аргументом** — no global state в моделях

## Dependencies

- fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru
- dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, httpx (для TestClient)