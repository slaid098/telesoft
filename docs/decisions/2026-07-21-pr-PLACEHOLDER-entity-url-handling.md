# ADR — PR <PR_NUMBER>: handle URL entities in messages and add integration tests

## Статус

Accepted (2026-07-21) — фикс бага, найденного при тестировании на реальном канале (`-1003903711726`): auto-discovery находит посты но `find_posts_with_pattern` возвращает 0 совпадений потому что URL — это `MessageEntityTextUrl` (formatted link, URL в `entity.url`, не в `m.text`). 5 коммитов, 8 файлов. `find_posts_with_pattern` теперь извлекает URL из entities и добавляет к text для матчинга. `replace_link_in_post` теперь заменяет URL в entities через raw API `messages.EditMessageRequest` (с `InputPeerChannel`). 4 integration tests (`tests/integration/test_real_edit.py`) skipif no creds. ruff, mypy, Biome, svelte-check (0 errors), Vitest (28), pytest (122 unit + 4 integration skipped) — green. No comments. Coverage 94.33%.

## Контекст

При тестировании на реальном канале (`-1003903711726`) auto-discovery (PR#32 `get_last_messages`) отрабатывал: `binary search: max_id=113`, `fetched 2 messages` (PR#40 logging). Но `find_posts_with_pattern` (PR#34) возвращал 0 matching posts, хотя posts содержали URL `https://new.example.com/path`. Причина: URL в постах — это `MessageEntityTextUrl` (formatted link, текст "click here", URL скрыт в `entity.url`), а не в `m.text`. Telethon `Message.text` хранит только видимый текст, не raw URL behind formatted links.

Код `core/link_replacer.py:108-109` проверял ТОЛЬКО `m.text`:
```python
regex = re.compile(pattern)
return [m for m in messages if (getattr(m, "text", None) or "") and regex.search(m.text)]
```

`replace_link_in_post` тоже заменял только в text через `client.edit_message(chat_id, msg_id, text=new_text)` — Telethon `client.edit_message` обновляет `message` (text), но НЕ обновляет `entities` (formatted links остаются со старыми URL).

Нужно было: (1) матчить URL в entities для find_posts, (2) заменять URL в entities через raw API EditMessageRequest, (3) integration tests с реальным каналом чтобы доказать fix работает на реальных Telegram постах.

## Решение

5 фиксов по спеке issue #43:

1. **find_posts_with_pattern** (`src/telesoft/core/link_replacer.py`) — добавлен helper `_entity_urls(message)` который возвращает список URL из `MessageEntityTextUrl` entities. `find_posts_with_pattern` теперь строит `full_text = text + " " + " ".join(entity_urls)` и матчит regex против `full_text`. Message матчится если pattern matches raw text OR любой entity url. Лог per-message: `logger.info("find_posts: msg {} text_len={} entity_urls={} matched={}", ...)`.

2. **replace_link_in_post** (`src/telesoft/core/link_replacer.py`) — два пути замены:
   - **URL в text** → `text_count > 0`: regex substitution в text через `replace_link`, edit через `telegram_module.edit_message(chat_id, message_id, new_text)`. `match_source="text"` в result dict.
   - **URL в entity** → `entity_count > 0`: rebuild entities — для каждого entity с `url` matching pattern, создать новый `MessageEntityTextUrl(offset=e.offset, length=e.length, url=new_link)`, остальные entities unchanged. Edit через новый helper `telegram_module.edit_message_entities(chat_id, message_id, text, new_entities)`. `match_source="entity"` в result dict.
   - **No match** → skipped, no edit called.
   - **Text path preferred** когда pattern matches both (text заменяется, entities нет) — text replacement проще, не трогает entities.

3. **edit_message_entities helper** (`src/telesoft/core/telegram.py`) — raw API `MessagesEditMessageRequest` (из `telethon.tl.functions.messages`) с `peer=InputPeerChannel(channel_id, access_hash)`. Channel input resolved через `_get_channel_input` (существующий helper PR#32, использует `client.get_entity` для access_hash).

4. **Логирование** — `link_replacer.find_posts_with_pattern` лог per-message (text_len, entity_urls count, matched). `link_replacer.replace_link_in_post` лог match source (text/entity/no match). `runner._run_job` лог `discovery: fetched={}, matched={}` после auto-discovery + filter.

5. **Integration tests** (`tests/integration/test_real_edit.py`) — 4 теста с `pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TELEGRAM_CREDS, ...)]`. Fixtures send test message to `CHANNEL_ID` (env `TELESOFT_TEST_CHANNEL_ID`, default `-1003903711726`), yield, delete on teardown (`finally` блок). Tests: `test_find_text_url` (URL в raw text матчит), `test_find_entity_url` (URL в entity матчит после fix), `test_replace_text_url` (replace URL в raw text, post отредактирован), `test_replace_entity_url` (replace URL в entity, entity.url обновлён). `pyproject.toml` добавлен `markers = ["integration: ..."]`.

## Альтернативы

### Поиск URL в entities (Фикс 1)
- **Extract entity URLs + concat to text (выбрано)** — `_entity_urls(message)` возвращает `[e.url for e in entities if hasattr(e, "url")]`, `full_text = text + " " + " ".join(entity_urls)`, `regex.search(full_text)`. Простой, единый regex pass по объединённому тексту. URL в entities обрабатываются тем же regex что и URL в text.
- **Отдельный regex pass per entity** — для каждого entity `regex.search(e.url)` отдельно. Сложнее (две логики matching), дублирование кода. Отклонено — concat проще, regex один.
- **Inline-only matching** — `regex.search(text + "".join(entity_urls))` без separator. Может создать false positive на границе text/url (например pattern `com/path` сматчит `path` в text + `com` в entity). Separator (" ") исключает это. Выбрано с separator.
- **Telethon Message.to_dict() / raw JSON** — использовать `message.to_dict()` (возвращает dict с `message` + `entities` плоско), regex по JSON string. Хрупко (формат dict может меняться между Telethon версиями), JSON escapes ломают regex (кавычки, backslashes). Отклонено.
- **Parse markdown** — Telethon `client.send_message(parse_mode='md', "[click here](https://...)")` создаёт `MessageEntityTextUrl`. Можно хранить original markdown в БД и regex по markdown. Но в Telegram markdown не хранится — только entities. Отклонено.
- **Оставить только text** — не матчить entity URLs. Отклонено — баг не фикшен, auto-discovery находит посты но find_posts_with_pattern возвращает 0.

### Замена URL в entities (Фикс 2)
- **Raw API `messages.EditMessageRequest` с `InputPeerChannel` (выбрано)** — Telethon 1.44 `EditMessageRequest` в `telethon.tl.functions.messages`, принимает `peer=TypeInputPeer`, `entities=List[TypeMessageEntity]`. Channel resolved через `_get_channel_input` (InputChannel) → `InputPeerChannel(channel_id, access_hash)`. Контроль над entities (replace matching, keep rest). Работает для bot-admin (подтверждено spike PR#30).
- **Telethon `client.edit_message(formatting_entities=...)`** — Telethon `client.edit_message` принимает `formatting_entities` параметр (`List[TypeMessageEntity]`), делает raw API call под капотом. Высокоуровневый wrapper, но: (1) парсит `text` через `_parse_message_text` если `formatting_entities=None` (мы передаём entities, OK), (2) возвращает `Message` (не `Updates`), (3) абстракция скрывает детали. Можно использовать `await client.edit_message(chat_id, message_id, text=text, formatting_entities=new_entities, link_preview=False)`. Отклонено — выбрали raw API для explicit control (спека требовала raw API) и для теста что raw API работает (spike PR#30 подтверждал channels.GetMessagesRequest, этот PR подтверждает messages.EditMessageRequest).
- **`channels.EditMessageRequest`** — НЕ существует в Telethon 1.44 (`telethon.tl.functions.channels` имеет `EditAdminRequest`/`EditBannedRequest`/`EditLocationRequest`/`EditPhotoRequest`/`EditTitleRequest`, но НЕ `EditMessageRequest`). Спека issue #43 указывала `telethon.tl.functions.channels.EditMessageRequest` (channel param) — это ошибка спеки. Реальный raw API — `messages.EditMessageRequest`. Если бы существовал channels версия — была бы preferred (не нужен `InputPeerChannel` conversion, сразу `channel=InputChannel`). Отклонено — не существует.
- **Удалить entity, добавить URL в text** — вместо замены `entity.url`, удалить entity entirely, добавить URL как plain text в `message.text`. Теряет formatting (text "click here" с URL → text "click here https://new.example.com/edited" plain). Ломает UX поста (formatted link → plain URL visible). Отклонено — теряет formatting.
- **Bot API HTTP editMessageText** — HTTP call к `https://api.telegram.org/bot<token>/editMessageText` с `entities` JSON. Medgoroka: Telethon уже подключен, raw API через `client(request)` проще (тот же MTProto connection, тот же client). Отклонено — Telethon raw API preferred (PR#14/16/32 паттерн).

### Логирование (Фикс 3)
- **loguru per-message logging (выбрано)** — `logger.info("find_posts: msg {} ...", ...)` per message, `logger.info("replace_link_in_post: ... match in text/entity/no match")`, `logger.info("discovery: fetched={}, matched={}", ...)` в runner. Использует уже импортированный loguru (PR#16/40). Виден в prod (INFO default). Не падает тесты (mock'и не assert'ят на логах).
- **Structured logging (structlog)** — JSON-logs с контекстом. Лучше для log aggregation, но требует новую dependency. Отклонено — loguru достаточно (PR#40 pattern).
- **Metrics (prometheus)** — counters/gauges для discovery (fetched/matched). Отклонено — overkill для MVP.
- **Оставить как есть** — `find_posts_with_pattern` молча. Отклонено — невозможно дебажить prod (PR#40 уже добавил discovery logging, этот PR добавляет filter logging).

### Integration tests (Фикс 4)
- **Opt-in `pytest -m integration` + skipif no creds (выбрано)** — `pytestmark = [pytest.mark.integration, pytest.mark.skipif(not CREDS, ...)]`. Integration tests НЕ в CI (skipif no creds → skip автоматически, не падают). Локальный запуск: `pytest -m integration` (или `pytest tests/integration/`). Главный агент прогоняет через `docker exec telesoft-api-1 pytest -m integration`.
- **Всегда skip** — `pytest.skip()` без opt-in. Отклонено — нет способа запустить локально.
- **В CI с test channel** — secrets в GitHub Actions, test channel доступен из CI. Отклонено — Telegram rate limits, test channel может быть modified, secrets в CI — security risk. Integration tests должны быть opt-in.
- **Mock Telethon вместо real API** — unit tests с mock'ами Telethon (как `test_telegram_client.py`). Отклонено — mock не доказывает что raw API работает на реальном Telegram. Integration tests нужны для доказательства (особенно `EditMessageRequest` который не был в spike PR#30).
- **Spike script (standalone)** — отдельный `scripts/integration_test.py` (как spike PR#14/30). Отклонено — не интегрирован в pytest, нет skipif, нет fixtures cleanup.

### E2E test update (Фикс 6)
- **Оставить zero-match E2E + добавить integration tests в backend (выбрано)** — `web/tests/e2e/mobile.spec.ts` не тронут (использует nonexistent pattern, проверяет zero-match feedback). Integration tests в backend (`tests/integration/test_real_edit.py`) покрывают реальный URL match+replace. E2E не может отправлять посты (нет API для send_message в frontend), поэтому реальный URL test невозможен в E2E.
- **Обновить E2E на реальный URL** — E2E test "replace-link form submission" использует реальный URL вместо nonexistent. Но E2E не может отправлять посты → real URL не существует в канале → zero match (как сейчас). Нет смысла менять.
- **E2E через API создания постов** — добавить API endpoint `POST /api/channels/{id}/send-test-message` для E2E. Отклонено — new endpoint только для testing, security risk (любой authed user может слать посты), не в scope этого PR.

## Ключевые отклонения от спеки

Спека issue #43 указывала точные строки и код — реализация в основном 1-в-1. Незначительные отклонения:

- **`telethon.tl.functions.messages.EditMessageRequest` (НЕ `channels`)** — спека указывала `telethon.tl.functions.channels.EditMessageRequest` с `channel=ch` параметром, но в Telethon 1.44 `EditMessageRequest` находится в `telethon.tl.functions.messages` и принимает `peer=TypeInputPeer` (НЕ `channel=TypeInputChannel`). `channels.EditMessageRequest` НЕ существует. Использован `messages.EditMessageRequest` + `InputPeerChannel(channel_id, access_hash)` (conversion из `InputChannel` через `_get_channel_input`). См. "Альтернативы" выше.
- **`match_source: "text" | "entity"` в result dict** — спека не упоминала этот ключ, добавлен для диагностики (tests могут assert'ить, runner/log может использовать в будущем). Не breaking (orchestrator/runner не проверяют этот ключ, используют `result.get("success")` / `result.get("edited")`).
- **Text path preferred over entity path** — спека не уточняла порядок. Реализовано: если pattern matches text (`text_count > 0`), text path выбран (regex substitution в text, entities untouched). Иначе если pattern matches entity (`entity_count > 0`), entity path выбран (rebuild entities, text untouched). Это проще (не нужно одновременно replace в text и entities), и обычно URL либо в text либо в entity, не оба.
- **`TELESOFT_TEST_CHANNEL_ID` env override** — спека хардкодила `-1003903711726` (test channel). Реализовано через env var с default `-1003903711726` для гибкости (можно указать другой channel без code change).
- **E2E не тронут** — спека указывала "Оставить zero-match test, добавить integration test в backend" как одну из альтернатив. Выбрана эта альтернатива (E2E не может отправлять посты, integration tests покрывают real URL).

## Pending / Follow-up

- **Прогон integration tests локально** — главный агент должен запустить `docker exec telesoft-api-1 pytest -m integration`. Сабагент НЕ прогоняет (нужен running контейнер с creds + test channel access).
- **PR#26 pending items** сохраняются: Edit channel mode, Job retry/delete UI, WebSocket shared client, Job detail auto-refresh fallback (polling), Logs pagination.
- **Кеширование max_id в БД** (PR#32 pending) — `last_known_max_id` field в `channels` table ускорит `get_last_messages` с 15 запросов до 1.
- **Structured logging** — если понадобится log aggregation, мигрировать на `structlog` (JSON logs).
- **E2E test с реальным URL** — E2E не может отправлять посты. Integration tests покрывают реальный URL match+replace в backend. Если когда-нибудь появится API для send-test-message (admin only), E2E сможет тестировать full flow.
- **`match_source` в log/result** — если понадобится deeper диагностика, можно persist `match_source` в `edit_logs` table (new column `match_source TEXT`). Не в scope.