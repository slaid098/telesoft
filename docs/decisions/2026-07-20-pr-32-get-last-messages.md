# ADR — PR #32: get_last_messages via channels.GetMessagesRequest

## Статус

Accepted (2026-07-20) — `get_last_messages(channel_id, limit)` реализован через `channels.GetMessagesRequest` raw API + binary search max_id + range fetch. Spike PR#30 подтвердил алгоритм; этот PR выносит его в production-код `core/telegram.py`. Ограничение PR#14 (by-ID fetch only) снимается — auto-discovery постов канала доступно без user-session и без ручных URLs.

## Контекст

PR#14 (spike #1) установил: Telethon bot mode поддерживает `get_entity`/`send_message`/`edit_message`/`get_messages(ids=[...])` (by-ID), но `iter_messages`/`get_messages(limit=N)` падают с `BotMethodInvalidError` (через `messages.GetHistoryRequest`). Это ограничило MVP: пользователь должен вручную указывать URL поста (`parse_post_url` → message_id), нет auto-discovery "последние N постов канала".

PR#30 (spike #2) подтвердил альтернативу: `channels.GetMessagesRequest` (raw API, namespace `channels.*`) работает для bot-admin. Алгоритм: binary search max_id (~14 probes с верхней границей 10000) + range fetch `GetMessagesRequest(id=list(range(max_id, max_id-N, -1)))` — один вызов = N постов. Spike на тестовом канале (`-1003903711726`): max_id=113 за 13 probes, range fetch 10 постов одним запросом.

Этот PR выносит алгоритм spike в production: `get_last_messages(channel_id, limit=100)` в `core/telegram.py` + настройки `max_probe_id`/`telegram_request_delay` + FloodWaitError handling + 9 тестов. Существующие `get_message`/`edit_message` — БЕЗ изменений (обратная совместимость).

## Решение

`get_last_messages(channel_id, limit)` реализован через 3 private helper'а:

1. **`_get_channel_input(channel_id) -> InputChannel`** — `entity = await client.get_entity(channel_id)`, вернуть `InputChannel(entity.id, entity.access_hash)`. Raw API требует `InputChannel` (id без `-100` prefix + access_hash). `get_entity` работает для ботов (PR#14).

2. **`_fetch_messages_by_ids(channel_input, ids) -> list[Message]`** — `result = await client(ChannelsGetMessagesRequest(channel=channel_input, id=ids))`, фильтр `m is not None and getattr(m, "date", None) is not None` (удаляет `None` для несуществующих/удалённых ID и сообщения без даты). FloodWaitError: try/except, max 3 retries, `await asyncio.sleep(exc.seconds + 1)` между retry, потом re-raise. Возвращает `ChannelMessages.messages` (filtered).

3. **`_find_max_id(channel_input, max_probe_id) -> int`** — binary search: `lo=1, hi=max_probe_id, last_existing=0`, probe `mid=(lo+hi)//2` через `_fetch_messages_by_ids(channel_input, [mid])`, если non-empty → `last_existing=mid, lo=mid+1`, иначе `hi=mid-1`. `await asyncio.sleep(settings.telegram_request_delay)` после каждого probe. Return `last_existing` (0 если все probes пустые).

4. **`get_last_messages(channel_id, limit=100)`** — orchestrator: `_get_channel_input` → `_find_max_id(settings.max_probe_id)` → if 0 return `[]` → `start_id = max(1, max_id - limit + 1)`, `ids = list(range(max_id, start_id - 1, -1))` → `await asyncio.sleep(delay)` → `_fetch_messages_by_ids(channel_input, ids)`. Total requests: ~log2(max_probe_id) + 1 (spike: 13 + 1 = 14 для max_probe_id=10000).

Настройки (`src/telesoft/config.py`):
- `max_probe_id: int = 10000` (env `MAX_PROBE_ID`) — upper bound для binary search. log2(10000)≈13.3 probes.
- `telegram_request_delay: float = 1.0` (env `TELEGRAM_REQUEST_DELAY`) — delay между запросами (flood control).
- Новый helper `_get_float(name, default)` (по аналогии с `_get_int`).

Тесты: 9 новых (`test_get_last_messages_success`, `test_get_last_messages_empty_channel`, `test_get_last_messages_limit_larger_than_max_id`, `test_find_max_id_binary_search`, `test_find_max_id_all_empty`, `test_fetch_messages_by_ids_filters_empty`, `test_flood_wait_retry`, `test_flood_wait_max_retries_exceeded`, `test_delay_between_requests`). `mock_channel_messages` helper в conftest. Все 110 тестов проходят, coverage 93.95%.

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `FloodWaitError(capture=N)` в тестах — `# type: ignore[call-arg]` (capture не в telethon stubs). `e.seconds` вычисляется из message.
- `mock_channel_messages` использует `MagicMock` (не `AsyncMock`) — `ChannelMessages` это plain object, не coroutine.
- `client.return_value = mock_channel_messages([])` в fixture по умолчанию — тесты переопределяют через `side_effect` (для разных probes) или `return_value` (одинаковый ответ).

## Альтернативы

- **`channels.GetMessagesRequest` (raw API) + binary search + range fetch (выбрано)** — работает для bot-admin (PR#30 spike), N постов одним запросом после binary search. ~14 probes + 1 range = 15 запросов независимо от N. Снимает ограничение PR#14 без user-session.

- **User-session (Telethon с phone+code)** — даёт `iter_messages`/`get_messages(limit=N)` напрямую (без binary search), но усложняет auth flow (phone + code, session management, 2FA). ADR PR#14 рекомендовал user-session для истории — этот PR снимает рекомендацию: bot mode + `channels.GetMessagesRequest` достаточен.

- **Range-by-ID через `get_messages(ids=[...])` (N+1)** — high-level Telethon wrapper из PR#14/16 тоже принимает list IDs, но под капотом делает отдельный запрос на каждый ID (N+1 паттерн, медленно для больших N). Raw API `channels.GetMessagesRequest(id=[...])` принимает list и возвращает все за один round-trip.

- **Bot API HTTP `/getUpdates`** — только входящие сообщения боту, не история канала. Bot API HTTP не имеет метода для чтения постов канала по ID. Telethon MTProto даёт доступ к `channels.GetMessagesRequest` — недоступно в Bot API HTTP.

- **Webhook на новые посты (channel updates)** — даёт только новые посты (после подписки), не историю. Не решает "последние N постов" для начального state. Можно комбинировать с этим PR: webhook для incremental, `get_last_messages` для initial load.

- **Dynamic probe upper bound (первая probe 1000000)** — для каналов с >10000 постов. Усложняет код, для MVP фиксированный 10000 достаточен (spike: max_id=113 на тестовом канале). Можно увеличить через env `MAX_PROBE_ID` без переделки алгоритма. Dynamic probe — Pending для будущего PR если понадобится.

- **Infinite retry на FloodWaitError (как в spike PR#30)** — spike делал infinite retry через `_retry_on_flood`. Production требует bounded retries (max 3) чтобы не зависеть надолго — если Telegram выдаёт repeated FloodWait, лучше fail fast и дать caller'у решить (retry/log/abort). Спека issue #31 явно требует max 3.