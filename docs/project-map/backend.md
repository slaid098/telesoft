---
module: src/telesoft
purpose: FastAPI backend — Telegram channel post editor
key_files:
  - src/telesoft/main.py — FastAPI app: lifespan (init_db/close_db + start/stop_client) + SessionMiddleware + GET /health + include_router(auth)
  - src/telesoft/config.py — Settings frozen dataclass with from_env()
  - src/telesoft/core/telegram.py — bot-mode Telethon singleton client (by-ID fetch only)
  - src/telesoft/core/url_parser.py — parse Telegram post URLs → (channel, message_id)
  - src/telesoft/db/connection.py — aiosqlite connection layer (init_db/get_db/close_db)
  - src/telesoft/db/base.py — базовые execute/executemany/insert/fetchone/fetchall
  - src/telesoft/db/models/channel.py — CRUD для channels
  - src/telesoft/db/models/job.py — CRUD для edit_jobs
  - src/telesoft/db/models/log.py — CRUD для edit_logs
  - src/telesoft/api/auth.py — auth helpers (verify_credentials/login/logout/current_user/require_auth)
  - src/telesoft/api/routers/auth.py — auth router (POST /api/auth/login, /logout, GET /me)
  - src/telesoft/api/routers/channels.py — channels router (GET/POST/GET-by-id/PATCH/DELETE under /api/channels, auth on whole router)
  - src/telesoft/schemas/auth.py — Pydantic models (LoginRequest, AuthResponse)
  - src/telesoft/schemas/channel.py — Pydantic models (ChannelCreate/ChannelUpdate/ChannelResponse/ChannelListResponse) + now_iso() helper
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
├── main.py       # FastAPI app: lifespan (init_db → start_client try/except → yield → stop_client try/except → close_db), SessionMiddleware (signed cookie), include_router(auth_router + channels_router), GET /health → {"status":"ok"}
├── config.py     # Settings frozen dataclass + from_env() classmethod + helpers (_get_int/_get_str/_get_list)
├── core/         # Telegram client + URL parser (bot-mode, by-ID fetch only)
│   ├── __init__.py    # Пустой — package marker
│   ├── telegram.py    # Bot-mode Telethon singleton: get_client/start_client/stop_client/get_message/get_messages/edit_message/resolve_entity/get_bot_info
│   └── url_parser.py  # parse_post_url/parse_post_urls/is_valid_post_url — public + private channels, ?comment= игнорируется
├── db/           # Async SQLite layer (raw aiosqlite, без ORM)
│   ├── __init__.py        # Пустой — package marker
│   ├── base.py            # type Row = dict[str, Any] (PEP 695); execute/executemany/insert/fetchone/fetchall
│   ├── connection.py      # @dataclass _State holder; init_db (WAL+foreign_keys=ON+_create_schema); get_db (async ctx mgr); close_db; get_db_path
│   └── models/
│       ├── __init__.py    # Реэкспорт CRUD функций (__all__ отсортирован по RUF022)
│       ├── channel.py     # channels: telegram_id UNIQUE, title, username, is_active; CRUD + update whitelist
│       ├── job.py         # edit_jobs: FK→channels CASCADE, status/total/edited/failed; CRUD + filters
│       └── log.py         # edit_logs: FK→edit_jobs CASCADE, message_id/old_text/success/error; CRUD + pagination
├── api/          # HTTP API layer (auth helpers + routers)
│   ├── __init__.py    # Пустой — package marker
│   ├── auth.py        # Auth helpers: verify_credentials (secrets.compare_digest), login/logout/current_user/require_auth (FastAPI Depends)
│   └── routers/
│       ├── __init__.py    # Пустой — package marker
│       ├── auth.py        # APIRouter(prefix="/api/auth"): POST /login, POST /logout (auth), GET /me (auth)
│       └── channels.py    # APIRouter(prefix="/api/channels", dependencies=[Depends(require_auth)]): GET "" (list, ?active_only), POST "" (201/409), GET "/{id}" (200/404), PATCH "/{id}" (200/404/422), DELETE "/{id}" (204/404, FK CASCADE)
└── schemas/      # Pydantic request/response models
    ├── __init__.py  # Пустой — package marker
    ├── auth.py      # LoginRequest(username, password), AuthResponse(status, user)
    └── channel.py   # ChannelCreate, ChannelUpdate (@model_validator "хотя бы одно поле"), ChannelResponse (classmethod from_row), ChannelListResponse, now_iso() helper
```

## Patterns

- **src layout** (`src/telesoft/` вместо `telesoft/`) — изолирует пакет от корня репо
- **Frozen dataclass** для конфига — иммутабельный `Settings`, `from_env()` читает переменные окружения
- **Lifespan** для инициализации/закрытия ресурсов — `init_db()` + `start_client()` (try/except) на startup, `stop_client()` (try/except) + `close_db()` на shutdown. Падение Telegram НЕ роняет app (логируется через loguru)
- **Health endpoint** `GET /health` — стандартный liveness probe (public, без auth)
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
- **SessionMiddleware** (Starlette, signed cookie через `itsdangerous`) — `app.add_middleware(SessionMiddleware, secret_key=Settings.from_env().secret_key)`. Cookie подписан HMAC-SHA256, данные в plaintext (base64) — НЕ хранить sensitive данные в session (только username). `request.session` — dict-like (`__getitem__`/`__setitem__`/`get`/`clear`). `SECRET_KEY` должен быть 32+ chars (itsdangerous требует ≥32 bytes для HMAC-SHA256)
- **`secrets.compare_digest`** для timing-safe сравнения username/password в `verify_credentials` — защита от timing attack (НЕ plaintext `==`). `Settings.from_env()` вызывается при каждом login (не cached)
- **`Depends(require_auth)` паттерн** — `require_auth` возвращает `str` (username) или бросает `HTTPException(401, "Not authenticated")`. Используется как `user: str = Depends(require_auth)` (если нужен username) или `_user: str = Depends(require_auth)` (если только auth, без использования — underscore prefix, ruff ARG001 не срабатывает)
- **`isinstance(user, str)` check в `current_user`** — защита от подмены типа в cookie (cookie подписан, но не зашифрован — тип может быть любым)
- **`async def` для всех auth helpers** — `verify_credentials`/`login`/`logout`/`current_user`/`require_auth` все async (консистентность + будущее расширение, напр. БД-lookup)
- **APIRouter с prefix/tags** — `APIRouter(prefix="/api/auth", tags=["auth"])`. Endpoints: `POST /login`, `POST /logout` (auth), `GET /me` (auth). `GET /health` остаётся public (вне router)
- **Pydantic schemas** в `schemas/` — `LoginRequest` (request body), `AuthResponse` (response для /login). `/logout` и `/me` возвращают `dict[str, str]` (без `response_model`)
- **Auth на весь роутер** через `APIRouter(..., dependencies=[Depends(require_auth)])` (channels router) — DRY, нельзя случайно забыть auth на новом эндпоинте. Если нужен public эндпоинт под тем же prefix — выносить в отдельный роутер без `dependencies`
- **CRUD router pattern** (channels): 5 эндпоинтов поверх DB-моделей (PR#12) через `async with get_db() as db:`. Status codes: 201 (create), 409 (duplicate telegram_id), 404 (not found), 422 (empty PATCH body via Pydantic validator), 204 (delete, FK CASCADE на edit_jobs/edit_logs)
- **Pydantic `@model_validator(mode="after")`** для "хотя бы одно поле" в `ChannelUpdate` — бросает `ValueError` если все поля `None` → FastAPI автоматически возвращает 422. `mode="after"` (не `"before"`) — корректно работает с `{}` body
- **`ChannelResponse.from_row` classmethod** — конвертирует dict-like `aiosqlite.Row` в Pydantic model с явными casts (`int()`/`str()`/`bool()`) для SQLite-типов. Идиоматичный Pydantic паттерн (не standalone function)
- **`now_iso()` helper** в `schemas/channel.py` — `datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` → `"2026-07-20T12:34:56Z"` (ISO 8601 UTC с trailing `Z`, формат из спеки). НЕ `isoformat()` с `+00:00`
- **`PATCH` not `PUT`** для partial update — `ChannelUpdate` с all-optional fields + `model_validator` для "хотя бы одно поле". Семантически корректнее для partial (RFC 5789)
- **`dict[str, str | int | None]` для PATCH fields** — mypy strict требует explicit type для `**fields` в `update_channel(db, channel_id=..., **fields)`. `dict[str, object]` → mypy `arg-type` error
- **`int(payload.is_active)` cast** в PATCH — SQLite хранит `is_active` как INTEGER (0/1), Pydantic `bool` → Python `True`/`False` → `int()` для совместимости с `str | int | None` типом `update_channel`

## Dependencies

- fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru
- dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, httpx (для TestClient)