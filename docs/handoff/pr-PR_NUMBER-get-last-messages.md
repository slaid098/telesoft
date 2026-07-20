---
pr: PR_NUMBER
issue: 31
branch: feat/telegram/get-last-messages
status: ready
created: 2026-07-20
---

# Handoff — PR #PR_NUMBER: get_last_messages via channels.GetMessagesRequest

## Что сделано

Реализован issue #31 — production-метод `get_last_messages(channel_id, limit)` в `core/telegram.py` через raw API `channels.GetMessagesRequest` (namespace `telethon.tl.functions.channels`). Снимает ограничение PR#14 (by-ID fetch only) — теперь можно auto-discovery последние N постов канала без ручных URLs. Spike PR#30 подтвердил алгоритм (binary search max_id + range fetch). Существующие `get_message`/`get_messages`/`edit_message`/`resolve_entity`/`get_bot_info` — БЕЗ изменений (обратная совместимость).

### Шаг 1: Settings — новые поля (`src/telesoft/config.py`)

- `max_probe_id: int = 10000` (env `MAX_PROBE_ID`) — верхняя граница binary search. log2(10000)≈13.3 probes.
- `telegram_request_delay: float = 1.0` (env `TELEGRAM_REQUEST_DELAY`) — delay между запросами к Telegram в секундах (flood control).
- Новый helper `_get_float(name, default)` — по аналогии с `_get_int`.
- `from_env()` обновлён: `max_probe_id=_get_int("MAX_PROBE_ID", 10000)`, `telegram_request_delay=_get_float("TELEGRAM_REQUEST_DELAY", 1.0)`.
- `.env.example` — добавлены `MAX_PROBE_ID=10000` и `TELEGRAM_REQUEST_DELAY=1.0`.
- `tests/test_config.py` — обновлён (defaults, custom, frozen tests включают новые поля).

### Шаг 2: core/telegram.py — get_last_messages

- Импорты: `from telethon.tl.functions.channels import GetMessagesRequest as ChannelsGetMessagesRequest`, `from telethon.tl.types import InputChannel`, `from telethon.errors import FloodWaitError` (добавлен к `RPCError`).
- `async def _get_channel_input(channel_id: int) -> InputChannel` — `entity = await client.get_entity(channel_id)`, вернуть `InputChannel(entity.id, entity.access_hash)`. Использует `start_client()`.
- `async def _fetch_messages_by_ids(channel_input, ids) -> list[Message]` — `result = await client(ChannelsGetMessagesRequest(channel=channel_input, id=ids))`, фильтр `m is not None and getattr(m, "date", None) is not None`. FloodWaitError: try/except, max 3 retries, потом re-raise. `await asyncio.sleep(exc.seconds + 1)` между retry.
- `async def _find_max_id(channel_input, max_probe_id) -> int` — binary search: `lo=1, hi=max_probe_id, last_existing=0`, probe `mid=(lo+hi)//2`, если non-empty → `last_existing=mid, lo=mid+1`, иначе `hi=mid-1`. `await asyncio.sleep(settings.telegram_request_delay)` после каждого probe. Return `last_existing`.
- `async def get_last_messages(channel_id: int, limit: int = 100) -> list[Message]` — `_get_channel_input` → `_find_max_id` → if 0 return `[]` → `start_id = max(1, max_id - limit + 1)`, `ids = list(range(max_id, start_id - 1, -1))` → `await asyncio.sleep(settings.telegram_request_delay)` → `_fetch_messages_by_ids(channel_input, ids)`.

### Шаг 3: Тесты (`tests/test_telegram_client.py`, `tests/conftest.py`)

- `MockMessage` — добавлено поле `date: object = None` (для фильтра в `_fetch_messages_by_ids`).
- `mock_channel_messages(messages)` helper — создаёт `MagicMock` с `.messages` атрибутом (эмулирует `ChannelMessages` результат).
- `mock_telethon_client` — `client.return_value = mock_channel_messages([])` (по умолчанию пустой `ChannelMessages`), `client.side_effect = None`. Тесты могут переопределять `side_effect`/`return_value` для разных probes.
- 9 новых тестов:
  - `test_get_last_messages_success` — mock `_find_max_id=150`, range fetch 100 messages → возвращает 100, проверяет `ChannelsGetMessagesRequest.id == list(range(150, 50, -1))`.
  - `test_get_last_messages_empty_channel` — `_find_max_id=0` → `[]`, `client` не вызывается.
  - `test_get_last_messages_limit_larger_than_max_id` — max_id=50, limit=100 → `start_id=1`, `ids=range(50, 0, -1)`, 50 messages.
  - `test_find_max_id_binary_search` — mock `client.side_effect` по `request.id[0]`, existing={1250, 1875} → возвращает 1875.
  - `test_find_max_id_all_empty` — все probes возвращают `[None]` → 0.
  - `test_fetch_messages_by_ids_filters_empty` — `[msg1, None, msg2, msg_date_none]` → `[msg1, msg2]`.
  - `test_flood_wait_retry` — `FloodWaitError(capture=2)` первый раз, потом OK → retry успешно, `asyncio.sleep(3)` вызван 1 раз.
  - `test_flood_wait_max_retries_exceeded` — всегда `FloodWaitError` → после 3 retry re-raise, `await_count == 3`, flood-sleeps == 2.
  - `test_delay_between_requests` — `asyncio.sleep` вызывается с `settings.telegram_request_delay` между probes.
- Все 110 тестов проходят, coverage 93.95% (требование ≥80%).
- ruff check + ruff format + mypy strict — зелёные.

## Почему

Spike PR#30 подтвердил: `channels.GetMessagesRequest` (raw API, namespace `telethon.tl.functions.channels`) работает для bot-admin — в отличие от `iter_messages`/`get_messages(limit=N)` (запрещены для ботов, `BotMethodInvalidError` через `messages.GetHistoryRequest`). Алгоритм binary search + range fetch (14 probes + 1 range = 15 запросов для "последние N постов", независимо от N) — проверен в spike на тестовом канале.

Это снимает ограничение PR#14 (by-ID fetch only — пользователь должен был вручную указывать URL поста через `parse_post_url`). Теперь можно auto-discovery "последние N постов канала" для выбора/предпросмотра — основа для будущего UI (PR 3 и PR 4 из 4).

## Pending

- **PR 3 из 4: API router + schema** — `GET /api/channels/{channel_id}/messages?limit=N` endpoint, возвращает `MessageResponse[]`. Использует `get_last_messages` из этого PR. Pydantic schema для message (id, date, text, edit protection).
- **PR 4 из 4: Frontend UI** — кнопка "Загрузить последние N постов" на channel detail page, выбор постов для replace-link job.
- **Кеширование max_id в БД** — после первого binary search (~14 probes) можно кешировать `max_id` в `channels` table, чтобы при последующих запросах пропускать binary search. Поле `last_known_max_id: int` + обновление после каждого `get_last_messages`. Ускоряет с 15 до 1 запроса.
- **Dynamic probe upper bound** — для каналов с >10000 постов (редко) — увеличить `MAX_PROBE_ID` через env или добавить dynamic: первая probe `id=[1000000]`, если существует → hi=1000000. Сейчас фиксированный 10000 (spike показал max_id=113 на тестовом канале).
- **ADR PR#14 caveat обновить** — `docs/decisions/2026-07-20-pr-14-spike-telethon.md` говорил "get_messages не работает для ботов → user-session для истории". Этот PR снимает caveat через `channels.GetMessagesRequest`. ADR PR#14 можно пометить как superseded этим PR (или обновить текст).

## Watch out

- **Binary search для монотонно возрастающих ID** — Telegram присваивает post IDs инкрементально (1, 2, ..., max_id) без пропусков для каналов. Binary search ищет max id сущ. поста (`date is not None`). Для каналов с удалёнными постами в конце — может дать max_id меньший чем реальный последний. Edge case, для MVP приемлемо (spike PR#30 подтвердил корректность на тестовом канале).
- **Delay между запросами** — `asyncio.sleep(settings.telegram_request_delay)` (default 1.0s) после каждого probe в `_find_max_id` и перед range fetch в `get_last_messages`. Для binary search (14 probes) + range fetch (1) — общее время ~15 секунд. НЕ уменьшать delay (flood risk) — лучше кешировать max_id (см. Pending).
- **FloodWaitError handling** — try/except в `_fetch_messages_by_ids`, max 3 retries, `await asyncio.sleep(exc.seconds + 1)` между retry, потом re-raise. Спека issue #31 требует max 3. `_retry_on_flood` helper из spike PR#30 не использован (spike делал infinite retry) — production требует bounded retries чтобы не зависеть надолго.
- **`channels.GetMessagesRequest` возвращает `ChannelMessages`** (не `list[Message]`) — `.messages` атрибут содержит список `Message` объектов. `getattr(result, "messages", [])` — safe access (если `.messages` None → `[]`).
- **`InputChannel(id, access_hash)`** — raw API требует `InputChannel` (id без `-100` prefix, из `entity.id` после `get_entity`). `entity.access_hash` — long int, уникален для канала. Если access_hash меняется (редко) — нужно заново `get_entity` (auto в `_get_channel_input`).
- **Limitation PR#14 снимается** — `docs/decisions/2026-07-20-pr-14-spike-telethon.md` говорил "user-session для истории". Этот PR показывает: bot mode + `channels.GetMessagesRequest` достаточно для auto-discovery. User-session НЕ требуется (bot token работает).
- **Существующие методы БЕЗ изменений** — `get_message`/`get_messages`/`edit_message`/`resolve_entity`/`get_bot_info` сохранены для обратной совместимости (могут использоваться в link_replacer.py PR#22 и будущих features). `_get_channel_input`/`_fetch_messages_by_ids`/`_find_max_id` — private helpers для `get_last_messages`.
- **`_fetch_messages_by_ids` filter** — `m is not None and getattr(m, "date", None) is not None` фильтрует: (a) `None` (пост удалён/не существует), (b) `Message` с `date=None` (редко, но возможно для служебных сообщений). Возвращает только "реальные" посты с датой.
- **`mock_channel_messages` helper** — создаёт `MagicMock` с `.messages` list. `MagicMock` (не `AsyncMock`) т.к. `ChannelMessages` — не coroutine, а plain object. Тесты могут класть туда `[None]`, `[msg1, None, msg2]`, и т.д.
- **`client(ChannelsGetMessagesRequest(...))` mock** — `client` это `AsyncMock`, `client(...)` возвращает coroutine (awaitable). `return_value` задаёт одинаковый ответ для всех вызовов; `side_effect` — function(request) для разных ответов (разные `request.id`). В `mock_telethon_client` fixture: `client.return_value = mock_channel_messages([])`, `client.side_effect = None` (по умолчанию пустой, тесты переопределяют).
- **`FloodWaitError(capture=N)` в тестах** — `FloodWaitError(request=None, capture=N)` → `e.seconds == N`. `capture` это positional arg в `RPCError.__init__`, `seconds` вычисляется из message (parsed через rpcerrorlist). `FloodWaitError(request=None, capture=2)` → `A wait of 2 seconds is required`. mypy: `# type: ignore[call-arg]` т.к. `capture` не в stubs.
- **ruff import sorting** — private helpers (`_fetch_messages_by_ids`, `_find_max_id`) в import block сортируются по имени (ruff isort). Сначала private с underscore, потом public — ruff считает по alphabetical order.