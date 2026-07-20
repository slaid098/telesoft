# ADR — PR #20: channels CRUD API

## Статус

Accepted (2026-07-20) — реализован стандартный CRUD над таблицей `channels` под `/api/channels` с auth на весь роутер через `dependencies=[Depends(require_auth)]`. Pydantic schemas в отдельном модуле `schemas/channel.py` (не в router). 5 эндпоинтов: GET /, POST /, GET /{id}, PATCH /{id}, DELETE /{id}.

## Контекст

telesoft — Telegram channel post editor. Юзер управляет каналами через UI: добавляет (telegram_id + title + username), видит список, удаляет неактуальные. Каналы — сущность, к которой привязываются запуски замены ссылок (`edit_jobs.channel_id` FK, PR#12). Нужен CRUD API поверх существующих DB-функций (`channel_model.create_channel`/`get_channel`/`list_channels`/`update_channel`/`delete_channel` из PR#12). Auth уже есть (PR#18, `require_auth` dependency). Референс паттерна: `/root/workspace/media-gen/src/media_gen/api/routers/channels.py` + `schemas/channel.py`.

Решения, которые надо было принять:
1. Auth на каждый эндпоинт vs на весь роутер.
2. Pydantic schemas в router vs отдельный модуль.
3. `PUT` (full replace) vs `PATCH` (partial update).
4. `added_at` timestamp — формат ISO 8601 с `Z` vs `+00:00`.
5. `ChannelUpdate` валидация "хотя бы одно поле" — Pydantic validator vs manual check в router.
6. `from_row` helper — classmethod на `ChannelResponse` vs standalone function.

## Решение

### Auth на весь роутер (`dependencies=[Depends(require_auth)]`)

- `APIRouter(prefix="/api/channels", tags=["channels"], dependencies=[Depends(require_auth)])`.
- Все 5 эндпоинтов автоматически требуют сессию. Без сессии → 401.
- Нельзя случайно забыть auth на новом эндпоинте (DRY). Если нужен public эндпоинт — выносить в отдельный роутер.

### Pydantic schemas в `schemas/channel.py`

- `ChannelCreate`, `ChannelUpdate`, `ChannelResponse`, `ChannelListResponse` — все в `schemas/channel.py`.
- `now_iso()` helper — тоже в schemas (используется только в router, но логически связан с `added_at`).
- Separation of concerns: router не содержит Pydantic-классов, только endpoint-логику.
- Схемы переиспользуются в тестах (через OpenAPI/client), потенциально в фронтенде (через OpenAPI types).
- Паттерн 1-в-1 с `schemas/auth.py` (PR#18) и media-gen референсом.

### `PATCH` для partial update (не `PUT`)

- Спека issue #19 требует `PATCH /api/channels/{id}` с partial body.
- `ChannelUpdate` — все поля optional (`str | None`, `bool | None`).
- media-gen использует `PUT` (full replace) — telesoft отклоняется в пользу `PATCH` (семантически корректнее для partial update, RFC 5789).
- `PATCH` с `{}` → 422 (model_validator требует хотя бы одно поле).

### `added_at` timestamp формат `"2026-07-20T12:34:56Z"`

- `now_iso() -> str` возвращает `datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`.
- Формат с trailing `Z` (не `+00:00`) — по спеке issue #19. Канонический ISO 8601 UTC.
- Существующие DB-тесты (PR#12) используют `datetime.now(tz=UTC).isoformat()` (`+00:00`) — БД хранит TEXT, оба формата валидны. `ChannelResponse.added_at` возвращает строку как есть.

### `ChannelUpdate` валидация через Pydantic `@model_validator(mode="after")`

- `_at_least_one` validator бросает `ValueError("At least one field must be provided")` если все поля `None`.
- FastAPI автоматически конвертирует `ValueError` в 422 response (validation error).
- НЕ manual check в router (`if not any([payload.title, payload.username, payload.is_active]): raise HTTPException(422)`) — Pydantic validator декларативнее, переиспользуется.
- `mode="after"` (не `"before"`) — проверка после Pydantic-init, корректно работает с `{}` body.

### `from_row` classmethod на `ChannelResponse`

- `@classmethod from_row(cls, row: ChannelRow) -> ChannelResponse` — конвертирует dict-like row (aiosqlite.Row) в Pydantic model.
- Явные casts: `int(row["id"])`, `str(row["title"])`, `bool(row["is_active"])` — SQLite возвращает `aiosqlite.Row`, типы могут быть int/bytes/None. Casts гарантируют Pydantic-совместимость.
- classmethod (не standalone function) — идиоматичный Pydantic паттерн, вызывается как `ChannelResponse.from_row(row)`.
- `ChannelRow` импортирован из `telesoft.db.models` (PEP 695 `type ChannelRow = dict[str, Any]` из PR#12).

### Standard CRUD endpoints

- `GET ""` → `ChannelListResponse` (200).
- `POST ""` + `ChannelCreate` → `ChannelResponse` (201) или 409 (duplicate telegram_id).
- `GET "/{id}"` → `ChannelResponse` (200) или 404.
- `PATCH "/{id}"` + `ChannelUpdate` → `ChannelResponse` (200) или 404 или 422 (no fields).
- `DELETE "/{id}"` → 204 No Content или 404. FK CASCADE удаляет связанные `edit_jobs` и `edit_logs`.
- БД через `async with get_db() as db:` (singleton aiosqlite connection из PR#12).

## Альтернативы

### Auth на каждый эндпоинт (а не на роутер)

- Pro: granular control (можно сделать `GET /` public, остальные auth).
- Con: boilerplate (`_user: str = Depends(require_auth)` на каждом эндпоинте), легко забыть.
- Решение: auth на роутере через `dependencies=[...]` — DRY, все эндпоинты защищены по умолчанию. Если нужен public эндпоинт — отдельный роутер без dependencies.

### Pydantic schemas в router (inline)

- Pro: меньше файлов, всё в одном месте.
- Con: router раздувается, схемы не переиспользуются, смешение validation logic и endpoint logic.
- Решение: отдельный `schemas/channel.py` — separation of concerns, паттерн из PR#18 (`schemas/auth.py`) и media-gen.

### `PUT` (full replace) как в media-gen

- Pro: совместимость с media-gen референсом.
- Con: `PUT` семантически означает full replace (все поля required), `PATCH` — partial update (optional fields). Спека issue #19 требует partial update.
- Решение: `PATCH` + `ChannelUpdate` с all-optional fields + `model_validator` для "хотя бы одно поле".

### Manual check в router для "хотя бы одно поле"

- Pro: explicit, не зависит от Pydantic validator internals.
- Con: boilerplate, не декларативно, логика в router вместо schema.
- Решение: Pydantic `@model_validator(mode="after")` — декларативно, переиспользуемо, FastPI автоматически возвращает 422.

### Standalone `_row_to_response(row)` function (как в media-gen)

- Pro: совместимость с media-gen референсом.
- Con: не идиоматичный Pydantic, вызов `_row_to_response(row)` вместо `ChannelResponse.from_row(row)`.
- Решение: `classmethod from_row` — идиоматичный Pydantic паттерн, вызывается на классе.

## Ключевые отклонения от спецификации

Зафиксированы в handoff, раздел "Watch out":
1. **`PATCH` не `PUT`** — спека issue #19 явно требует `PATCH` (media-gen использует `PUT`, telesoft отклоняется).
2. **`now_iso()` формат с `Z`** — спека issue #19 явно требует `"2026-07-20T12:34:56Z"` (strftime с `%SZ`), не `isoformat()` с `+00:00`.
3. **`@model_validator(mode="after")` для "хотя бы одно поле"** — Pydantic v2 validator, не manual check в router.
4. **`from_row` classmethod** — идиоматичный Pydantic, не standalone function как в media-gen.
5. **`dict[str, str | int | None]` для PATCH fields** — mypy strict требует explicit type для `**fields`, `dict[str, object]` → mypy error.
6. **`int(payload.is_active)` cast** — SQLite хранит is_active как INTEGER, Pydantic bool → Python bool → `int()` для совместимости с `str | int | None` типом `update_channel`.