# ADR — PR #<PR-NUMBER>: Spike v2 — channels.GetMessagesRequest raw API for bot-admin

## Статус

Accepted (2026-07-20) — spike прошёл: `channels.GetMessagesRequest` (raw API, namespace `channels.*`) работает для bot-admin, binary search находит max_id за O(log N) probes, range fetch одним запросом возвращает N постов. Критическое ограничение PR#14 (`get_messages` не работает для ботов) обходится без user-session. Можно реализовывать `get_last_messages(channel_id, limit)` в refactor PR 2 из 4.

## Контекст

PR#14 (spike #1) подтвердил: Telethon bot mode поддерживает `connect`/`get_entity`/`send_message`/`edit_message` для бота-админа на канале. НО `iter_messages`/`get_messages(limit=N)` падают с `BotMethodInvalidError: ...caused by GetHistoryRequest` — MTProto запрещает bot-аккаунтам читать историю через `messages.GetHistoryRequest`. Это ограничило MVP: пользователь должен вручную указывать URL поста (`parse_post_url` → message_id), нет auto-discovery "последние N постов канала".

Архитектурные варианты из ADR PR#14:
1. **message_id в БД** (выбрано для MVP в PR#14) — ручной ввод, нет auto-discovery.
2. **user session** — Telethon с phone+code (не бот), у него `get_messages` работает. Усложняет auth flow.
3. **Bot API HTTP `/getUpdates`** — только входящие сообщения боту, не история канала.
4. **Webhook на новые посты** — channel updates, не даёт историю.

Inline spike (через `python -c` heredoc, 2026-07-20) экспериментально проверил **другой raw API метод** — `channels.GetMessagesRequest` (namespace `channels.*`, не `messages.*`). Предварительные результаты: метод принимает `id=[...]` (точные ID) и работает для bot-admin. Этот PR фиксирует результаты в standalone скрипте `scripts/spike_telethon_v2.py` + ADR, чтобы refactor `core/telegram.py` (PR 2 из 4) мог использовать raw API для auto-discovery.

Тестовый канал: `-1003903711726` ("Тест portfolio"), бот `@server10bot` (id `6164770162`) — админ с правом редактирования постов. Креды в окружении: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`.

## Решение

Spike v2 выполнен через standalone async скрипт `scripts/spike_telethon_v2.py` (НЕ часть `src/telesoft/`, читает env через `os.environ` напрямую). 5 тестов:

1. **TEST 1: channels.GetMessagesRequest id=[1,2,3]** — ✅ PASS. `client(GetMessagesRequest(channel=InputChannel(ch_id, ah), id=[1,2,3]))` → `ChannelMessages` с 3 posts (id=1,2,3), `date` и `message` заполнены. **Метод работает для bot-admin.** Это raw API (не high-level wrapper), namespace `telethon.tl.functions.channels`, принимает `InputChannel` (id без `-100` prefix + access_hash из `get_entity`).

2. **TEST 2: Binary search max_id (upper=10000)** — ✅ PASS. Алгоритм: `lo=1, hi=10000`, probe `mid=(lo+hi)//2`, если `messages[0].date is not None` → post существует (`lo=mid+1`, запомнить `last_existing_id=mid`), иначе `hi=mid-1`. **13 probes** → `max_id=113` (log2(10000)≈13.3 — точно как ожидалось). Каждый probe — один `GetMessagesRequest(id=[mid])` с `asyncio.sleep(1.0)` между ними (flood control, общее время ~13 секунд).

3. **TEST 3: Range fetch последних 10 постов** — ✅ PASS. `GetMessagesRequest(id=list(range(113, 103, -1)))` → **ОДИН запрос** вернул 10 posts (id 104-113, все non-None). Это ключевое преимущество: N постов одним запросом, не N запросов (как при by-ID fetch из PR#14). Total requests для "последние N постов": ~14 (binary search) + 1 (range fetch) = 15, независимо от N.

4. **TEST 4 (контроль, expected FAIL): messages.GetHistoryRequest** — ✅ PASS (expected fail). `GetHistoryRequest(peer=InputPeerChannel(ch_id, ah), offset_id=0, offset_date=None, add_offset=0, limit=5, max_id=0, min_id=0, hash=0)` → `BotMethodInvalidError: ...caused by GetHistoryRequest`. Подтверждает ограничение PR#14: `messages.*` namespace запрещён для ботов.

5. **TEST 5 (контроль, expected FAIL): client.iter_messages** — ✅ PASS (expected fail). `async for msg in client.iter_messages(entity, limit=5)` → `BotMethodInvalidError: ...caused by GetHistoryRequest`. Telethon `iter_messages` под капотом использует `GetHistoryRequest` → та же ошибка.

**Итог:** spike прошёл. `channels.GetMessagesRequest` работает для bot-admin. `get_last_messages(channel_id, limit)` можно реализовать как:
1. `entity = await client.get_entity(channel_id)` → `Channel` (id, access_hash).
2. Binary search `max_id` через `channels.GetMessagesRequest(id=[mid])` (≤14 probes для upper=10000).
3. Range fetch: `id=list(range(max_id, max_id-limit, -1))` → N постов одним запросом.
4. Delay 1.0s между запросами (flood control), catch `FloodWaitError` → `await asyncio.sleep(e.seconds + 1)` → retry.

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `MAX_PROBE_ID=10000` хватило для тестового канала (max_id=113). Для каналов с >10000 постов — нужно увеличивать или динамически (первая probe `id=[1000000]`).
- Ruff per-file-ignore для `scripts/*` добавлен (`TRY300`新增ился — return inside try в тест-функциях; PR#14 не требовал per-file-ignore).
- `FloodWaitError` handling реализован через `_retry_on_flood(coro_factory, label)` helper, но не сработал в spike (все probes прошли без flood).

## Альтернативы

- **`channels.GetMessagesRequest` (raw API) vs `messages.GetMessages` (high-level)**: выбран `channels.GetMessagesRequest` (namespace `channels.*`) — работает для bot-admin. Альтернатива — `messages.GetMessages` (namespace `messages.*`, используется в `get_messages(ids=[...])` из PR#14/16) — тоже работает для ботов (by-ID fetch), но это высокоуровневая обёртка, не даёт `ChannelMessages` структуру. Для auto-discovery (binary search + range fetch) raw API предпочтительнее — меньше overhead, прямой контроль над запросом.

- **User-session (Telethon с phone+code) vs bot mode + `channels.GetMessagesRequest`**: выбран bot mode (есть `TELEGRAM_BOT_TOKEN`, не требует phone+code auth). Альтернатива — user session — даёт `iter_messages`/`get_messages(limit=N)` напрямую (без binary search), но усложняет auth flow (phone + code, session management, 2FA). Для MVP с bot token — `channels.GetMessagesRequest` достаточен и не требует user-аккаунта. ADR PR#14 рекомендовал user-session для истории — этот spike снимает эту рекомендацию.

- **Range-by-ID через `get_messages(ids=[...])` (N+1) vs `channels.GetMessagesRequest` range fetch (1 запрос)**: выбран `channels.GetMessagesRequest` range fetch — N постов одним запросом. Альтернатива — `get_messages(chat_id, ids=[id1, id2, ...])` (high-level, PR#14/16) — тоже может принимать list IDs, но под капотом делает отдельный запрос на каждый ID (N+1 паттерн, медленно для больших N). Raw API `channels.GetMessagesRequest(id=[...])` принимает list и возвращает все за один round-trip.

- **Bot API HTTP getChat/getUpdates vs Telethon MTProto**: выбран Telethon (MTProto даёт `channels.GetMessagesRequest` — недоступно в Bot API HTTP). Альтернатива — raw HTTP к `https://api.telegram.org/bot<token>/getChat` — не даёт посты канала (только metadata). `/getUpdates` — только входящие сообщения боту, не история канала. Bot API HTTP не подходит для auto-discovery постов.

- **Binary search upper bound (10000) vs dynamic (первая probe 1000000)**: выбран фиксированный `MAX_PROBE_ID=10000` (хватает для тестового канала, max_id=113). Альтернатива — dynamic: первая probe `id=[1000000]`, если существует → hi=1000000, иначе hi=1000000/2. Усложняет код, для MVP фиксированный 10000 достаточен (можно увеличить в config без переделки алгоритма). Для каналов с >10000 постов — увеличить `MAX_PROBE_ID` или добавить dynamic probe в PR 2.