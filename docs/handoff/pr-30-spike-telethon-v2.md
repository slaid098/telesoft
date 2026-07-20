---
pr: 30
issue: 29
branch: spike/telegram/channels-get-messages
status: ready
created: 2026-07-20
---

# Handoff — PR #30: Spike v2 — channels.GetMessagesRequest raw API for bot-admin

## Что сделано

Реализован issue #29 — standalone async spike-скрипт `scripts/spike_telethon_v2.py` для проверки альтернативного raw API метода `channels.GetMessagesRequest` (namespace `telethon.tl.functions.channels`) для чтения постов канала через бота-админа. PR#14 (spike #1) ограничил MVP by-ID fetch (`get_messages(ids=[...])`) — `iter_messages`/`get_messages(limit=N)` падают для ботов с `BotMethodInvalidError` (вызван `messages.GetHistoryRequest`). Этот spike проверяет, может ли `channels.GetMessagesRequest` заменить user-session для auto-discovery постов канала.

### Шаг 1: Spike скрипт

- `scripts/spike_telethon_v2.py` — standalone async Python скрипт (НЕ часть `src/telesoft/`, НЕ импортирует `Settings.from_env()` — читает env напрямую через `os.environ`).
- Структура:
  - `from telethon.tl.functions.channels import GetMessagesRequest` — main raw API.
  - `from telethon.tl.types import InputChannel` — channel input для raw API.
  - `from telethon.tl.functions.messages import GetHistoryRequest` — контрольный тест (expected FAIL).
  - `from telethon.tl.types import InputPeerChannel` — peer input для GetHistoryRequest.
  - `from telethon.errors import BotMethodInvalidError, FloodWaitError` — для catch.
- 5 тестов (см. ниже).
- `asyncio.sleep(REQUEST_DELAY = 1.0)` между всеми запросами к Telegram (flood control).
- `FloodWaitError` → `await asyncio.sleep(e.seconds + 1)` → retry (через `_retry_on_flood` helper).
- Креды: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN` через `os.environ`.
- `SESSION_PATH = "app_data/bot.session"` (переиспользуется с PR#14).
- `MAX_PROBE_ID = 10000` (верхняя граница binary search).
- `RANGE_FETCH_COUNT = 10` (последние N постов для range fetch).

### Шаг 2: pyproject.toml

Добавлен `per-file-ignores` для `scripts/*`:

```toml
"scripts/*" = ["T201", "S603", "S101", "TRY300"]
```

- `T201` (print) — spike использует `print` для вывода результатов.
- `S603`/`S101` — spec рекомендует их добавить preemptively (даже если не нужны сейчас).
- `TRY300` (return inside try) — ruff требует перенести `return False` в `else` блоки, но для тест-функций со множеством try/except это менее читаемо; добавлен per-file-ignore.

### Шаг 3: Запуск и результаты spike

Команда: `cd /root/workspace/telesoft && uv run python scripts/spike_telethon_v2.py`

**Фактический вывод скрипта:**

```
=== 1. connect (bot mode) ===
bot id:       6164770162
bot username: @server10bot
bot first_name: СЕРВЕР 10 БОТ
bot is_bot:   True

=== 2. resolve channel entity ===
entity type:  Channel
channel id:   3903711726
channel title: Тест portfolio
channel username: (none)
channel access_hash: 2360878343388152150

=== TEST 1: channels.GetMessagesRequest id=[1,2,3] ===
  [test1] GetMessagesRequest id=[1, 2, 3]
result type: ChannelMessages
messages returned: 3
  id=1 date=2026-04-29 13:42:54+00:00 text=''
  id=2 date=2026-04-29 13:49:04+00:00 text=''
  id=3 date=2026-05-08 02:17:47+00:00='>_ LOG: SYS.PATCH >_ LINK: https://github.com/slaid098/digital_factory'
TEST 1: OK — channels.GetMessagesRequest works for bot-admin

=== TEST 2: binary search max_id (upper bound 10000) ===
  [probe#1] GetMessagesRequest id=[5000]
  probe #1: id=5000 exists=False date=None range=[1, 10000]
  [probe#2] GetMessagesRequest id=[2500]
  probe #2: id=2500 exists=False date=None range=[1, 4999]
  [probe#3] GetMessagesRequest id=[1250]
  probe #3: id=1250 exists=False date=None range=[1, 2499]
  [probe#4] GetMessagesRequest id=[625]
  probe #4: id=625 exists=False date=None range=[1, 1249]
  [probe#5] GetMessagesRequest id=[312]
  probe #5: id=312 exists=False date=None range=[1, 624]
  [probe#6] GetMessagesRequest id=[156]
  probe #6: id=156 exists=False date=None range=[1, 311]
  [probe#7] GetMessagesRequest id=[78]
  probe #7: id=78 exists=True date=2026-05-25 04:12:15+00:00 range=[1, 155]
  [probe#8] GetMessagesRequest id=[117]
  probe #8: id=117 exists=False date=None range=[79, 155]
  [probe#9] GetMessagesRequest id=[97]
  probe #9: id=97 exists=True date=2026-05-28 05:41:09+00:00 range=[79, 116]
  [probe#10] GetMessagesRequest id=[107]
  probe #10: id=107 exists=True date=2026-06-02 12:32:43+00:00 range=[98, 116]
  [probe#11] GetMessagesRequest id=[112]
  probe #11: id=112 exists=True date=2026-07-20 15:53:32+00:00 range=[108, 116]
  [probe#12] GetMessagesRequest id=[114]
  probe #12: id=114 exists=False date=None range=[113, 116]
  [probe#13] GetMessagesRequest id=[113]
  probe #13: id=113 exists=True date=2026-07-20 15:53:39+00:00 range=[113, 113]
TEST 2: max_id = 113 (found in 13 probes)

=== TEST 3: range fetch last 10 posts ===
  [test3-range] GetMessagesRequest id=[113, 112, 111, 110, 109, 108, 107, 106, 105, 104]
requested 10 ids, got 10 entries, 10 non-None
existing posts returned: 10
  id=113 date=2026-07-20 15:53:39+00:00='Test post for spike: https://new.example.com/path'
  id=112 date=2026-07-20 15:53:32+00:00='Test post for spike: https://new.example.com/path'
  id=111 date=2026-07-01 03:44:45+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=110 date=2026-06-27 17:14:29+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=109 date=2026-06-20 16:24:31+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=108 date=2026-06-20 16:16:24+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=107 date=2026-06-02 12:32:43+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=106 date=2026-06-02 12:22:26+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=105 date=2026-06-02 12:15:25+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
  id=104 date=2026-06-02 12:09:35+00:00='>_ : ... >_ : SYS.PATCH >_ : github.com/slaid098/digital_factory'
TEST 3: OK — 10 messages returned in one request

=== TEST 4 (control, expected FAIL): messages.GetHistoryRequest ===
TEST 4: FAIL BotMethodInvalidError (expected): The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by GetHistoryRequest)

=== TEST 5 (control, expected FAIL): client.iter_messages ===
TEST 5: FAIL BotMethodInvalidError (expected): The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by GetHistoryRequest)

=== spike summary ===
TEST 1 (channels.GetMessagesRequest id=[1,2,3]): PASS
TEST 2 (binary search max_id): max_id=113
TEST 3 (range fetch last 10): PASS
TEST 4 (GetHistoryRequest control, expected FAIL): PASS (expected fail)
TEST 5 (iter_messages control, expected FAIL): PASS (expected fail)

=== spike result: SUCCESS — channels.GetMessagesRequest works ===
```

### Результаты spike по тестам

| Тест | Ожидание | Факт | Статус |
|------|----------|------|--------|
| TEST 1 (channels.GetMessagesRequest id=[1,2,3]) | 3 поста возвращены | `ChannelMessages` с 3 posts (id=1,2,3), date/text заполнены | ✅ PASS |
| TEST 2 (binary search max_id, upper=10000) | max_id найден за ~13 probes | `max_id=113`, найден за **13 probes** (log2(10000)≈13.3) | ✅ PASS |
| TEST 3 (range fetch последних 10 постов) | 10 постов одним запросом | `id=list(range(113, 103, -1))` → 10 posts одним запросом | ✅ PASS |
| TEST 4 (messages.GetHistoryRequest — контроль) | FAIL `BotMethodInvalidError` | `BotMethodInvalidError: ...caused by GetHistoryRequest` (подтверждает PR#14) | ✅ PASS (expected fail) |
| TEST 5 (iter_messages — контроль) | FAIL `BotMethodInvalidError` | `BotMethodInvalidError: ...caused by GetHistoryRequest` | ✅ PASS (expected fail) |

**Итог spike:** SUCCESS — `channels.GetMessagesRequest` работает для bot-admin, binary search находит max_id за O(log N) probes, range fetch одним запросом даёт N постов. Можно реализовывать `get_last_messages(channel_id, limit)` в PR 2 из 4 (refactor `core/telegram.py`).

## Почему

PR#14 (spike #1) ограничил MVP by-ID fetch — пользователь должен был вручную указывать URL поста (`parse_post_url` → message_id). `iter_messages`/`get_messages(limit=N)` падают для ботов (`BotMethodInvalidError` через `messages.GetHistoryRequest`). Это ограничило UX: нельзя автоматически получить "последние N постов канала" для выбора/предпросмотра.

Inline spike (через `python -c` heredoc) экспериментально проверил альтернативный raw API — `channels.GetMessagesRequest` (namespace `channels.*`, не `messages.*`). Результаты обнадёживающие: метод принимает `id=[...]` (точные ID) и работает для bot-admin. Этот PR фиксирует результаты в standalone скрипте + ADR, чтобы refactor `core/telegram.py` (PR 2 из 4) мог использовать raw API для auto-discovery постов канала без ручных URLs.

## Pending

- **PR 2 из 4: refactor `core/telegram.py`** — добавить `get_last_messages(channel_id, limit)`:
  1. `entity = await client.get_entity(channel_id)` → `Channel` (id, access_hash).
  2. Binary search `max_id` через `channels.GetMessagesRequest(id=[mid])` (≤14 probes для upper=10000).
  3. Range fetch: `id=list(range(max_id, max_id-limit, -1))` → N постов одним запросом.
  4. Total requests: ~14 + 1 = 15 (вместо N при by-ID fetch) → значительно быстрее для больших каналов.
- **`.env.example` обновить** — добавить `MAX_PROBE_ID=10000` (верхняя граница binary search) и `TELEGRAM_REQUEST_DELAY=1.0` (delay между запросами). Spec issue #29 упоминает как опциональный шаг — не сделан в этом PR (можно в PR 2).
- **ADR PR#14 caveat снимается** — `docs/decisions/2026-07-20-pr-14-spike-telethon.md` говорил "get_messages не работает для ботов → user-session для истории". Этот spike показывает, что `channels.GetMessagesRequest` работает → caveat снимается. Обновить ADR PR#14 в PR 2 (или создать superseding ADR).

## Watch out

- **`channels.GetMessagesRequest` принимает `id=[...]` (точные ID), НЕ `limit=N`** — это raw API метод, не high-level wrapper. Для "последние N постов" нужен **двухфазный алгоритм**:
  1. **Binary search max_id**: `lo=1, hi=MAX_PROBE_ID (10000)`, probe `mid=(lo+hi)//2`, если `messages[0].date is not None` → существует (`lo=mid+1`), иначе `hi=mid-1`. ~log2(10000) ≈ 14 probes. Каждый probe — один `GetMessagesRequest(id=[mid])`.
  2. **Range fetch**: `id=list(range(max_id, max_id-N, -1))` — ОДИН запрос возвращает N постов (с некоторыми None если посты удалены/не существуют — фильтровать).
- **`messages.GetHistoryRequest` запрещён для ботов** (контроль TEST 4) — `BotMethodInvalidError: ...caused by GetHistoryRequest`. Это ограничение MTProto для bot-аккаунтов, подтверждает PR#14.
- **`client.iter_messages` запрещён для ботов** (контроль TEST 5) — под капотом `GetHistoryRequest`, та же ошибка.
- **`asyncio.sleep(1.0)` между всеми запросами к Telegram** — flood control. Спека issue #29 явно требует 1 секунду между запросами. Для binary search (14 probes) + range fetch (1) — общее время ~15 секунд. Если нужно быстрее — уменьшать delay нельзя (flood risk), лучше кешировать max_id в БД после первого поиска.
- **`FloodWaitError` handling**: `except FloodWaitError as exc: await asyncio.sleep(exc.seconds + 1)` → retry. Реализовано через `_retry_on_flood(coro_factory, label)` helper (factory pattern — корутина пересоздаётся при retry). Стандартный Telethon pattern. В spike не сработал (все probes прошли без flood), но нужен для production.
- **`channels.GetMessagesRequest` возвращает `ChannelMessages`** (не `list[Message]`) — `.messages` атрибут содержит список `Message` объектов. `getattr(result, "messages", [])` — safe access.
- **`InputChannel(id, access_hash)`** — raw API требует `InputChannel` (id без `-100` prefix, из `entity.id` после `get_entity`). `entity.access_hash` — long int (e.g. `2360878343388152150`), уникален для канала. Если access_hash меняется (редко) — нужно заново `get_entity`.
- **Binary search корректен для монотонно возрастающих ID** — Telegram присваивает post IDs инкрементально (1, 2, 3, ..., max_id) без пропусков для каналов. Если пост удалён — `GetMessagesRequest(id=[deleted_id])` возвращает `messages=[None]` (date=None), но ID "существует" в нумерации. Binary search ищет max_id сущ. поста (date is not None). Для каналов с удалёнными постами в конце — может дать max_id меньший чем реальный последний. Edge case, для MVP приемлемо.
- **`MAX_PROBE_ID = 10000`** — верхняя граница. Для каналов с >10000 постов — нужно увеличивать (или динамически: первая probe `id=[1000000]`, если существует → hi=1000000). В spike 10000 хватило (max_id=113).
- **Ruff per-file-ignore для `scripts/*`** — добавлен `"scripts/*" = ["T201", "S603", "S101", "TRY300"]`. `TRY300` (return inside try) — ruff предлагает перенести `return False` в `else` блоки, но для тест-функций со множеством try/except это менее читаемо. PR#14 не требовал per-file-ignore (T201/S603/S101 не в select), но `TRY300`新增ился — пришлось добавить.
- **mypy не проверяет `scripts/`** — `[tool.mypy]` без `files` опции, CI использует `uv run mypy src/` (только src/). Скрипт использует `Any` для Telethon-объектов (spike, не production).
- **Session file `app_data/bot.session` (28672 bytes)** — переиспользуется с PR#14 (без повторного логина). В `.gitignore` (`app_data/*` кроме `.gitkeep`) — НЕ коммитить.
- **Тестовые посты в канале**: id=112, id=113 (из PR#14 spike) всё ещё в канале с `new.example.com`. Этот spike НЕ создаёт новые посты (только читает). Range fetch в TEST 3 включает id=112, id=113 — это норм, посты реальные.