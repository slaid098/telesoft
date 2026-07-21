---
pr: <PR_NUMBER>
issue: 43
branch: fix/api/entity-url-handling
status: ready
created: 2026-07-21
---

# Handoff — PR <PR_NUMBER>: handle URL entities in messages and add integration tests

## Что сделано

Реализован issue #43 — фикс бага, найденного при тестировании на реальном канале (`-1003903711726`): auto-discovery находит посты (max_id=113, fetched 2 messages), но `find_posts_with_pattern` возвращает 0 совпадений потому что URL — это `MessageEntityTextUrl` (formatted link, URL скрыт в `entity.url`), а не в `m.text`. Regex не матчит.

5 коммитов, 8 файлов изменено (4 src + 3 tests + 1 config), 122 unit tests + 4 integration tests (skipif no creds), ruff/mypy/Biome/svelte-check/Vitest/Knip — green.

### Фикс 1: find_posts_with_pattern — `src/telesoft/core/link_replacer.py`

Извлекает URL из `MessageEntityTextUrl` entities и добавляет к тексту для матчинга:

```python
def _entity_urls(message: Any) -> list[str]:
    entities = getattr(message, "entities", None) or []
    return [e.url for e in entities if hasattr(e, "url")]

async def find_posts_with_pattern(messages: list[Any], pattern: str) -> list[Any]:
    regex = re.compile(pattern)
    matching: list[Any] = []
    for m in messages:
        text = getattr(m, "text", None) or ""
        entity_urls = _entity_urls(m)
        full_text = text + " " + " ".join(entity_urls)
        matched = bool(full_text.strip()) and bool(regex.search(full_text))
        logger.info("find_posts: msg {} text_len={} entity_urls={} matched={}", ...)
        if matched:
            matching.append(m)
    return matching
```

### Фикс 2: replace_link_in_post — `src/telesoft/core/link_replacer.py` + `core/telegram.py`

Два случая:
- URL в `text` → `edit_message(chat_id, msg_id, text=new_text)` (regex substitution в text)
- URL в `entity.url` → raw API `EditMessageRequest` с обновлёнными entities (regex substitution в `e.url`)

`core/telegram.py` helper:
```python
async def edit_message_entities(chat_id, message_id, text, entities) -> Any:
    client = await start_client()
    channel_input = await _get_channel_input(chat_id)
    peer = InputPeerChannel(channel_id=channel_input.channel_id, access_hash=channel_input.access_hash)
    return await client(MessagesEditMessageRequest(peer=peer, id=message_id, message=text, entities=entities))
```

Result dict получает новый ключ `match_source: "text" | "entity"` для диагностики.

### Фикс 3: Логирование

- `link_replacer.find_posts_with_pattern`: `logger.info("find_posts: msg {} text_len={} entity_urls={} matched={}", ...)` per message
- `link_replacer.replace_link_in_post`: `logger.info("replace_link_in_post: msg {} match in text/entity (replacements={})", ...)` + `logger.info("... no match ...")` if skip
- `runner._run_job`: `logger.info("discovery: fetched={}, matched={}", len(messages), total)` после `find_posts_with_pattern`

### Фикс 4: Integration tests — `tests/integration/test_real_edit.py`

4 теста (pytestmark: `integration` marker + `skipif` no creds):
- `test_find_text_url` — URL в raw text матчит
- `test_find_entity_url` — URL в entity матчит (после fix)
- `test_replace_text_url` — URL в raw text заменяется, post отредактирован
- `test_replace_entity_url` — URL в entity заменяется, entity.url обновлён

Fixtures (`test_text_url_msg` / `test_entity_url_msg`): send test message to CHANNEL_ID (`-1003903711726` env-override), yield, delete on teardown. Channel clean.

### Фикс 5: pyproject + pytest config

`[tool.pytest.ini_options]`:
- `markers = ["integration: requires Telegram creds + real channel (opt-in via -m integration)"]`
- `testpaths = ["tests"]` (без изменений, включает `tests/integration/`)
- `addopts = "--cov=telesoft --cov-report=term-missing --cov-fail-under=80"` — coverage gate не изменён (integration tests skipif no creds, не понижают coverage)

### Фикс 6: E2E

Спека: "Оставить zero-match test, добавить integration test в backend" — E2E (`web/tests/e2e/mobile.spec.ts`) не тронут, integration tests в backend добавлены.

## Почему

При тестировании на реальном канале auto-discovery (PR#32 `get_last_messages`) отрабатывал: `binary search: max_id=113`, `fetched 2 messages` (PR#40 logging). Но `find_posts_with_pattern` (PR#34) возвращал 0 — pattern `https://new.example.com/path` не матчит `m.text` потому что URL — это `MessageEntityTextUrl` (formatted link, текст "click here", URL скрыт в `entity.url`). Telethon `Message.text` хранит только видимый текст, не raw URL behind formatted links.

Код `core/link_replacer.py:108-109` проверял ТОЛЬКО `m.text`:
```python
regex = re.compile(pattern)
return [m for m in messages if (getattr(m, "text", None) or "") and regex.search(m.text)]
```

Нужно было: (1) матчить URL в entities для find_posts, (2) заменять URL в entities через raw API EditMessageRequest (Telethon `client.edit_message` только обновляет text, не entities), (3) integration tests с реальным каналом.

## Pending

- **Прогон integration tests локально** — главный агент должен запустить `docker exec telesoft-api-1 pytest -m integration` (нужен running контейнер с creds + test channel access). Сабагент НЕ прогоняет integration tests.
- **PR#26 pending items** сохраняются: Edit channel mode, Job retry/delete UI, WebSocket shared client, Job detail auto-refresh fallback (polling), Logs pagination.
- **Кеширование max_id в БД** (PR#32 pending) — `last_known_max_id` field в `channels` table ускорит `get_last_messages` с 15 запросов до 1.
- **Structured logging** — если понадобится log aggregation, мигрировать на `structlog` (JSON logs).
- **E2E test с реальным URL** — `web/tests/e2e/mobile.spec.ts` использует nonexistent pattern. E2E не может отправлять посты, integration tests покрывают реальный URL.

## Watch out

- **`EditMessageRequest` в `telethon.tl.functions.messages`, НЕ `telethon.tl.functions.channels`** — спека issue #43 указывала `telethon.tl.functions.channels.EditMessageRequest` (channel param), но в Telethon 1.44 `EditMessageRequest` находится в `messages` и принимает `peer: TypeInputPeer` (НЕ `channel: TypeInputChannel`). `channels.EditMessageRequest` НЕ существует — проверено `python -c "import telethon.tl.functions.channels as c; print([n for n in dir(c) if 'Edit' in n])"` → `['EditAdminRequest', 'EditBannedRequest', 'EditLocationRequest', 'EditPhotoRequest', 'EditTitleRequest']`. Использован `telethon.tl.functions.messages.EditMessageRequest` + `InputPeerChannel(channel_id, access_hash)` (вместо `InputChannel`). См. ADR.
- **`mock_telethon_client` возвращал `MagicMock` для `client` вызова** — `test_edit_message_entities_invokes_raw_api` использует `monkeypatch.setattr(telegram_module, "_get_channel_input", ...)` чтобы изолировать от `_get_channel_input` (который дёргает `client.get_entity`). Без monkeypatch `edit_message_entities` бы пошёл в реальный `get_entity` на mock client → возвращал AsyncMock вместо InputChannel.
- **`MockMessage` расширён `entities: list[object] | None = None`** — `tests/conftest.py:131` MockMessage dataclass получил новое поле (default None) для тестов с entity urls. Существующие тесты не указывают entities → default None → `getattr(m, "entities", None)` в `_entity_urls` возвращает None → `None or []` → `[]` (нет entity urls). Не breaking change.
- **`match_source: "text" | "entity"` в result dict** — `replace_link_in_post` возвращает новый ключ. `replace_link_in_posts` (orchestrator) и `runner._run_job` не проверяют этот ключ (используют `result.get("success")` / `result.get("edited")`), не breaking. Tests могут assert'ить `result["match_source"] == "text"` для диагностики.
- **`entity.url` regex match** — `regex.search(e.url)` (НЕ `regex.match`), т.к. pattern может быть substring в URL (например `https://old\.example\.com` matches `https://old.example.com/path`). Если pattern требует anchor, пользователь сам добавляет `^` / `$`.
- **Integration tests cleanup** — fixtures `test_text_url_msg` / `test_entity_url_msg` `await client.delete_messages(CHANNEL_ID, [msg.id])` в `finally` (НЕ в teardown after yield) — даже если test падает, message удаляется. Если test runner умирает mid-test, message может остаться в канале (требуется ручная очистка).
- **`TELESOFT_TEST_CHANNEL_ID` env override** — default `-1003903711726` (test channel из контекста). Через env var можно указать другой channel для integration tests (не хардкод).
- **Pre-existing advisory warnings** — `state_referenced_locally` на `jobs/[id]/+page.svelte` строки 10-11 (`let job = $state(data.job)`, `let logs = $state(data.logs)`). PR#26/40 documented as intentional. НЕ фиксятся в этом PR.