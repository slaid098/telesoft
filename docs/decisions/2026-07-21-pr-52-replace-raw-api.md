---
pr: <PR-NUMBER>
issue: 51
status: Accepted
created: 2026-07-21
---

# ADR — PR <PR-NUMBER>: replace raw API with high-level get_messages in get_last_messages

## Статус

Accepted (2026-07-21). Реализует issue #51. Завершает миграцию с raw API на high-level API в `core/telegram.py` (начата в PR#50 для `edit_message_entities`). ADR `docs/decisions/2026-07-20-pr-32-get-last-messages.md` (raw API `ChannelsGetMessagesRequest`) — superseded.

## Контекст

`message.text` возвращал `None` для сообщений, полученных через raw API `ChannelsGetMessagesRequest` в `get_last_messages()`. Это корневая причина 0/0 — `find_posts_with_pattern` видит `text_len=0` для всех постов, pattern не совпадает, `matched=0`, результат `0/0`.

### Root cause

Raw API `channels.GetMessagesRequest` возвращает `ChannelMessages` объекты, которые не проходят через Telethon's `Message` constructor properly — `message.text` остаётся `None` (хотя `message.message` — raw text — заполнен). High-level `client.get_messages(chat_id, ids=ids)` properly инициализирует `Message` объекты, `message.text` работает (уже используется в `get_message()` и `get_messages()` — строки 91-104).

### Why raw API was used originally (PR#32)

PR#14 (spike) обнаружил, что `get_messages(limit=N)` / `iter_messages` → `BotMethodInvalidError` для ботов. PR#30 (spike v2) нашёл, что raw API `channels.GetMessagesRequest` работает для bot-admin. PR#32 реализовал `get_last_messages` через raw API как workaround. Но raw API возвращает `ChannelMessages` объекты, у которых `message.text` не инициализирован properly — этот баг не был обнаружен, потому что тесты использовали `MockMessage` с явно установленным `text` полем.

## Решение

**4 изменения:**

1. **`_fetch_messages_by_ids(chat_id: int, ids: list[int])`** — параметр `channel_input: InputChannel` заменён на `chat_id: int`. Реализация: `client.get_messages(chat_id, ids=ids)` вместо `client(ChannelsGetMessagesRequest(channel=channel_input, id=ids))`. Фильтр `m is not None and getattr(m, "date", None) is not None` сохранён. 3-retry на FloodWaitError сохранён.

2. **`_find_max_id(chat_id: int, max_probe_id: int, delay: float)`** — параметр `channel_input` заменён на `chat_id`. Binary search алгоритм не изменён.

3. **`get_last_messages(channel_id: int, limit: int = 100)`** — убран вызов `_get_channel_input(channel_id)`. `channel_id` передаётся напрямую в `_find_max_id` и `_fetch_messages_by_ids`.

4. **Cleanup** — удалён `_get_channel_input` (не используется), удалены импорты `ChannelsGetMessagesRequest`, `InputChannel`. Удалён `mock_channel_messages` helper из `conftest.py` (эмулировал raw API response).

## Альтернативы

1. **Сохранить raw API, исправить `message.text` вручную** — после fetch, конвертировать `message.message` → `message.text` для каждого сообщения. Плюс: минимальные изменения. Минус: хрупкий workaround (Telethon может изменить internal field names), не решает проблему с `entities` (тоже могут быть не инициализированы). Отклонено — high-level API решает все проблемы сразу.

2. **Использовать `iter_messages` вместо by-ID fetch** — `iter_messages(chat_id, limit=N)` проще. Минус: `BotMethodInvalidError` для ботов (PR#14, PR#30). Отклонено — не работает для bot-admin.

3. **User session вместо bot session** — user session имеет `get_messages(limit=N)` working. Минус: усложняет auth (phone+code flow), требует session management. Отклонено — bot session работает для `get_messages(ids=[...])` (by-ID fetch).

4. **Message ID в БД (user указывает ID поста)** — вместо auto-discovery, user вводит ID постов вручную. Минус: poor UX, требует ручной работы. Отклонено — auto-discovery через binary search работает с high-level API.

## Последствия

- `_fetch_messages_by_ids` сигнатура изменилась: `(channel_input: InputChannel, ids)` → `(chat_id: int, ids)`. Internal function, callers обновлены.
- `_find_max_id` сигнатура изменилась: `(channel_input: InputChannel, max_probe_id, delay)` → `(chat_id: int, max_probe_id, delay)`. Internal function, caller обновлен.
- `_get_channel_input` удалён — Telethon high-level API сам резолвит `chat_id` в channel peer. Убирает 1 лишний `get_entity` вызов per `get_last_messages` invocation.
- `ChannelsGetMessagesRequest` и `InputChannel` импорты удалены из `core/telegram.py`. Все импорты из `telethon.tl.functions.channels` и `telethon.tl.types.InputChannel` — больше не нужны.
- `mock_channel_messages` helper удалён из `conftest.py`. `mock_telethon_client` fixture упрощён (убраны `client.return_value` и `client.side_effect` для raw API path).
- ADR PR#32 (raw API `ChannelsGetMessagesRequest`) — superseded. Raw API подход остаётся валидным для cases где high-level API не работает (но в Telethon 1.44+ `get_messages(ids=[...])` работает для bot-admin). ADR PR#32 не обновляется (immutable record).
- `scripts/spike_telethon_v2.py` — standalone spike script, использует `InputChannel` напрямую (собственный import). НЕ затронут этим PR.
- Integration tests (`test_real_edit.py`) — используют `get_message` (high-level API, by-ID fetch). НЕ затронуты этим PR.
