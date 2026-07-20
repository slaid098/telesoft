---
module: src/telesoft
purpose: FastAPI backend — Telegram channel post editor
key_files:
  - src/telesoft/main.py — FastAPI app: lifespan (init_db/close_db + start/stop_client + EventBus/JobRunner start/stop) + SessionMiddleware + GET /health + include_router(auth/channels/jobs/ws)
  - src/telesoft/config.py — Settings frozen dataclass with from_env() (incl. jobs_max_concurrency, max_probe_id, telegram_request_delay)
  - src/telesoft/core/telegram.py — bot-mode Telethon singleton client (by-ID fetch + get_last_messages auto-discovery via channels.GetMessagesRequest raw API)
  - src/telesoft/core/url_parser.py — parse Telegram post URLs → (channel, message_id)
  - src/telesoft/core/link_replacer.py — regex link replacement + by-ID fetch + edit_message + find_posts_with_pattern + replace_link_in_posts orchestrator (PR#34)
  - src/telesoft/core/events.py — EventBus pub/sub (asyncio.Queue per subscriber)
  - src/telesoft/core/runner.py — JobRunner (asyncio.Semaphore, cooperative cancel, auto-discovery via get_last_messages PR#34)
  - src/telesoft/db/connection.py — aiosqlite connection layer (init_db/get_db/close_db)
  - src/telesoft/db/base.py — базовые execute/executemany/insert/fetchone/fetchall
  - src/telesoft/db/models/channel.py — CRUD для channels
  - src/telesoft/db/models/job.py — CRUD для edit_jobs
  - src/telesoft/db/models/log.py — CRUD для edit_logs
  - src/telesoft/api/auth.py — auth helpers (verify_credentials/login/logout/current_user/require_auth/ws_current_user)
  - src/telesoft/api/routers/auth.py — auth router (POST /api/auth/login, /logout, GET /me)
  - src/telesoft/api/routers/channels.py — channels router (GET/POST/GET-by-id/PATCH/DELETE under /api/channels, auth on whole router)
  - src/telesoft/api/routers/jobs.py — jobs router (POST replace-link с auto-discovery через limit, GET /api/jobs, GET /api/jobs/{id}, GET /api/jobs/{id}/logs, POST /api/jobs/{id}/cancel, auth on whole router, no prefix)
  - src/telesoft/api/routers/ws.py — WebSocket router (WS /api/ws, ws_current_user auth via scope["session"], sender+receive loops)
  - src/telesoft/schemas/auth.py — Pydantic models (LoginRequest, AuthResponse)
  - src/telesoft/schemas/channel.py — Pydantic models (ChannelCreate/ChannelUpdate/ChannelResponse/ChannelListResponse) + now_iso() helper
  - src/telesoft/schemas/job.py — Pydantic models (ReplaceLinkRequest с pattern/new_link/limit PR#34, JobResponse/JobListResponse/LogResponse/LogListResponse/WsEvent) + now_iso() helper
  - src/telesoft/__init__.py — package marker (empty)
  - src/telesoft/py.typed — PEP 561 marker (empty)
dependencies: []
last_updated: 2026-07-20 (PR#34)
---

# backend — src/telesoft/

> **Note:** `scripts/` (standalone spike/PoC скрипты) — отдельный модуль, НЕ часть `src/telesoft/`. См. [scripts.md](scripts.md).

## Structure

```
src/telesoft/
├── __init__.py   # Пустой — package marker
├── py.typed      # Пустой — PEP 561 marker (типы доступны внешним потребителям)
├── main.py       # FastAPI app: lifespan (init_db → EventBus + JobRunner(max_concurrency=settings.jobs_max_concurrency) start → start_client try/except → yield → runner.stop try/except → stop_client try/except → close_db), SessionMiddleware (signed cookie), include_router(auth + channels + jobs + ws), GET /health → {"status":"ok"}. app.state.event_bus / app.state.job_runner
├── config.py     # Settings frozen dataclass + from_env() classmethod + helpers (_get_int/_get_str/_get_list/_get_float). Поля: admin_*, secret_key, host/port/log_level, db_path, telegram_*, session_path, jobs_max_concurrency (env JOBS_MAX_CONCURRENCY, default 3), max_probe_id (env MAX_PROBE_ID, default 10000 — upper bound binary search для get_last_messages), telegram_request_delay (env TELEGRAM_REQUEST_DELAY, default 1.0 — delay между запросами к Telegram, flood control)
├── core/         # Telegram client + URL parser + link replacer + EventBus + JobRunner (bot-mode, by-ID fetch + auto-discovery последних N постов)
│   ├── __init__.py        # Пустой — package marker
│   ├── telegram.py        # Bot-mode Telethon singleton: get_client/start_client/stop_client/get_message/get_messages/edit_message/resolve_entity/get_bot_info + get_last_messages(channel_id, limit=100) auto-discovery через channels.GetMessagesRequest raw API (helpers: _get_channel_input → InputChannel с defensive getattr(access_hash, 0) PR#34, _fetch_messages_by_ids с FloodWaitError retry max 3, _find_max_id binary search с delay параметром PR#34)
│   ├── url_parser.py      # parse_post_url/parse_post_urls/is_valid_post_url — public + private channels, ?comment= игнорируется (НЕ импортируется в jobs.py с PR#34, сохранён для future use)
│   ├── link_replacer.py   # validate_pattern (re.compile fail-fast), replace_link (re.sub + findall count), replace_link_in_post (get_message by-ID → regex replace → edit_message; None→not-found, count==0→skipped, exception→success=False), find_posts_with_pattern (regex-фильтр списка Message PR#34), replace_link_in_posts orchestrator (summary {total,edited,failed,skipped} + on_progress callback PR#34)
│   ├── events.py          # EventBus: pub/sub на asyncio.Queue per subscriber; Event dataclass (type, data dict); subscribe()/publish()/unsubscribe(); fan-out через put_nowait
│   └── runner.py          # JobRunner: asyncio.Semaphore(max_concurrency), submit(job_id, chat_id, limit, pattern, new_link) → asyncio.create_task (PR#34: limit вместо message_ids), cancel(job_id) cooperative (_cancelled set + task.cancel), worker _run_job (mark running → get_last_messages(chat_id, limit) auto-discovery → find_posts_with_pattern → set total=len(matching) → publish job_started → loop matching: check _cancelled → replace_link_in_post → write log → publish progress → mark done/cancelled/failed + publish event)
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
│   ├── auth.py        # Auth helpers: verify_credentials (secrets.compare_digest), login/logout/current_user/require_auth (FastAPI Depends, Request-based), ws_current_user (WebSocket-based, reads websocket.scope["session"])
│   └── routers/
│       ├── __init__.py    # Пустой — package marker
│       ├── auth.py        # APIRouter(prefix="/api/auth"): POST /login, POST /logout (auth), GET /me (auth)
│       ├── channels.py    # APIRouter(prefix="/api/channels", dependencies=[Depends(require_auth)]): GET "" (list, ?active_only), POST "" (201/409), GET "/{id}" (200/404), PATCH "/{id}" (200/404/422), DELETE "/{id}" (204/404, FK CASCADE)
│       ├── jobs.py        # APIRouter(tags=["jobs"], dependencies=[Depends(require_auth)]) БЕЗ prefix: POST /api/channels/{channel_id}/replace-link (201, body ReplaceLinkRequest {pattern, new_link, limit=100}, validates channel/pattern, runner.submit с limit — url_parser НЕ импортируется PR#34), GET /api/jobs (filters + pagination), GET /api/jobs/{id} (404), GET /api/jobs/{id}/logs (404 + pagination), POST /api/jobs/{id}/cancel (404/409 if terminal)
│       └── ws.py          # APIRouter(tags=["ws"]) БЕЗ auth dependency: WS /api/ws — ws_current_user check (scope["session"]) → close(4001) if None; accept → bus.subscribe() → sender task (_forward_events: queue.get → send_json) + receive loop (_drain_client: receive_text до disconnect); cleanup on WebSocketDisconnect
└── schemas/      # Pydantic request/response models
    ├── __init__.py  # Пустой — package marker
    ├── auth.py      # LoginRequest(username, password), AuthResponse(status, user)
    ├── channel.py   # ChannelCreate, ChannelUpdate (@model_validator "хотя бы одно поле"), ChannelResponse (classmethod from_row), ChannelListResponse, now_iso() helper
    └── job.py       # ReplaceLinkRequest(pattern, new_link, limit: int = Field(default=100, ge=1, le=1000)) PR#34 (post_urls удалён), JobResponse (+ from_row), JobListResponse, LogResponse (+ from_row), LogListResponse, WsEvent (+ from_event, optional fields for all event types), now_iso() helper
```

## Patterns

- **src layout** (`src/telesoft/` вместо `telesoft/`) — изолирует пакет от корня репо
- **Frozen dataclass** для конфига — иммутабельный `Settings`, `from_env()` читает переменные окружения
- **Lifespan** для инициализации/закрытия ресурсов — `init_db()` + `EventBus`/`JobRunner` start + `start_client()` (try/except) на startup, `runner.stop()` + `stop_client()` (try/except) + `close_db()` на shutdown. Падение Telegram НЕ роняет app (логируется через loguru)
- **Health endpoint** `GET /health` — стандартный liveness probe (public, без auth)
- **Env-префиксы**: `ADMIN_`, `SECRET_KEY`, `TELEGRAM_`, `JOBS_MAX_CONCURRENCY`
- **Raw aiosqlite без ORM** (паттерн media-gen) — `CREATE TABLE IF NOT EXISTS` на startup, без миграций
- **`type Row = dict[str, Any]` (PEP 695)** — ruff UP040 запрещает `TypeAlias`
- **`@dataclass _State` holder** вместо `global` (ruff PLW0603) — singleton state в `db.connection._state.db` и `core.telegram._state.client/started`
- **`_CREATE_SQL` + `_CREATE_INDEXES_SQL`** константы на модуль — `init_db()` итерирует в порядке FK-зависимостей (channels → edit_jobs → edit_logs)
- **FK CASCADE** с `PRAGMA foreign_keys=ON` (default OFF в SQLite) — канал → job'ы → логи
- **WAL mode** для конкурентного чтения при write-операциях
- **`update_channel` whitelist** (`title`/`username`/`is_active`) — `ValueError` на неизвестном поле
- **CRUD функции принимают `aiosqlite.Connection` первым аргументом** — no global state в моделях
- **Bot-mode Telethon singleton** (`core/telegram.py`) — `TelegramClient(session_path, api_id, api_hash, receive_updates=False)` + `client.start(bot_token=...)`. Token в `start()`, НЕ в конструктор. File session (`settings.session_path`) для переиспользования между запусками (НЕ `MemorySession`)
- **By-ID fetch only** (для существующих методов) — `get_messages(chat_id, ids=[...])`. **КРИТИЧНО: НЕ `iter_messages`/`get_messages(limit=...)`** — `BotMethodInvalidError` для ботов (history iteration запрещён MTProto)
- **`get_last_messages` auto-discovery** (PR#32, perf improvements PR#34) — `get_last_messages(channel_id, limit=100)` через raw API `channels.GetMessagesRequest` (namespace `telethon.tl.functions.channels`, alias `ChannelsGetMessagesRequest`). Работает для bot-admin (в отличие от `iter_messages`). Алгоритм: binary search max_id (~14 probes с `settings.max_probe_id=10000`) + range fetch одним запросом `ids=list(range(max_id, start_id-1, -1))`. Total ~15 запросов независимо от N. Снимает ограничение PR#14 (by-ID fetch only) — auto-discovery без user-session. **PR#34 perf**: `Settings.from_env()` читается 1 раз в `get_last_messages`, `delay` передаётся параметром в `_find_max_id` (раньше 15 чтений env на каждый probe); trailing sleep после последнего probe убран (`if lo <= hi: await asyncio.sleep(delay)`)
- **`_get_channel_input(channel_id) -> InputChannel`** — `get_entity(channel_id)` → `InputChannel(entity.id, getattr(entity, "access_hash", 0))` (PR#34: defensive `getattr` default 0 — если `get_entity` вернёт не-Channel, `access_hash` может не быть → 0 вместо AttributeError). Raw API требует `InputChannel` (id без `-100` prefix + access_hash)
- **`_fetch_messages_by_ids` filter** — `m is not None and getattr(m, "date", None) is not None` фильтрует `None` (пост удалён/не существует) и `Message` с `date=None` (служебные). Возвращает `ChannelMessages.messages` (filtered)
- **FloodWaitError retry max 3** — try/except в `_fetch_messages_by_ids`, `await asyncio.sleep(exc.seconds + 1)` между retry, после 3 попыток re-raise (bounded retries, НЕ infinite как в spike PR#30). Caller решает retry/log/abort
- **`_find_max_id` binary search** (PR#32, PR#34) — `lo=1, hi=max_probe_id, last_existing=0`, probe `mid=(lo+hi)//2` через `_fetch_messages_by_ids([mid])`, non-empty → `last_existing=mid, lo=mid+1`, иначе `hi=mid-1`. `delay: float` параметр (PR#34, НЕ `Settings.from_env()` внутри). `await asyncio.sleep(delay)` после каждого probe КРОМЕ последнего (PR#34: `if lo <= hi` guard — когда binary search done, выход без sleep). Return `last_existing` (0 если все probes пустые)
- **`asyncio.sleep(settings.telegram_request_delay)`** между запросами к Telegram (default 1.0s) — после каждого probe в `_find_max_id` (КРОМЕ последнего, PR#34) и перед range fetch в `get_last_messages`. Для binary search (14 probes) + range fetch (1) — общее время ~15 секунд (PR#34: -1s за счёт убранного trailing sleep). НЕ уменьшать delay (flood risk) — лучше кешировать max_id (Pending)
- **`asyncio.Lock` + double-checked locking** в `start_client()` — защита от concurrent start (fast path до lock, slow path повторная проверка внутри `async with _connection_lock`)
- **`edit_message` propagates `RPCError`** — не глотает ошибки, caller решает retry/log/abort
- **URL parser regex** `^https?://t\.me/(c/)?(\w+)/(\d+)` — public (`mychannel/123` → `("mychannel", 123)`), private (`c/1234567890/456` → `(-1001234567890, 456)` через `int(f"-100{channel_part}")`), `?comment=` игнорируется
- **mypy override для telethon** — `[[tool.mypy.overrides]] module = ["telethon.*"] ignore_missing_imports = true` (telethon не имеет `py.typed`, scoped override, не глобальный)
- **SessionMiddleware** (Starlette, signed cookie через `itsdangerous`) — `app.add_middleware(SessionMiddleware, secret_key=Settings.from_env().secret_key)`. Cookie подписан HMAC-SHA256, данные в plaintext (base64) — НЕ хранить sensitive данные в session (только username). `request.session` — dict-like (`__getitem__`/`__setitem__`/`get`/`clear`). `SECRET_KEY` должен быть 32+ chars (itsdangerous требует ≥32 bytes для HMAC-SHA256)
- **`secrets.compare_digest`** для timing-safe сравнения username/password в `verify_credentials` — защита от timing attack (НЕ plaintext `==`). `Settings.from_env()` вызывается при каждом login (не cached)
- **`Depends(require_auth)` паттерн** — `require_auth` возвращает `str` (username) или бросает `HTTPException(401, "Not authenticated")`. Используется как `user: str = Depends(require_auth)` (если нужен username) или `_user: str = Depends(require_auth)` (если только auth, без использования — underscore prefix, ruff ARG001 не срабатывает)
- **`isinstance(user, str)` check в `current_user`** — защита от подмены типа в cookie (cookie подписан, но не зашифрован — тип может быть любым)
- **`async def` для auth helpers** — `verify_credentials`/`login`/`logout`/`current_user`/`require_auth` все async (консистентность + будущее расширение). `ws_current_user` — sync (WebSocket не имеет Request, читает scope напрямую)
- **`ws_current_user(websocket: Any) -> str | None`** — WebSocket auth helper, читает `websocket.scope["session"]` (Starlette SessionMiddleware кладёт session data в scope). `Any` для WebSocket (избегаем import WebSocket в auth.py). Без сессии → `websocket.close(code=4001)` (custom application-level unauthenticated). Отклонение от media-gen `current_user(websocket)` — mypy strict запрещает передавать WebSocket где ожидается Request
- **APIRouter с prefix/tags** — `APIRouter(prefix="/api/auth", tags=["auth"])`. Endpoints: `POST /login`, `POST /logout` (auth), `GET /me` (auth). `GET /health` остаётся public (вне router)
- **Pydantic schemas** в `schemas/` — `LoginRequest` (request body), `AuthResponse` (response для /login). `/logout` и `/me` возвращают `dict[str, str]` (без `response_model`)
- **Auth на весь роутер** через `APIRouter(..., dependencies=[Depends(require_auth)])` (channels + jobs routers) — DRY, нельзя случайно забыть auth на новом эндпоинте. Если нужен public эндпоинт под тем же prefix — выносить в отдельный роутер без `dependencies`
- **CRUD router pattern** (channels): 5 эндпоинтов поверх DB-моделей (PR#12) через `async with get_db() as db:`. Status codes: 201 (create), 409 (duplicate telegram_id), 404 (not found), 422 (empty PATCH body via Pydantic validator), 204 (delete, FK CASCADE на edit_jobs/edit_logs)
- **Pydantic `@model_validator(mode="after")`** для "хотя бы одно поле" в `ChannelUpdate` — бросает `ValueError` если все поля `None` → FastAPI автоматически возвращает 422. `mode="after"` (не `"before"`) — корректно работает с `{}` body
- **`ChannelResponse.from_row` classmethod** — конвертирует dict-like `aiosqlite.Row` в Pydantic model с явными casts (`int()`/`str()`/`bool()`) для SQLite-типов. Идиоматичный Pydantic паттерн (не standalone function)
- **`now_iso()` helper** — `datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` → `"2026-07-20T12:34:56Z"` (ISO 8601 UTC с trailing `Z`, формат из спеки). НЕ `isoformat()` с `+00:00`. Дублирован в `schemas/channel.py` и `schemas/job.py` (PR#20 + PR#22)
- **`PATCH` not `PUT`** для partial update — `ChannelUpdate` с all-optional fields + `model_validator` для "хотя бы одно поле". Семантически корректнее для partial (RFC 5789)
- **`dict[str, str | int | None]` для PATCH fields** — mypy strict требует explicit type для `**fields` в `update_channel(db, channel_id=..., **fields)`. `dict[str, object]` → mypy `arg-type` error
- **`int(payload.is_active)` cast** в PATCH — SQLite хранит `is_active` как INTEGER (0/1), Pydantic `bool` → Python `True`/`False` → `int()` для совместимости с `str | int | None` типом `update_channel`
- **Regex link replacement** (`core/link_replacer.py`) — `validate_pattern` (re.compile fail-fast, 422 в router), `replace_link` (re.sub + len(re.findall) для подсчёта), `replace_link_in_post` (get_message by-ID → regex replace → edit_message). None → not-found, count==0 → skipped (edit НЕ вызывается), exception → success=False (caller решает retry/log). `text = message.text or ""` (media-only → None → skipped). **PR#34 добавил**: `find_posts_with_pattern(messages, pattern)` — regex-фильтр списка Message (НЕ fetch'ит из Telegram, defensive `getattr(m, "text", None) or ""` для text=None); `replace_link_in_posts(chat_id, messages, pattern, new_link, on_progress=None)` — orchestrator, summary `{total, edited, failed, skipped}`, `on_progress: Callable[[int, int, int], Awaitable[None]] | None` callback. Orchestrator НЕ используется в runner (runner сам итерирует для publish progress + write log на каждом шаге) — public API для future use (preview/dry-run)
- **EventBus pub/sub** (`core/events.py`) — `asyncio.Queue` per subscriber, `subscribe()`/`publish()`/`unsubscribe()`. `Event` dataclass (type: str, data: dict[str, object]). Fan-out через `put_nowait`. One instance per app (`app.state.event_bus`). Паттерн 1-в-1 из media-gen
- **JobRunner** (`core/runner.py`) — `asyncio.Semaphore(max_concurrency)` для лимита concurrent edits (Telegram rate limits). **PR#34**: `submit(job_id, chat_id, limit, pattern, new_link)` (вместо `message_ids`) → `asyncio.create_task`, registry `_tasks[job_id] = task`. Все параметры явно (НЕ из БД — telesoft `edit_jobs` не имеет JSON-колонок, отличие от media-gen). Worker: `async with sem` → mark running → `get_last_messages(chat_id, limit)` auto-discovery → `find_posts_with_pattern(messages, pattern)` → `total = len(matching)` → `update_job_status(total=total)` → publish `job_started` с `total=len(matching)` (НЕ limit) → loop matching: check `_cancelled` → `replace_link_in_post` → update progress → write log → publish `progress`. В конце: `done` + `completed` event. CancelledError → `cancelled` event + re-raise. Exception → `failed` event. `finally` — `_tasks.pop` + `_cancelled.discard`
- **Cooperative cancellation** — `cancel(job_id)` → `task.cancel()` + `_cancelled.add(job_id)`. Worker проверяет `if job_id in self._cancelled: raise asyncio.CancelledError` перед каждым message_id. Сancellation между edits — между post fetch'ами НЕ прерывается (Telethon call в полёте). MVP достаточно
- **Jobs router БЕЗ prefix** (`api/routers/jobs.py`) — `APIRouter(tags=["jobs"], dependencies=[Depends(require_auth)])` без prefix, т.к. эндпоинт `/api/channels/{channel_id}/replace-link` не подходит под `/api/jobs`. Полный путь в `@router.post(...)`. Auth на весь роутер (PR#20 паттерн). **PR#34**: body = `ReplaceLinkRequest {pattern, new_link, limit=100}` (post_urls удалён), `runner.submit(job_id, channel.telegram_id, limit, pattern, new_link)`, `url_parser` import убран (backend сам находит посты через `get_last_messages`). Валидация: channel_id (404) + pattern (422 через `validate_pattern`)
- **`_resolve_chat_and_ids`** (PR#22, removed PR#34) — ранее сверял parsed URL chat_id/username с `channel.telegram_id`/`channel.username`. **PR#34 убрал** — `url_parser` больше не импортируется в `jobs.py`, endpoint принимает `limit` вместо `post_urls`, backend сам находит посты через `get_last_messages`. `chat_id` для runner = `channel.telegram_id` всегда
- **WebSocket router** (`api/routers/ws.py`) — `APIRouter(tags=["ws"])` без auth dependency (WS не работает с `Depends` через cookie). `WS /api/ws` — `ws_current_user(websocket)` check → `close(4001)` if None. Иначе `accept()` → `bus.subscribe()` → sender task (`_forward_events`: `queue.get()` → `send_json({"type", "data"})`) + receive loop (`_drain_client`: `receive_text()` до disconnect). На `WebSocketDisconnect` — cancel sender + `bus.unsubscribe(queue)`. Heartbeat НЕ реализован (MVP)
- **`WsEvent.from_event`** — `Event.data` — `dict[str, object]`, WsEvent fields — specific (job_id, edited, failed, total, message_id, error). Extra keys → Pydantic v2 ignore (NO `extra="forbid"`). `type` — отдельный positional field, не в data
- **`edit_jobs` НЕ имеет `error` column** — schema из PR#12 имеет `status`/`total`/`edited`/`failed`/`created_at`/`completed_at`, но НЕТ `error`. Runner НЕ persist'ит error в БД (только в event bus + logger). Если понадобится — миграция в новом PR
- **`get_runner` dependency** — `getattr(request.app.state, "job_runner")` + `cast("JobRunner", runner)`. 503 если runner не init (defensive, pragma: no cover)
- **ruff `B008` per-file-ignores** для `src/telesoft/api/routers/*` (Depends в default args). `TRY301` `# noqa` на `raise asyncio.CancelledError` в worker loop (cooperative cancellation, нельзя вынести в helper). Дополнительно: `scripts/*` = [T201, S603, S101, TRY300] (PR#30, spike scripts — см. [scripts.md](scripts.md)), `tests/*` = [S101, PLR2004, S106, S603, S607, S108, S104, S105], `src/telesoft/db/models/*` = [S608] (f-string table names — false positive).

## Dependencies

- fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru
- dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, httpx (для TestClient)