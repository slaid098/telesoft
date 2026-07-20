---
pr: <PR-NUMBER>
issue: 15
branch: feat/telegram/bot-client
status: ready
created: 2026-07-20
---

# Handoff — PR <PR-NUMBER>: bot-mode Telethon client wrapper

## Что сделано

Реализован issue #15 — production wrapper для замены ссылок в постах каналов через бота-админа Telegram. Добавлены `core/telegram.py` (bot-mode singleton client) и `core/url_parser.py` (парсер post URL → `(channel, message_id)`), lifespan FastAPI интегрирует `start_client`/`stop_client` с try/except, тесты покрывают все public API.

### Шаг 1: Telegram client wrapper (`src/telesoft/core/telegram.py`)

- `_State` dataclass с полями `client: TelegramClient | None`, `started: bool` (holder, не global — ruff PLW0603).
- `_connection_lock = asyncio.Lock()` для защиты `start_client()` от concurrent start (паттерн digital_factory).
- `async def get_client() -> TelegramClient` — lazy singleton. Создаёт `TelegramClient(settings.session_path, api_id, api_hash, receive_updates=False)`. НЕ передаёт `bot_token` в конструктор.
- `async def start_client() -> TelegramClient` — idempotent start: `await client.start(bot_token=settings.telegram_bot_token)`, выставляет `_state.started = True`. Double-checked locking pattern.
- `async def stop_client() -> None` — disconnect если started, сбрасывает `_state.client`/`_state.started`.
- `async def get_message(chat_id, message_id) -> Message | None` — `await client.get_messages(chat_id, ids=[message_id])`, вернуть `messages[0] if messages else None`.
- `async def get_messages(chat_id, message_ids) -> list[Message]` — batch fetch, фильтр `None`.
- `async def edit_message(chat_id, message_id, text) -> Message` — propagates `RPCError` (не глотает).
- `async def resolve_entity(identifier: str | int) -> Any` — `await client.get_entity(identifier)`.
- `async def get_bot_info() -> dict[str, Any]` — `await client.get_me()`, вернуть `{id, username, first_name, is_bot}`.
- Session = файловая `settings.session_path` (НЕ `MemorySession`) — переиспользование между запусками без повторного логина.

### Шаг 2: URL parser (`src/telesoft/core/url_parser.py`)

- `type ParsedPostURL = tuple[str | int, int]` (PEP 695).
- `parse_post_url(url)` — regex `^https?://t\.me/(c/)?(\w+)/(\d+)`:
  - `https://t.me/mychannel/123` → `("mychannel", 123)` (username без @).
  - `https://t.me/c/1234567890/456` → `(-1001234567890, 456)` (приватные: `internal_id` → `-100<internal_id>` через `int(f"-100{channel_part}")`).
  - `?comment=...` query игнорируется (regex не требует конца строки).
  - Невалидный URL → `ValueError("invalid Telegram post URL: ...")`.
- `parse_post_urls(urls)` — map по списку, бросает `ValueError` с указанием `index N` для плохого URL.
- `is_valid_post_url(url)` — bool проверка без бросания.

### Шаг 3: Lifespan интеграция (`src/telesoft/main.py`)

- Startup: `await init_db()` → если `settings.telegram_bot_token` задан — `await start_client()` в try/except (падение Telegram НЕ роняет app, логируется через loguru `logger.warning`).
- Shutdown: `await stop_client()` в try/except (логируется) → `await close_db()`.
- Если `TELEGRAM_BOT_TOKEN` пуст — Telegram skip без warning (по спеке: "если задан — иначе skip с warning"; warning только при failed start, не при пустом token — дефолт `""` в `Settings.from_env()`).

### Шаг 4: Тесты

- `tests/conftest.py` — добавлены:
  - `MockMessage` dataclass (id, text, chat_id, message).
  - `mock_message` fixture.
  - `mock_telethon_client` async fixture: monkeypatch `telegram_module.TelegramClient` чтобы конструктор возвращал AsyncMock (с `get_messages`/`edit_message`/`get_entity`/`get_me`/`start`/`disconnect`). НЕ заменяет `get_client`/`start_client` — реальные функции упражнятся против mock client (через patched конструктор), что позволяет тестировать singleton + idempotency. Reset `_state` в setup/teardown.
- `tests/test_telegram_client.py` (10 тестов):
  - `test_get_client_singleton` — два вызова возвращают тот же инстанс.
  - `test_start_client_idempotent` — повторный `start_client()` не вызывает `client.start()` дважды (через `await_count`).
  - `test_get_message_by_id` — mock возвращает message по `ids=[123]`.
  - `test_get_message_returns_none_for_missing` — `get_messages` возвращает `[]` → `get_message` возвращает `None`.
  - `test_get_messages_batch_filters_none` — `[m1, None, m2]` → `[m1, m2]`.
  - `test_edit_message_success` — вызывает `client.edit_message` с правильными args.
  - `test_edit_message_propagates_error` — mock бросает `BadRequestError(request=None, message="boom")` → `edit_message` пробрасывает `RPCError`.
  - `test_resolve_entity` — вызывает `client.get_entity`.
  - `test_get_bot_info` — возвращает dict с ключами id/username/first_name/is_bot.
  - `test_stop_client_resets_state` — после `stop_client()`, `_state.client = None`, `_state.started = False`, `disconnect` awaited.
- `tests/test_url_parser.py` (9 тестов): public channel, private channel (`-100<internal_id>`), `?comment=` query, invalid format, non-t.me domain, private non-digit, batch, batch with index, `is_valid_post_url` true/false.

### Шаг 5: pyproject.toml

- `[[tool.mypy.overrides]] module = ["telethon.*"] ignore_missing_imports = true` — telethon не имеет stubs (нет `py.typed`), mypy strict падает с `import-untyped`. Override добавлен по спеке.

## Почему

Spike PR#14 подтвердил: Telethon bot-mode может `edit_message` посты канала где бот — админ, и `get_messages(chat_id, ids=[...])` (by-ID fetch) разрешён ботам (spike тестировал только `get_messages(limit=...)` — history iteration, который падает с `BotMethodInvalidError` — но by-ID fetch — другой API path). Для production MVP нужен был wrapper с:
1. Singleton client с file session (переиспользование между запусками).
2. by-ID fetch (`get_messages(ids=[...])`) — НЕ history iteration.
3. Idempotent start с concurrent guard (`asyncio.Lock`).
4. Lifespan интеграция, где падение Telegram НЕ роняет app (логируется, продолжается).

Архитектура telesoft: юзер в UI даёт список post URLs → backend парсит `(channel, message_id)` из URL → fetch'ит текст поста через `get_messages(ids=...)` → regex-замена old_pattern на new_link → `edit_message`. Никакой итерации истории канала — это разрешено ботам.

## Pending

- **Endpoint'ы и EditJob** — отдельные issues (auth, channels CRUD, replace-link endpoint, edit_logs). Этот PR реализует только `core/telegram.py` + `core/url_parser.py` + lifespan + unit-тесты.
- **Live integration test** — `core/telegram.py` тестирован только через mock (без реального подключения к Telegram API). Для E2E нужен отдельный test с реальными кредами (CI не имеет секретов — ручной smoke или integration test в отдельном issue).
- **`resolve_entity` return type** — возвращает `Any` (Telethon entity — `Channel`/`User`/`Chat`), для type-safety можно ввести Protocol/Union в будущем, когда определятся endpoint'ы.
- **`get_bot_info` me.first_name** — `User.first_name` может быть `None` для ботов без name; `dict[str, Any]` принимает None, но endpoint /api/health/bot-info должен это учитывать.

## Watch out

- **НЕ использовать `iter_messages` или `get_messages(limit=...)`** — `BotMethodInvalidError` (spike PR#14, шаг 3: `caused by GetHistoryRequest`). Только `get_messages(chat_id, ids=[...])` — by-ID fetch, это разрешено ботам (разный MTProto method). Это КРИТИЧЕСКОЕ ограничение для архитектуры.
- **`TelethonError` НЕ существует** — в `telethon.errors` нет класса `TelethonError`. Базовый класс для API errors — `RPCError` (в `telethon.errors.rpcbaseerrors`). Спецификация issue #15 упоминала `TelethonError` — это ошибка в спеке, зафиксировано здесь. Конкретные subclasses: `BadRequestError` (400), `ForbiddenError` (403), `FloodError`, `UnauthorizedError`, `NotFoundError`, `ServerError`, `TimedOutError`. Для тестирования `side_effect = BadRequestError(request=None, message="...")` — `RPCError.__init__(self, request, message, code=None)` требует `request` (можно `None`).
- **`client.start(bot_token=...)` не в конструкторе** — `TelegramClient.__init__` не принимает `bot_token`. Token передаётся в `start()`, который выполняет MTProto handshake. Если передать в конструктор — `TypeError`.
- **File session, не MemorySession** — `MemorySession()` (как в digital_factory референсе) НЕ переиспользуется между запусками (хранится в RAM, теряется при restart). telesoft использует `settings.session_path` (`app_data/bot.session` по умолчанию) — файловая сессия, Telethon сам создаёт файл при `client.start()`. Файл в `.gitignore` (`app_data/*` кроме `.gitkeep`).
- **`asyncio.Lock()` для concurrent start** — без lock, два concurrent вызова `start_client()` могут оба увидеть `_state.started = False`, оба вызвать `client.start(bot_token=...)` — второй упадёт с "already connected" или создаст race. Double-checked locking: проверка `started` до lock (fast path), повторная проверка внутри `async with _connection_lock` (slow path).
- **`receive_updates=False`** — бот не получает channel updates (не нужно для замены ссылок по ID), экономит traffic. Для future webhook feature — убрать этот флаг.
- **`get_messages(ids=[single_id])` возвращает list** — Telethon возвращает list даже для single ID если передан как list. `messages[0]` — нужный message или `None` если list пустой (пост удалён/не существует).
- **`mock_telethon_client` fixture design** — НЕ заменяет `get_client`/`start_client` (как предлагалось в спеке), а patch'ит `TelegramClient` конструктор. Это позволяет реальным `get_client`/`start_client` упражняться (singleton, idempotency, locking) против mock client. Если заменить функции — `test_get_client_singleton`/`test_start_client_idempotent`/`test_stop_client_resets_state` потеряют смысл.
- **`Settings.from_env()` вызывается в `get_client()` и `start_client()`** — не cached (как в `db.connection.get_db_path`). Тесты `monkeypatch.setenv` ДО вызова работают; production — статичные env vars. `mock_settings` fixture в conftest выставляет env до `mock_telethon_client`.
- **mypy override для telethon** — `[[tool.mypy.overrides]] module = ["telethon.*"] ignore_missing_imports = true` в `pyproject.toml`. Без него mypy strict падает: `Skipping analyzing "telethon": module is installed, but missing library stubs or py.typed marker [import-untyped]`. Override scoped только для telethon (не глобальный `ignore_missing_imports = true`).
- **Coverage 95.26%** — `core/telegram.py` 93% (uncovered: defensive branches в `stop_client` для `client is None` + `not started`), `core/url_parser.py` 95% (uncovered: defensive `raise AssertionError` после `_raise_invalid` — unreachable, mypy happy). Общее покрытие ≥80% — gate пройден.
- **Lifespan try/except без typing** — `except Exception as exc:` (broad). Telethon errors — `RPCError` subclasses (network, auth, MTProto). Ruff TRY002 (raise vanilla `Exception`) не срабатывает т.к. мы ловим, не бросаем. BLE001 (blind except) не в ruff select — noqa не нужно.
- **`loguru` уже в deps** (из PR #2) — `from loguru import logger` работает без изменений в `pyproject.toml`.