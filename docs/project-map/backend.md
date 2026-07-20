---
module: src/telesoft
purpose: FastAPI backend — Telegram channel post editor
key_files:
  - src/telesoft/main.py — FastAPI app: lifespan (init_db/close_db + start/stop_client) + GET /health
  - src/telesoft/config.py — Settings frozen dataclass with from_env()
  - src/telesoft/core/telegram.py — bot-mode Telethon singleton client (by-ID fetch only)
  - src/telesoft/core/url_parser.py — parse Telegram post URLs → (channel, message_id)
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
├── main.py       # FastAPI app: lifespan (init_db → start_client try/except → yield → stop_client try/except → close_db), GET /health → {"status":"ok"}
├── config.py     # Settings frozen dataclass + from_env() classmethod + helpers (_get_int/_get_str/_get_list)
├── core/         # Telegram client + URL parser (bot-mode, by-ID fetch only)
│   ├── __init__.py    # Пустой — package marker
│   ├── telegram.py    # Bot-mode Telethon singleton: get_client/start_client/stop_client/get_message/get_messages/edit_message/resolve_entity/get_bot_info
│   └── url_parser.py  # parse_post_url/parse_post_urls/is_valid_post_url — public + private channels, ?comment= игнорируется
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
- **Lifespan** для инициализации/закрытия ресурсов — `init_db()` + `start_client()` (try/except) на startup, `stop_client()` (try/except) + `close_db()` на shutdown. Падение Telegram НЕ роняет app (логируется через loguru)
- **Health endpoint** `GET /health` — стандартный liveness probe
- **Env-префиксы**: `ADMIN_`, `SECRET_KEY`, `TELEGRAM_`
- **Raw aiosqlite без ORM** (паттерн media-gen) — `CREATE TABLE IF NOT EXISTS` на startup, без миграций
- **`type Row = dict[str, Any]` (PEP 695)** — ruff UP040 запрещает `TypeAlias`
- **`@dataclass _State` holder** вместо `global` (ruff PLW0603) — singleton state в `db.connection._state.db` и `core.telegram._state.client/started`
- **`_CREATE_SQL` + `_CREATE_INDEXES_SQL`** константы на модуль — `init_db()` итерирует в порядке FK-зависимостей (channels → edit_jobs → edit_logs)
- **FK CASCADE** с `PRAGMA foreign_keys=ON` (default OFF в SQLite) — канал → job'ы → логи
- **WAL mode** для конкурентного чтения при write-операциях
- **`update_channel` whitelist** (`title`/`username`/`is_active`) — `ValueError` на неизвестном поле
- **CRUD функции принимают `aiosqlite.Connection` первым аргументом** — no global state в моделях
- **Bot-mode Telethon singleton** (`core/telegram.py`) — `TelegramClient(session_path, api_id, api_hash, receive_updates=False)` + `client.start(bot_token=...)`. Token в `start()`, НЕ в конструктор. File session (`settings.session_path`) для переиспользования между запусками (НЕ `MemorySession`)
- **By-ID fetch only** — `get_messages(chat_id, ids=[...])`. **КРИТИЧНО: НЕ `iter_messages`/`get_messages(limit=...)`** — `BotMethodInvalidError` для ботов (history iteration запрещён MTProto)
- **`asyncio.Lock` + double-checked locking** в `start_client()` — защита от concurrent start (fast path до lock, slow path повторная проверка внутри `async with _connection_lock`)
- **`edit_message` propagates `RPCError`** — не глотает ошибки, caller решает retry/log/abort
- **URL parser regex** `^https?://t\.me/(c/)?(\w+)/(\d+)` — public (`mychannel/123` → `("mychannel", 123)`), private (`c/1234567890/456` → `(-1001234567890, 456)` через `int(f"-100{channel_part}")`), `?comment=` игнорируется
- **mypy override для telethon** — `[[tool.mypy.overrides]] module = ["telethon.*"] ignore_missing_imports = true` (telethon не имеет `py.typed`, scoped override, не глобальный)

## Dependencies

- fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru
- dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, httpx (для TestClient)