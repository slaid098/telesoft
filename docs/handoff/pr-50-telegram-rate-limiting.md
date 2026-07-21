---
pr: 50
issue: 49
branch: fix/telegram-rate-limiting
status: ready
created: 2026-07-21
---

# Handoff — PR 50: rate limiting, FloodWait handling, eliminate redundant API calls

## Что сделано

Реализован issue #49 — устранены корневые причины падения replace-link jobs с FloodWait или возвратом 0/0. 5 коммитов, 12 файлов изменено (6 src + 6 test), 125 unit tests green, ruff/mypy — green.

### Фикс 1: `src/telesoft/config.py` + `.env.example`

- Новое поле `telegram_edit_delay: float` в `Settings` (default 5.0) — пауза между успешными edit-ами.
- `from_env()`: `telegram_edit_delay=_get_float("TELEGRAM_EDIT_DELAY", 5.0)`.
- `.env.example`: `TELEGRAM_EDIT_DELAY=5.0`.

### Фикс 2: `src/telesoft/core/telegram.py` — TelegramClient params + retry

TelegramClient constructor (`get_client()`):
```python
TelegramClient(
    session, api_id, api_hash,
    receive_updates=False,
    flood_sleep_threshold=100,   # auto-sleep на FloodWait <= 100s
    auto_reconnect=True,
    connection_retries=100,
    retry_delay=5,
    entity_cache_limit=1000,
)
```

`edit_message` — 3-retry на FloodWaitError (по аналогии с `_fetch_messages_by_ids` из PR#32). `asyncio.sleep(exc.seconds + 1)` между retry, re-raise после 3-й попытки.

`edit_message_entities` — **ЗАМЕНА** raw API `MessagesEditMessageRequest` на high-level `client.edit_message(chat_id, message.id, text=message.text or "", formatting_entities=entities)`. Сигнатура изменилась: `(chat_id, message_id, text, entities)` → `(chat_id, message, entities)`. 3-retry на FloodWait. Удалён `_get_channel_input` вызов (Telethon сам резолвит peer). Удалены импорты `MessagesEditMessageRequest`, `InputPeerChannel`. `InputChannel` сохранён (используется в `_get_channel_input` для `get_last_messages` binary search).

### Фикс 3: `src/telesoft/core/link_replacer.py` — message object + in-place mutation

`replace_link_in_post(chat_id, message, pattern, new_link)` — принимает message object (НЕ re-fetch по ID). Убран `get_message` вызов. Entity URL replacement: `entity.url = new_link` in-place (НЕ создаёт новый `MessageEntityTextUrl`), передаёт исходный `entities` list в `edit_message_entities`. Удалён импорт `MessageEntityTextUrl`.

`replace_link_in_posts` — передаёт `message` object (не `int(message.id)`) в `replace_link_in_post`.

### Фикс 4: `src/telesoft/core/runner.py` + `main.py` — delays

`JobRunner.__init__` — новые параметры `edit_delay: float = 5.0, pre_edit_delay: float = 2.0`.

`_run_job`:
- После `find_posts_with_pattern` (если `total > 0`): `await asyncio.sleep(self._pre_edit_delay)` (2с, discovery→edit transition).
- После каждого успешного edit (`result.get("edited")`): `await asyncio.sleep(self._edit_delay)` (5с). НЕ спать после skip (нет API write).

`main.py` lifespan: `JobRunner(max_concurrency=..., event_bus=..., edit_delay=settings.telegram_edit_delay, pre_edit_delay=2.0)`.

### Фикс 5: Tests

- `tests/conftest.py`: `mock_settings` — `monkeypatch.setenv("TELEGRAM_EDIT_DELAY", "0.0")` + `delenv`. `_install_runner`, `_restore_default_runner`, `mock_runner` — `edit_delay=0.0, pre_edit_delay=0.0`.
- `tests/test_config.py`: `TELEGRAM_EDIT_DELAY` в defaults (5.0), custom (3.5), frozen constructor.
- `tests/test_link_replacer.py`: все тесты передают message object (через `_mk_msg` helper), убраны `get_message` mock'и. Удалён `test_replace_link_in_post_message_not_found` (message всегда передан, нет "not found" пути). Entity test проверяет in-place мутацию `entity.url`.
- `tests/test_telegram_client.py`: `test_edit_message_entities_invokes_raw_api` → `test_edit_message_entities_uses_high_level_api` (проверяет `client.edit_message(formatting_entities=...)` вместо raw API). Добавлены `test_edit_message_retries_on_flood_wait`, `test_edit_message_flood_wait_max_retries_exceeded`, `test_edit_message_entities_retries_on_flood_wait`, `test_edit_message_entities_flood_wait_max_retries_exceeded`.
- `tests/test_api_jobs.py`: `mock_runner` fixture добавлен к тестам, которые submit jobs (`test_replace_link_success`, `test_replace_link_limit_validation`, `test_replace_link_default_limit`) — runner с `edit_delay=0.0` обеспечивает быстрое завершение background tasks.
- `tests/integration/test_real_edit.py`: `replace_link_in_post(CHANNEL_ID, test_text_url_msg, ...)` — передаёт message object вместо `test_text_url_msg.id`.

## Почему

Replace-link jobs падали с FloodWait или возвращали 0/0 (issue #49). Корневые причины:

1. **Нет паузы между edit-ами** — 30 edit-ов подряд без sleep → FloodWait. Фикс: `TELEGRAM_EDIT_DELAY=5.0` между успешными edit-ами + 2с pre-edit delay (discovery→edit transition).
2. **Нет `flood_sleep_threshold`** — Telethon бросал exception вместо auto-sleep на короткие FloodWait (10-30с). Фикс: `flood_sleep_threshold=100` — Telethon auto-sleep'ит на FloodWait ≤100с, не бросая exception.
3. **Нет retry на edit FloodWait** — `edit_message`/`edit_message_entities` не ловили FloodWait, пост сразу marked failed без backoff. Фикс: 3-retry loop с `asyncio.sleep(exc.seconds + 1)`.
4. **Redundant API calls** — `replace_link_in_post` re-fetch'ил message по ID (30 лишних `get_message` запросов), `edit_message_entities` re-resolv'ил channel per edit через `_get_channel_input` (ещё 30 лишних `get_entity`). Фикс: передаём message object (убран `get_message`), используем high-level `client.edit_message(formatting_entities=...)` (Telethon сам резолвит peer, убран `_get_channel_input`).
5. **Raw API вместо `formatting_entities`** — `MessagesEditMessageRequest` требовал `InputPeerChannel` + `access_hash` (дополнительный `get_entity` вызов per edit). High-level `client.edit_message(formatting_entities=...)` делает это сам. In-place мутация `entity.url = new_link` (вместо создания новых `MessageEntityTextUrl` объектов) сохраняет original entity metadata.

## Pending

- **Прогон integration tests локально** — главный агент должен запустить `uv run pytest -m integration` (нужны валидные creds `TELEGRAM_BOT_TOKEN` / `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` + `TELEGRAM_SESSION_STRING` в `.env` + test channel access). Сабагент НЕ прогоняет integration tests. Текущая сессия Telegram может быть expired (`AuthKeyNotFound` при попытке integration tests).
- **`TELEGRAM_EDIT_DELAY` tuning** — default 5.0с между edit-ами. Для каналов с 100+ постами = 500+ секунд (8+ минут). Может потребоваться adaptive delay (меньше для маленьких batch'ей, больше для больших). Низкий приоритет.
- **`pre_edit_delay` hardcoded** — `2.0` в `main.py` и `JobRunner.__init__` default. Можно вынести в `Settings` если потребуется tuning. Низкий приоритет.
- **PR#26 pending items** сохраняются: Edit channel mode, Job retry/delete UI, WebSocket shared client, Job detail auto-refresh fallback, Logs pagination.
- **`Settings.session_path` deprecation** — сохранён для backwards compat (PR#46/48 pending).
- **Pre-existing broken files on main** (`Dockerfile.api`, `docker-compose.yml`) — НЕ включены в этот PR (как и в PR#48).

## Watch out

- **`edit_message_entities` сигнатура изменилась**: `(chat_id, message_id, text, entities)` → `(chat_id, message, entities)`. Любой caller, использующий старую сигнатуру, сломается. Единственный caller — `link_replacer.py` (обновлён в этом PR).
- **In-place entity mutation**: `entity.url = new_link` мутирует исходный message object. Если message object переиспользуется после `replace_link_in_post` (например, в кэше), URL уже изменён. В текущем flow runner не переиспользует messages после edit, но стоит учитывать.
- **`mock_runner` fixture order**: `mock_runner` должен запускаться ПОСЛЕ `authed_client` (который создаёт `app.state.job_runner` в lifespan). В pytest fixture resolution order = order in function signature. `authed_client` должен быть первым в списке параметров. Если `mock_runner` запустится до `authed_client`, он не найдёт `app.state.job_runner` для сохранения prev state, и lifespan перезапишет его runner.
- **`flood_sleep_threshold=100`**: Telethon auto-sleep'ит на FloodWait ≤100с. FloodWait >100с всё ещё бросает exception → попадает в 3-retry loop. Если Telegram выдаёт repeated FloodWait >100с → 3 retry × (sleep+1) = потенциально долгое ожидание. Для critical jobs стоит рассмотреть increase threshold или infinite retry (но для MVP 3-retry достаточно).
- **`entity_cache_limit=1000`**: Telethon кэширует до 1000 entities в памяти. Для каналов с >1000 уникальных entities (редко) — старые entities вытесняются, `get_entity` вызывается заново. Не критично для replace-link flow (entity resolution делегирован Telethon'у в high-level API).
- **`connection_retries=100, retry_delay=5`**: Telethon будет пытаться переподключиться до 100 раз с 5с delay. Если Telegram недоступен (network issue), startup может занять до 500с (8+ минут). Lifespan ловит exception и продолжает без Telegram (`logger.warning`), но задержка может быть заметна.
- **Integration test session**: `tests/integration/test_real_edit.py` `_client()` использует `TelegramClient` с `flood_sleep_threshold` НЕ установленным (default 60). Для consistency можно обновить, но integration tests — standalone (не используют `core/telegram.py` singleton). Низкий приоритет.
