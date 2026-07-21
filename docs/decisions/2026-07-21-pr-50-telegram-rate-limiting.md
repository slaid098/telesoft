---
pr: 50
issue: 49
status: Accepted
created: 2026-07-21
---

# ADR — PR 50: rate limiting, FloodWait handling, eliminate redundant API calls

## Статус

Accepted (2026-07-21). Реализует issue #49. Дополняет ADR `docs/decisions/2026-07-21-pr-44-entity-url-handling.md` (raw API `MessagesEditMessageRequest` заменён на high-level `formatting_entities`).

## Контекст

Replace-link jobs падали с `FloodWaitError` или возвращали 0/0 (ни одного edit'а). Анализ выявил 5 корневых причин:

1. **Нет паузы между edit-ами** — runner делал 30 edit-ов подряд без `asyncio.sleep` между ними → Telegram FloodWait.
2. **Нет `flood_sleep_threshold`** — Telethon default 60с. FloodWait 10-30с (короткие) бросал exception вместо auto-sleep, прерывая весь job.
3. **Нет retry на edit FloodWait** — `edit_message` и `edit_message_entities` не имели retry loop (в отличие от `_fetch_messages_by_ids` из PR#32, который имеет 3-retry). Один FloodWait → post marked failed без backoff.
4. **Redundant API calls** — `replace_link_in_post(chat_id, message_id, ...)` re-fetch'ил message по ID через `get_message` (30 лишних запросов для 30 matching posts). `edit_message_entities` re-resolv'ил channel через `_get_channel_input` per edit (ещё 30 лишних `get_entity` запросов). ~60 лишних API calls per job увеличивали риск FloodWait.
5. **Raw API вместо `formatting_entities`** — PR#44 использовал `MessagesEditMessageRequest` с `InputPeerChannel(channel_id, access_hash)`, что требовало `_get_channel_input` (→ `get_entity`) per edit. High-level `client.edit_message(formatting_entities=...)` делает peer resolution сам.

## Решение

**5 изменений, каждое решает одну корневую причину:**

1. **`TELEGRAM_EDIT_DELAY` config** (default 5.0с) + `pre_edit_delay` (2.0с) в `JobRunner.__init__`. Runner спит 2с после discovery (read→write transition) и 5с после каждого успешного edit. НЕ спит после skip (нет API write). `main.py` передаёт `edit_delay=settings.telegram_edit_delay, pre_edit_delay=2.0`.

2. **`flood_sleep_threshold=100`** в `TelegramClient` constructor. Telethon auto-sleep'ит на FloodWait ≤100с (не бросает exception). Дополнительно: `auto_reconnect=True`, `connection_retries=100`, `retry_delay=5`, `entity_cache_limit=1000`.

3. **3-retry на FloodWait** в `edit_message` и `edit_message_entities`. `asyncio.sleep(exc.seconds + 1)` между retry, re-raise после 3-й попытки. Паттерн из `_fetch_messages_by_ids` (PR#32).

4. **Передача message object** вместо re-fetch по ID. `replace_link_in_post(chat_id, message, pattern, new_link)` принимает message object напрямую (убран `get_message` вызов = -30 API calls). `replace_link_in_posts` и runner передают `message` объект. `edit_message_entities(chat_id, message, entities)` принимает message object (убран `_get_channel_input` вызов = -30 API calls).

5. **`formatting_entities` вместо raw API**. `edit_message_entities` использует `client.edit_message(chat_id, message.id, text=message.text or "", formatting_entities=entities)` вместо `MessagesEditMessageRequest(peer=InputPeerChannel(...), ...)`. Telethon сам резолвит channel peer. Entity URL replacement: `entity.url = new_link` in-place (вместо создания новых `MessageEntityTextUrl` объектов) — сохраняет original entity metadata, меньше аллокаций. Удалены импорты `MessagesEditMessageRequest`, `InputPeerChannel`.

## Альтернативы

1. **Infinite retry на FloodWait** (вместо 3-retry) — spike PR#30 использовал infinite retry. Плюс: не сдаётся при repeated FloodWait. Минус: job может зависеть на часы. Отклонено — 3-retry bounded, caller (runner) ловит exception и marked failed, user может retry.

2. **Per-message delay через `asyncio.sleep` в link_replacer** (вместо runner) — delay в `replace_link_in_post` после edit. Минус: link_replacer — pure function (не должен знать про rate limiting), delay — infrastructure concern. Отклонено — delay в runner (infrastructure layer).

3. **`TELEGRAM_EDIT_DELAY` через `Settings` в runner** (вместо constructor param) — runner читает `Settings.from_env()` для delay. Минус: runner уже принимает `max_concurrency` как constructor param (не читает Settings), нарушение паттерна. Отклонено — constructor param (`edit_delay=settings.telegram_edit_delay` в `main.py`).

4. **Raw API `MessagesEditMessageRequest` (PR#44 подход)** — оставить как есть, не менять на `formatting_entities`. Минус: требует `_get_channel_input` per edit (30 лишних `get_entity` запросов). Отклонено — high-level API делегирует peer resolution Telethon'у.

5. **Создание новых `MessageEntityTextUrl` объектов** (вместо in-place mutation) — PR#44 подход, rebuild entities list с новыми объектами. Плюс: immutable, не мутирует caller'а message. Минус: больше аллокаций, теряет original entity metadata (если Telethon добавит новые fields в будущем). Отклонено — in-place mutation проще, message не переиспользуется после edit в current flow.

6. **`pre_edit_delay` через `Settings`** (вместо hardcoded 2.0) — вынести в `TELEGRAM_PRE_EDIT_DELAY` env var. Плюс: configurable. Минус: overengineering для MVP (2с — разумный default, не требует tuning). Отклонено — hardcoded в `main.py` и `JobRunner.__init__` default.

## Последствия

- `edit_message_entities` сигнатура изменилась: `(chat_id, message_id, text, entities)` → `(chat_id, message, entities)`. Breaking change для любого caller'а — единственный caller (`link_replacer.py`) обновлён в этом PR.
- `replace_link_in_post` сигнатура изменилась: `(chat_id, message_id, pattern, new_link)` → `(chat_id, message, pattern, new_link)`. Breaking change — callers (runner, `replace_link_in_posts`, integration tests) обновлены.
- `edit_message` теперь retry'ит на FloodWait (поведение изменилось — раньше бросал сразу, теперь 3-retry). Non-breaking для callers (return type unchanged, exception type unchanged).
- `TELEGRAM_EDIT_DELAY` env var — новый, default 5.0с. Production должен задать в `.env` если нужен другой интервал.
- In-place entity mutation: `entity.url = new_link` мутирует исходный message object. В current flow безопасно (runner не переиспользует messages после edit), но стоит учитывать при future refactoring.
- ADR PR#44 (raw API `MessagesEditMessageRequest`) — superseded этим ADR для `edit_message_entities`. Raw API подход (PR#44) остаётся валидным для cases где `formatting_entities` не работает (но в Telethon 1.44+ работает). ADR PR#44 не обновляется (immutable record).
- `MessagesEditMessageRequest` и `InputPeerChannel` импорты удалены из `core/telegram.py`. `_get_channel_input` и `InputChannel` сохранены (используются в `get_last_messages` binary search, PR#32).
- `MockMessage` entities in-place mutation test: `test_replace_link_in_post_replaces_entity_url` проверяет `entity.url == "https://new.example.com/edited"` после `replace_link_in_post` (in-place mutation assertion).
- Integration tests (`test_real_edit.py`) передают message object напрямую (`replace_link_in_post(CHANNEL_ID, test_text_url_msg, ...)` вместо `test_text_url_msg.id`). Требует валидную Telegram session для прогона.
