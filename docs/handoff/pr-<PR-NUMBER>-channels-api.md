---
pr: <PR-NUMBER>
issue: 19
branch: feat/api/channels-crud
status: ready
created: 2026-07-20
---

# Handoff — PR #<PR-NUMBER>: channels CRUD API

## Что сделано

Реализован issue #19 — стандартный CRUD над таблицей `channels` (PR#12) под `/api/channels` с auth на весь роутер (`Depends(require_auth)` из PR#18). 5 эндпоинтов, Pydantic schemas в отдельном модуле, 14 тестов через `authed_client` фикстуру.

### Шаг 1: Schemas (`src/telesoft/schemas/channel.py`)

- `class ChannelCreate(BaseModel): telegram_id: int; title: str; username: str | None = None`.
- `class ChannelUpdate(BaseModel): title: str | None = None; username: str | None = None; is_active: bool | None = None` с `@model_validator(mode="after")` `_at_least_one` — бросает `ValueError("At least one field must be provided")` если все поля `None` → FastAPI возвращает 422.
- `class ChannelResponse(BaseModel): id: int; telegram_id: int; title: str; username: str | None; is_active: bool; added_at: str` + classmethod `from_row(cls, row: ChannelRow) -> ChannelResponse` — конвертирует dict-like row (aiosqlite.Row) в Pydantic model, с `int()`/`str()`/`bool()` casts для совместимости с SQLite types.
- `class ChannelListResponse(BaseModel): channels: list[ChannelResponse]; total: int`.
- `def now_iso() -> str` — `datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` (ISO 8601 UTC с trailing `Z`, формат из спеки issue #19).

### Шаг 2: Channels router (`src/telesoft/api/routers/channels.py`)

- `router = APIRouter(prefix="/api/channels", tags=["channels"], dependencies=[Depends(require_auth)])` — auth применён ко всему роутеру (все 5 эндпоинтов требуют сессию). Без сессии → 401.
- `GET ""` (response_model=`ChannelListResponse`) — query `active_only: bool = False`. Вызывает `list_channels(db, active_only=...)`, конвертирует rows → `ChannelResponse.from_row`. Возвращает `{channels, total}`.
- `POST ""` (response_model=`ChannelResponse`, status_code=201) — body `ChannelCreate`. Сначала `get_channel_by_telegram_id` для проверки уникальности; если существует → 409 Conflict (`"Channel with telegram_id {id} already exists"`). Иначе `create_channel(..., added_at=now_iso())` → 201.
- `GET "/{channel_id}"` (response_model=`ChannelResponse`) — `_get_channel_or_404` helper (404 если нет). Возвращает `ChannelResponse.from_row`.
- `PATCH "/{channel_id}"` (response_model=`ChannelResponse`) — body `ChannelUpdate`. Сначала `_get_channel_or_404` (404 если нет). Собирает `fields: dict[str, str | int | None]` только из non-None полей payload (`title`, `username`, `is_active` → `int(payload.is_active)` т.к. SQLite хранит is_active как INTEGER). Вызывает `update_channel(db, channel_id=..., **fields)`. Пустое body → 422 (model_validator в ChannelUpdate).
- `DELETE "/{channel_id}"` (status_code=204) — `_get_channel_or_404` (404 если нет), `delete_channel(...)`. Возвращает 204 No Content. FK CASCADE (PRAGMA foreign_keys=ON из PR#12) удаляет связанные `edit_jobs` и `edit_logs`.
- БД через `async with get_db() as db:` паттерн (singleton aiosqlite connection из PR#12).
- `_get_channel_or_404` — async helper, возвращает `channel_model.ChannelRow` или бросает 404.

### Шаг 3: Интеграция в main.py

- `from telesoft.api.routers.channels import router as channels_router`.
- `app.include_router(channels_router)` после `app.include_router(auth_router)`.
- `GET /health` остаётся public (без auth).

### Шаг 4: Тесты (`tests/test_api_channels.py`, 14 тестов)

- `db_handle` fixture — exposes shared app DB connection (`connection._state.db`) для прямых SQL-запросов в cascade-тесте.
- `_create_channel` helper — POST /api/channels с валидным body, assert 201, return body dict.
- 14 тестов (все через `authed_client` кроме `test_create_channel_requires_auth`):
  1. `test_list_channels_empty` — GET без каналов → 200, `{"channels": [], "total": 0}`.
  2. `test_list_channels_returns_all` — 3 канала → total=3.
  3. `test_list_channels_active_only` — 2 active + 1 inactive, `?active_only=true` → 2.
  4. `test_create_channel_success` — POST → 201, response содержит id/telegram_id/title/username/is_active/added_at.
  5. `test_create_channel_duplicate_telegram_id` — POST с существующим telegram_id → 409.
  6. `test_create_channel_requires_auth` — без логина → 401 (использует отдельный TestClient без authed_client).
  7. `test_get_channel_by_id` — GET /api/channels/{id} → 200.
  8. `test_get_channel_not_found` — GET /9999 → 404.
  9. `test_update_channel_success` — PATCH с `{title: "new"}` → 200, title обновлён.
  10. `test_update_channel_not_found` — PATCH /9999 → 404.
  11. `test_update_channel_no_fields` — PATCH с `{}` → 422 (Pydantic model_validator).
  12. `test_delete_channel_success` — DELETE → 204, последующий GET → 404.
  13. `test_delete_channel_not_found` — DELETE /9999 → 404.
  14. `test_delete_channel_cascade_jobs_logs` — создать channel + job + log через model functions напрямую (db_handle), DELETE channel → jobs и logs удалены (FK CASCADE, проверка через `list_jobs`/`list_logs`).

### Шаг 5: conftest.py — `authed_client` фикстура

- `authed_client` (async) — monkeypatch env vars (`SECRET_KEY` 32+ chars, `ADMIN_USERNAME=admin`, `ADMIN_PASSWORD=secret`, `DB_PATH=tmp`), `TestClient(app)` as context manager (trigger lifespan → init_db), `POST /api/auth/login` с admin/secret, assert 200, yield client. Аналог `client` фикстуры из `test_auth.py`, но с предзаполненной сессией.
- Импорты добавлены: `from fastapi.testclient import TestClient`, `from telesoft.main import app`.

## Почему

Юзер управляет каналами через UI: добавляет канал (telegram_id + title + username), видит список, удаляет неактуальные. Каналы — сущность, к которой привязываются запуски замены ссылок (`edit_jobs.channel_id` FK, PR#12). Без CRUD API нет фронтенда для управления каналами. Auth на весь роутер (а не на каждый эндпоинт) — DRY, нельзя случайно забыть `Depends(require_auth)` на новом эндпоинте. Pydantic schemas в отдельном модуле (`schemas/channel.py`, не в router) — separation of concerns, схемы переиспользуются в тестах и потенциально в фронтенде (через OpenAPI). Референс паттерна: `/root/workspace/media-gen/src/media_gen/api/routers/channels.py` + `schemas/channel.py`.

## Pending

- **Edit jobs API** — CRUD над `edit_jobs` (запуск замены ссылок в канале). Отдельный issue.
- **Edit logs API** — read-only доступ к `edit_logs`. Отдельный issue.
- **Replace-link worker** — эндпоинт запуска замены (.Telethon client из PR#16). Отдельный issue.
- **Frontend channels UI** — список, форма добавления, удаление в SvelteKit. Отдельный issue.

## Watch out

- **`dependencies=[Depends(require_auth)]` на роутере** — auth применяется ко ВСЕМ эндпоинтам роутера. Если нужно добавить public эндпоинт под `/api/channels` — выносить в отдельный роутер без `dependencies`. Нельзя случайно забыть auth на новом эндпоинте.
- **`ChannelUpdate` `@model_validator(mode="after")`** — Pydantic v2 validator. Бросает `ValueError` если все поля `None` → FastAPI автоматически возвращает 422. НЕ использовать `mode="before"` (не срабатывает на пустом dict корректно). `mode="after"` проверяет после Pydantic-init.
- **`from_row` casts** — `int(row["id"])`, `bool(row["is_active"])` — SQLite возвращает `aiosqlite.Row` (dict-like), но типы могут быть `bytes`/`int`/`None`. Явные casts (`int`/`str`/`bool`) гарантируют Pydantic-совместимость. `is_active` хранится как INTEGER (0/1), `bool()` конвертирует корректно.
- **`now_iso()` формат** — `strftime("%Y-%m-%dT%H:%M:%SZ")` даёт `"2026-07-20T12:34:56Z"` (с `Z`, без microseconds, без `+00:00`). Спека issue #19 явно требует этот формат. Существующие DB-тесты используют `datetime.now(tz=UTC).isoformat()` (`+00:00`) — это ОК, БД хранит TEXT, `ChannelResponse.added_at` возвращает строку как есть.
- **`PATCH` not `PUT`** — спека требует `PATCH` (partial update). media-gen использует `PUT` (full replace) — telesoft отклоняется в пользу `PATCH` (семантически корректнее для partial). `ChannelUpdate` с all-optional fields → PATCH-семантика.
- **`fields: dict[str, str | int | None]`** — mypy strict требует явный тип для `**fields` в `update_channel(db, channel_id=..., **fields)`. `dict[str, object]` → mypy `arg-type` error (model expects `str | int | None`). `dict[str, str | int | None]` — корректно.
- **`is_active` → `int(payload.is_active)`** — SQLite хранит `is_active` как INTEGER (0/1). Pydantic `bool` → Python `True`/`False`. `int(True)` = 1, `int(False)` = 0 — корректная конвертация. Без `int()` → aiosqlite передаёт Python bool → SQLite хранит как 1/0, но mypy ругается на тип (не `str | int | None`).
- **FK CASCADE test** — `test_delete_channel_cascade_jobs_logs` создаёт channel через API, затем job + log через model functions напрямую (`job_model.create_job`, `log_model.create_log`) используя `db_handle` fixture (shared app DB connection). После `DELETE /api/channels/{id}` проверяет `list_jobs`/`list_logs` → пусто. CASCADE работает потому что PR#12 включил `PRAGMA foreign_keys=ON` в `init_db()`.
- **`authed_client` — async fixture** — `async def authed_client(...)` с `yield TestClient`. pytest-asyncio `auto` mode поддерживает async fixtures без декоратора. Используется в sync-тестах (`def test_...`) и async-тестах (`async def test_...`) — оба работают.
- **`connection._state.db` direct access** — `db_handle` fixture читает приватный `_state` из `db.connection` для direct SQL queries в cascade-тесте. Это приватный API, но `connection` module стабилен (PR#12). Альтернатива — отдельная `get_db()` call, но это вернулo бы тот же singleton.
- **Coverage 96.42%** — `api/routers/channels.py` 97% (uncovered: defensive `assert row is not None` after `_get_channel_or_404` — mypy hint, не выполняется). `schemas/channel.py` 100%. Общее покрытие ≥80% — gate пройден.
- **mypy strict** — `from telesoft.db.models import ChannelRow` в schemas/channel.py (type-only usage в `from_row` signature). `dict[str, str | int | None]` для `fields` в PATCH. Все async endpoints typed.
- **ruff** — `model_validator` import из `pydantic`. `dict[str, str | int | None]` type hint. Per-file-ignores для `tests/*` покрывают S101/S104/S105/S106/S603/S607/S108 (используемые паттерны). `test_create_channel_requires_auth` создаёт отдельный TestClient (без `authed_client`) — без сессии → 401.