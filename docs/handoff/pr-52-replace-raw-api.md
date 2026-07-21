---
pr: 52
issue: 51
branch: fix/telegram/replace-raw-api
status: ready
created: 2026-07-21
---

# Handoff — PR 52: replace raw API with high-level get_messages, fix message.text=None

## Что сделано

Реализован issue #51 — raw API `ChannelsGetMessagesRequest` заменён на high-level `client.get_messages(chat_id, ids=ids)` в `get_last_messages()` (binary search + range fetch). Это устраняет корневую причину `message.text=None`: raw API возвращал `ChannelMessages` объекты, у которых `message.text` не инициализирован properly; high-level API возвращает fully-initialised `Message` объекты. 3 коммита, 3 файла изменено (1 src + 2 test), 125 unit tests green, ruff/mypy — green.

### Шаг 1: `src/telesoft/core/telegram.py` — замена raw API

- `_fetch_messages_by_ids(chat_id: int, ids: list[int]) -> list[Message]` — параметр `channel_input: InputChannel` заменён на `chat_id: int`. Реализация: `client.get_messages(chat_id, ids=ids)` вместо `client(ChannelsGetMessagesRequest(channel=channel_input, id=ids))`. Фильтр `m is not None and getattr(m, "date", None) is not None` сохранён. 3-retry на FloodWaitError сохранён.
- `_find_max_id(chat_id: int, max_probe_id: int, delay: float) -> int` — параметр `channel_input` заменён на `chat_id`. Binary search алгоритм не изменён. Docstring упрощён.
- `get_last_messages(channel_id: int, limit: int = 100)` — убран вызов `_get_channel_input(channel_id)`. `channel_id` передаётся напрямую в `_find_max_id` и `_fetch_messages_by_ids`. Docstring обновлён.
- Удалён `_get_channel_input` (больше не используется).
- Удалены импорты: `ChannelsGetMessagesRequest` (from `telethon.tl.functions.channels`), `InputChannel` (from `telethon.tl.types`).

### Шаг 2: `tests/conftest.py` — cleanup

- Удалён `mock_channel_messages(messages)` helper — эмулировал `ChannelMessages` результат raw API (`.messages` атрибут). После замены на high-level API `client.get_messages` возвращает plain list, helper не нужен.
- `mock_telethon_client` fixture — убраны `client.side_effect = None` и `client.return_value = mock_channel_messages([])` (raw API default). `client.get_messages.return_value = [mock_message]` сохранён (используется `get_message`/`get_messages` тестами).
- Удалён `MagicMock` import (был нужен только для `mock_channel_messages`).

### Шаг 3: `tests/test_telegram_client.py` — обновить тесты

- Удалён `ChannelsGetMessagesRequest` import.
- Удалён `mock_channel_messages` import.
- Удалён `_probe_response(probe_id, exists)` helper — эмулировал raw API response для binary search probe.
- Все тесты `_fetch_messages_by_ids` и `_find_max_id`: `channel_input=object()` → `chat_id=-1001234567890`.
- `mock_telethon_client.return_value = mock_channel_messages(...)` → `mock_telethon_client.get_messages.return_value = [...]` (plain list).
- `mock_telethon_client.side_effect = _probe` → `mock_telethon_client.get_messages.side_effect = _probe`.
- `mock_telethon_client.assert_awaited_once()` → `mock_telethon_client.get_messages.assert_awaited_once()` (проверка high-level API вызова вместо raw API).
- `test_get_last_messages_success`: assertion `isinstance(request, ChannelsGetMessagesRequest)` → `mock_telethon_client.get_messages.await_args.kwargs["ids"] == list(range(150, 50, -1))`.
- `test_get_last_messages_empty_channel`: `mock_telethon_client.assert_not_awaited()` → `mock_telethon_client.get_messages.assert_not_awaited()`.
- `test_find_max_id_binary_search`: `_probe(request: ChannelsGetMessagesRequest)` → `_probe(*_args, **kwargs)` (kwargs["ids"][0] для mid).
- `test_get_last_messages_reads_settings_once`: убран monkeypatch `_get_channel_input` (функция удалена). Stub `start_client` сохранён.

## Почему

`message.text` возвращал `None` для сообщений из raw API `ChannelsGetMessagesRequest`. Это корневая причина 0/0 — `find_posts_with_pattern` видит `text_len=0` для всех постов (через `getattr(m, "text", None) or ""`), pattern не совпадал, `matched=0`, результат `0/0`.

### Корневая причина

Raw API `channels.GetMessagesRequest` возвращает `ChannelMessages` объекты, которые не проходят через Telethon's `Message` constructor properly — `message.text` остаётся `None` (хотя `message.message` — raw text — заполнен). High-level `client.get_messages(chat_id, ids=ids)` properly инициализирует `Message` объекты, `message.text` работает (уже используется в `get_message()` и `get_messages()` — строки 91-104).

### Почему это не было обнаружено раньше

- PR#32 (get_last_messages via raw API) тестировался с `MockMessage` objects, у которых `text` поле установлено явно. Raw API `ChannelMessages` объекты не тестировались (только mock'и).
- PR#44 (entity URL handling) добавил `edit_message_entities` через raw API `MessagesEditMessageRequest`, но PR#50 заменил его на high-level `formatting_entities`. `get_last_messages` остался на raw API.
- PR#50 (rate limiting) улучшил retry/delay, но не трогал `get_last_messages` — root cause 0/0 не был address'нут.

### Дополнительный benefit

Убран `_get_channel_input` (→ `get_entity` вызов per `get_last_messages` call). Telethon's high-level API сам резолвит `chat_id` → channel peer. Это убирает 1 лишний API call per `get_last_messages` invocation (binary search делает ~14 probes + 1 range fetch = ~15 API calls, было +1 for `get_entity`).

## Pending

- **Прогон integration tests локально** — главный агент должен запустить `uv run pytest -m integration` (нужны валидные creds `TELEGRAM_BOT_TOKEN` / `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` + `TELEGRAM_SESSION_STRING` в `.env` + test channel access). Сабагент НЕ прогоняет integration tests. Текущая сессия Telegram может быть expired (`FloodWaitError` 642с при попытке integration tests во время этого PR).
- **Pre-existing broken files on main** (`Dockerfile.api`, `docker-compose.yml`, `Dockerfile.nginx`, `docker-compose.preview.yml`, `nginx.preview.conf`) — НЕ включены в этот PR (как и в PR#48/#50).
- **PR#50 pending items** сохраняются: `TELEGRAM_EDIT_DELAY` tuning, `pre_edit_delay` hardcoded, PR#26 UI items.

## Watch out

- **`_fetch_messages_by_ids` сигнатура изменилась**: `(channel_input: InputChannel, ids)` → `(chat_id: int, ids)`. Internal function, единственный caller — `_find_max_id` и `get_last_messages` (обновлены в этом PR).
- **`_find_max_id` сигнатура изменилась**: `(channel_input: InputChannel, max_probe_id, delay)` → `(chat_id: int, max_probe_id, delay)`. Internal function, единственный caller — `get_last_messages` (обновлён в этом PR).
- **`mock_channel_messages` helper удалён** из `conftest.py`. Если другие тесты используют его — они сломаются. Проверено: только `test_telegram_client.py` использовал его (обновлён в этом PR).
- **`mock_telethon_client` fixture изменился**: убраны `client.return_value` и `client.side_effect` (raw API default). `client.get_messages.return_value = [mock_message]` сохранён. Тесты, которые override `client.get_messages.return_value` или `client.get_messages.side_effect` — работают. Тесты, которые set `client.return_value` (raw API path) — сломаются (обновлены в этом PR).
- **`client.get_messages(chat_id, ids=ids)`** — Telethon high-level API properly инициализирует `Message` объекты (включая `message.text`, `message.entities`). Raw API `ChannelsGetMessagesRequest` возвращал `ChannelMessages.messages` где `message.text` был `None` (хотя `message.message` — raw text — был заполнен). Это был root cause 0/0.
- **`_get_channel_input` удалён** — Telethon high-level API сам резолвит `chat_id` (int с `-100` prefix или `@username`) в channel peer. `InputChannel(id, access_hash)` больше не нужен.
