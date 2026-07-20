# ADR — PR #16: bot-mode Telethon client wrapper

## Статус

Accepted (2026-07-20) — реализован production wrapper для замены ссылок в постах каналов через бота-админа. Строго by-ID fetch (без history iteration), file session для переиспользования, lifespan интеграция с graceful degradation.

## Контекст

Spike PR#14 (ADR `docs/decisions/2026-07-20-pr-14-spike-telethon.md`, Accepted) подтвердил:
- Telethon bot-mode может `edit_message` посты канала где бот — админ (главная цель — снята).
- `get_messages(limit=...)` / `iter_messages` (history iteration) НЕ работает для ботов — `BotMethodInvalidError: ...caused by GetHistoryRequest` (MTProto запрещает bot-аккаунтам читать историю).
- by-ID fetch (`get_messages(chat_id, ids=[...])`) — это другой MTProto method, разрешён ботам (spike не тестировал его явно, но это документированный path в digital_factory референсе `src/shared/services/portfolio/telegram/client.py:80-89`).

Для production MVP (telesoft) нужен был Telegram client wrapper с:
1. Singleton client с file session (переиспользование между запусками, не повторный логин).
2. by-ID fetch — НЕ history iteration (критическое ограничение bot mode).
3. Idempotent start с concurrent guard (asyncio.Lock, паттерн digital_factory).
4. Lifespan интеграция в FastAPI — падение Telegram НЕ должно ронять app (логируется, продолжается).
5. Методы: `get_client`/`start_client`/`stop_client`/`get_message`/`get_messages`/`edit_message`/`resolve_entity`/`get_bot_info`.

Архитектура telesoft: юзер в UI даёт **список post URLs** (напр. `https://t.me/channel/123`, `https://t.me/c/1234567890/456`) → backend парсит `(channel, message_id)` из URL → fetch'ит текст поста через `get_messages(ids=...)` → regex-замена old_pattern на new_link → `edit_message`. Никакой итерации истории канала.

Референс паттерна: `/root/workspace/digital_factory/src/shared/services/portfolio/telegram/client.py:80-89` — `TelegramBot` class с `_connection_lock`, `start()` (double-checked locking), `get_one_message(chat_id, message_id)` / `get_messages(chat_id, message_ids)` (by-ID fetch, фильтр None). digital_factory использует `MemorySession` — для telesoft выбрана file session (`settings.session_path`).

## Решение

### Bot mode + by-ID fetch

- `TelegramClient(settings.session_path, api_id, api_hash, receive_updates=False)` + `await client.start(bot_token=settings.telegram_bot_token)` — bot mode. Token передаётся в `start()`, НЕ в конструктор (TelegramClient не принимает его в `__init__`).
- File session (`app_data/bot.session`) — переиспользование между запусками без повторного логина. `MemorySession` теряется при restart — не подходит для production.
- `get_messages(chat_id, ids=[message_id])` — by-ID fetch, разрешён ботам. `iter_messages`/`get_messages(limit=...)` — запрещены (`BotMethodInvalidError`), НЕ используются.
- `edit_message(chat_id, message_id, text=...)` — propagates `RPCError` (не глотает ошибки — caller решает, что делать: retry/log/abort).

### Singleton + concurrent guard

- `_State` dataclass (`client: TelegramClient | None`, `started: bool`) — holder, не global re-assignment (ruff PLW0603 запрещает module-level re-assignment).
- `_connection_lock = asyncio.Lock()` — double-checked locking в `start_client()`: fast path (проверка `started` до lock), slow path (повторная проверка внутри `async with _connection_lock`). Защита от concurrent start (два вызова могут оба увидеть `started = False` без lock → оба вызвать `client.start()` → race/error).
- `get_client()` — lazy singleton: создаёт `TelegramClient` при первом вызове, возвращает тот же инстанс при последующих.

### Lifespan graceful degradation

- Startup: `await init_db()` → если `settings.telegram_bot_token` задан — `await start_client()` в try/except. Падение Telegram (network, invalid token, MTProto error) логируется через `loguru.logger.warning`, app продолжает работу (DB available, endpoint'ы для замены ссылок вернут 503 при вызове — но health endpoint работает).
- Shutdown: `await stop_client()` в try/except → `await close_db()`. Если disconnect падает — логируется, DB всё равно закрывается.
- Если `TELEGRAM_BOT_TOKEN` пуст — Telegram skip без warning (дефолт `""` в `Settings.from_env()`, для local dev без Telegram).

### URL parser

- `parse_post_url(url) -> tuple[str | int, int]` — regex `^https?://t\.me/(c/)?(\w+)/(\d+)`:
  - Public: `https://t.me/mychannel/123` → `("mychannel", 123)` (username без @, передаётся в `resolve_entity("@mychannel")` или `get_messages`).
  - Private: `https://t.me/c/1234567890/456` → `(-1001234567890, 456)` (`internal_id` → `-100<internal_id>` через `int(f"-100{channel_part}")` — MTProto convention для private channels).
  - `?comment=...` query игнорируется (regex не требует конца строки `^...$`).
- `parse_post_urls(urls)` — batch, `ValueError` с указанием `index N` для плохого URL (caller может показать пользователю какой URL невалидный).
- `is_valid_post_url(url)` — bool для form validation.

### Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out")

1. **`TelethonError` НЕ существует** — спецификация issue #15 упоминала `except TelethonError`, но в `telethon.errors` нет такого класса. Базовый — `RPCError` (`telethon.errors.rpcbaseerrors`). Использован `RPCError` в `stop_client` catch + `BadRequestError(request=None, message="...")` в тесте.
2. **`mock_telethon_client` fixture design** — спека предлагала monkeypatch `get_client`/`start_client`. Реализовано через patch `TelegramClient` конструктора — позволяет реальным `get_client`/`start_client` упражняться (singleton, idempotency, locking) против mock client. Иначе `test_get_client_singleton`/`test_start_client_idempotent`/`test_stop_client_resets_state` потеряли бы смысл.
3. **`MemorySession` не используется** — спека явно говорит "НЕ MemorySession, переиспользование между запусками". File session `settings.session_path` (digital_factory референс использовал MemorySession — отклонение от референса, по спеке).
4. **mypy override для telethon** — `[[tool.mypy.overrides]] module = ["telethon.*"] ignore_missing_imports = true` в `pyproject.toml`. telethon не имеет `py.typed` — mypy strict падает с `import-untyped`. Scoped override (не глобальный).

## Альтернативы

### Bot mode vs user session

Выбран **bot mode** (`TELEGRAM_BOT_TOKEN`, не требует phone+code auth). Альтернатива — **user session** (Telethon с phone+code, отдельный user-аккаунт):
- Pro: `get_messages`/`iter_messages` работают (history iteration разрешён для user-аккаунтов) — можно автоматически искать посты по pattern.
- Con: усложняет auth flow (phone + code, может требовать 2FA, session management сложнее), требует user-аккаунт (не bot), может нарушать ToS для автоматизации.
- Решение: bot mode + by-ID fetch (пользователь указывает post URL вручную) — проще для MVP, auth через bot token (один env var). User session — если понадобится автоматический поиск постов (future issue).

### Raw Bot API HTTP vs Telethon

Выбран **Telethon** (MTProto, Pythonic API). Альтернатива — raw HTTP-запросы к `https://api.telegram.org/bot<token>/...` (Bot API HTTP):
- Pro: проще deploy (нет MTProto dependency, меньше пакетов), REST проще для debugging.
- Con: нет `get_entity` для валидации канала (нужен отдельный `/getChat`), нет `get_messages(ids=...)` (только `/getUpdates` для входящих, не для history — даже Bot API HTTP не даёт history канала для ботов), editMessageText требует `chat_id`+`message_id` (но нет fetch поста по ID).
- Решение: Telethon — единый client API с `get_messages(ids=...)` (by-ID fetch разрешён ботам через MTProto, но НЕ через Bot API HTTP `/getMessage` который не существует). Для замены ссылок (fetch → edit) нужен fetch — Telethon даёт его, Bot API HTTP — нет.

### Bot API HTTP для edit only (без fetch)

Гибрид: Telethon для `get_messages(ids=...)` (fetch) + Bot API HTTP для `editMessageText` (edit). Альтернатива — Telethon для обоих.
- Pro: edit через REST проще debugging, нет MTProto для write path.
- Con: два client (MTProto + HTTP), два auth mechanism (bot token для обоих, но разные API), расхождение в error handling.
- Решение: Telethon для обоих — единый client, единый auth, единый error handling (`RPCError`).

### `MemorySession` vs file session

Выбрана **file session** (`settings.session_path`). Альтернатива — `MemorySession` (как в digital_factory референсе):
- Pro MemorySession: нет файла на диске (clean, no FS dependency), проще для tests.
- Con: теряется при restart → повторный логин каждый запуск (для bot — не критично, bot token не требует подтверждения, но лишний MTProto handshake + rate limits).
- Решение: file session — переиспользование между запусками (explicit requirement в спеке), `app_data/bot.session` в `.gitignore` (не коммитится).

### `@dataclass _State` vs `global` vs class

Выбран `@dataclass _State` (`client`, `started` поля). Альтернативы:
- `global client, started` — ruff PLW0603 запрещает module-level re-assignment.
- `class TelegramClientWrapper` (как digital_factory `TelegramBot`) — больше boilerplate, но OOP. telesoft использует functional API (`get_client()`/`start_client()`/etc) для консистентности с `db.connection` (тоже functional, не class).
- Решение: `@dataclass _State` + module-level functions — паттерн из PR#12 (`db.connection._State`), консистентно.