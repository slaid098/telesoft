# ADR — PR #34: replace-link endpoint uses auto-discovery instead of post URLs

## Статус

Accepted (2026-07-20) — `POST /api/channels/{id}/replace-link` переведён с ручного сбора URL постов на auto-discovery последних N постов канала через `get_last_messages` (PR#32). `ReplaceLinkRequest` = `{pattern, new_link, limit=100}` (limit 1..1000). Backend сам находит посты, regex-фильтрует, редактирует. Снимает UX-блокер PR#14/PR#22 (юзер вручную собирал URLs постов). Дополнительно: retroactive code review PR#32 suggestions учтены (perf improvements в `core/telegram.py`).

## Контекст

PR#22 реализовал `POST /api/channels/{id}/replace-link` с `ReplaceLinkRequest { post_urls: list[str], pattern: str, new_link: str }` — юзер вручную собирает URLs постов через `parse_post_url` (PR#16). Это работало для MVP одного канала с 5-10 постами, но не масштабируется: 20 каналов × 100 постов = 2000 ручных URL-сборов — нереально.

PR#32 добавил `get_last_messages(channel_id, limit)` через `channels.GetMessagesRequest` raw API + binary search max_id (spike PR#30 подтвердил алгоритм). Это снимает ограничение PR#14 (by-ID fetch only) — backend может auto-discover "последние N постов канала" без user-session и без ручных URLs.

Этот PR рефакторит API: `ReplaceLinkRequest` меняется на `{pattern, new_link, limit=100}`, backend сам находит посты через `get_last_messages`, regex-фильтрует по pattern, редактирует. Дополнительно учтены minor suggestions из retroactive code review PR#32:
- `delay` параметром в `_find_max_id` (было `Settings.from_env()` на каждый probe = 15 чтений env, стало 1 чтение в `get_last_messages`).
- Убран trailing sleep после последнего probe.
- Defensive `getattr(entity, "access_hash", 0)` (если `get_entity` вернёт не-Channel).

## Решение

7 изменений по шагам (см. handoff для деталей):

1. **Schemas** (`src/telesoft/schemas/job.py`) — `ReplaceLinkRequest` = `{pattern: str, new_link: str, limit: int = Field(default=100, ge=1, le=1000)}`. `post_urls` удалён. `Field(default=100, ge=1, le=1000)` — Pydantic v2 валидация 1..1000 (422 при нарушении).

2. **link_replacer** (`src/telesoft/core/link_replacer.py`) — добавлены 2 public-функции:
   - `find_posts_with_pattern(messages, pattern) -> list` — regex-фильтр списка Message (НЕ fetch'ит из Telegram). `getattr(m, "text", None) or ""` defensive для `text=None`.
   - `replace_link_in_posts(chat_id, messages, pattern, new_link, on_progress=None) -> dict` — orchestrator, summary `{total, edited, failed, skipped}`. `on_progress` callback для runner'а (publish progress events). НЕ используется в runner (runner сам итерирует + пишет логи + publish events) — public API для future use.

3. **runner** (`src/telesoft/core/runner.py`) — `submit(job_id, chat_id, limit, pattern, new_link)` (вместо `message_ids`). Worker: `get_last_messages(chat_id, limit)` → `find_posts_with_pattern(messages, pattern)` → `total = len(matching)` → `update_job_status(total=total)` → `job_started` event с `total=len(matching)` (НЕ limit) → iterate matching → `replace_link_in_post` + log + progress event → `done`/`completed`. Semaphore + cancel logic — без изменений.

4. **api/routers/jobs.py** — `POST /api/channels/{id}/replace-link` body = новая `ReplaceLinkRequest`. Валидация: channel_id (404) + pattern (422 через `validate_pattern`). `runner.submit(job_id, channel.telegram_id, limit, pattern, new_link)`. `url_parser` import убран.

5. **core/telegram.py perf** — `_find_max_id(channel_input, max_probe_id, delay: float)` принимает `delay` параметром. `get_last_messages` читает `Settings.from_env()` 1 раз, передаёт `settings.telegram_request_delay` в `_find_max_id`. Trailing sleep убран (`if lo <= hi: await asyncio.sleep(delay)`). `_get_channel_input` defensive `getattr(entity, "access_hash", 0)`.

6. **url_parser.py сохранён** — НЕ удалён (для future features), import убран из `jobs.py`. `tests/test_url_parser.py` остаётся зелёным.

7. **Тесты** — `test_api_jobs.py` (новый body, удалены url-тесты, добавлены limit validation + default limit + `_drain_until_settled` helper для pump'а event loop), `test_link_replacer.py` (find_posts_with_pattern + replace_link_in_posts_summary), `test_telegram_client.py` (test_delay_between_requests updated + test_get_last_messages_reads_settings_once), `test_websocket.py` (test_ws_receives_events с auto-discovery), `conftest.py` (mock_telethon_get_last_messages fixture). 115 тестов, coverage 94.24%.

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `replace_link_in_posts` orchestrator НЕ используется в runner — runner сам итерирует matching (нужно publish progress event + write log на каждом шаге). Orchestrator — public API для future use (preview/dry-run).
- `test_get_last_messages_reads_settings_once` stubs `start_client`/`_get_channel_input` — иначе их `from_env` вызовы pollute count (3 вместо 1). Spec intent: "not per-probe (15)", не "literally 1 in whole call stack".
- `_matching_messages(link, count)` helper renamed — принимает literal URL (НЕ regex), т.к. раньше regex-строка с `\.` embedding в text не матчилась.
- `_drain_until_settled` helper — sync TestClient не pump'ит asyncio loop, bg task не успевает до assert.

## Альтернативы

- **Auto-discovery via `get_last_messages` (выбрано)** — backend сам находит последние N постов канала через PR#32. Юзер даёт канал + pattern + new_link + limit. Снимает UX-блокер (2000 ручных URLs → 20 запросов). Использует уже реализованный `get_last_messages` (PR#32) — нулевые новые Telegram-вызовы в этом PR.

- **Keep `post_urls` + add auto-discovery as optional** — `ReplaceLinkRequest { post_urls?: list[str], pattern, new_link, limit?: int }` — либо URLs, либо limit. Усложняет API (два режима), валидацию, тесты. Spec issue #33 явно требует убрать `post_urls` — auto-discovery единственный режим.

- **Frontend собирает URLs из `get_last_messages` preview** — отдельный endpoint "preview posts", frontend показывает список, юзер отмечает, frontend собирает URLs, шлёт `post_urls`. Усложняет frontend (UI для выбора постов), не снимает UX-блокер (юзер всё равно кликает 100 постов × 20 каналов). Backend auto-discovery проще.

- **`delay` как global/module-level (НЕ параметр)** — `delay = Settings.from_env().telegram_request_delay` на module load. Менее testable (monkeypatch module var сложнее чем параметр), и `Settings.from_env()` на module load ломает test fixtures (env vars ещё не set). Параметр + 1 чтение в `get_last_messages` — testable + fast.

- **Trailing sleep оставить** — `await asyncio.sleep(delay)` после каждого probe безусловно (включая последний). Усложняет тесты (extra sleep assertion), экономит 0 времени в production (~1 секунда раз). Убрать — spec issue #33 явно требует, упрощает тесты.

- **Defensive `access_hash` через `hasattr`** — `if hasattr(entity, "access_hash"): ... else: 0`. Многословнее `getattr(entity, "access_hash", 0)`. `getattr` — Pythonic one-liner, эквивалент. Выбрано `getattr`.

- **Удалить `url_parser.py`** — не используется в этом PR. Spec issue #33 явно говорит "НЕ удалять (для future features)". `tests/test_url_parser.py` остаётся зелёным (95% coverage). Удаление — loss of working code без gain.