---
pr: 34
issue: 33
branch: refactor/api/replace-link-auto-discovery
status: ready
created: 2026-07-20
---

# Handoff — PR #34: replace-link endpoint uses auto-discovery instead of post URLs

## Что сделано

Реализован issue #33 — `POST /api/channels/{id}/replace-link` переведён с ручного сбора URL постов на auto-discovery последних N постов канала через `get_last_messages` (PR#32). Юзер даёт канал + pattern + new_link + limit — софт сам находит посты, regex-фильтрует, редактирует. Снимает UX-блокер: для 20 каналов × 100 постов это 20 запросов вместо 2000 ручных URL-сборов.

### Шаг 1: Schemas refactor (`src/telesoft/schemas/job.py`)

- `ReplaceLinkRequest` изменён:
  - OLD: `class ReplaceLinkRequest(BaseModel): post_urls: list[str]; pattern: str; new_link: str`
  - NEW: `class ReplaceLinkRequest(BaseModel): pattern: str; new_link: str; limit: int = Field(default=100, ge=1, le=1000)`
- Добавлен `from pydantic import BaseModel, Field` (раньше был только `BaseModel`).
- Порядок полей: `pattern, new_link, limit` (limit последним — required-поля первыми, по конвенции).
- Docstring обновлён: поясняет, что backend auto-discovers через `get_last_messages`.
- `JobResponse`/`JobListResponse`/`LogResponse`/`LogListResponse`/`WsEvent` — БЕЗ изменений.

### Шаг 2: link_replacer refactor (`src/telesoft/core/link_replacer.py`)

- Сохранены `replace_link(text, pattern, new_link) -> tuple[str, int]`, `validate_pattern(pattern) -> str`, `replace_link_in_post(chat_id, message_id, pattern, new_link) -> dict` — БЕЗ изменений.
- Добавлен `async def find_posts_with_pattern(messages: list[Any], pattern: str) -> list[Any]`:
  - `regex = re.compile(pattern)`, return `[m for m in messages if (getattr(m, "text", None) or "") and regex.search(m.text)]`.
  - НЕ fetch'ит из Telegram — работает с уже полученным списком (от `get_last_messages`).
  - Сообщения с `text=None`/empty — никогда не матчатся (defensive `getattr(m, "text", None) or ""`).
- Добавлен `async def replace_link_in_posts(chat_id, messages, pattern, new_link, on_progress=None) -> dict[str, int]`:
  - Orchestrator: для каждого message → `replace_link_in_post(chat_id, int(message.id), pattern, new_link)`.
  - Summary: `{"total": len(messages), "edited": N, "failed": M, "skipped": K}`.
  - `on_progress: Callable[[int, int, int], Awaitable[None]] | None` — optional callback `await on_progress(edited, failed, total)` после каждого message.
  - `skipped` = success но `edited` не True (count==0 — post без pattern, edit не вызывался).

### Шаг 3: JobRunner refactor (`src/telesoft/core/runner.py`)

- `submit` signature: OLD `submit(job_id, chat_id, message_ids, pattern, new_link)` → NEW `submit(job_id, chat_id, limit, pattern, new_link)`.
- Worker (`_run_job`) алгоритм:
  1. `_mark_running(job_id)` — `update_job_status(status="running")`, проверка что job существует в БД.
  2. `messages = await telegram_module.get_last_messages(chat_id, limit)` — auto-discovery (PR#32).
  3. `matching = await find_posts_with_pattern(messages, pattern)` — regex-фильтр (Шаг 2).
  4. `total = len(matching)` → `_set_total(job_id, total)` — `update_job_status(status="running", total=total)`.
  5. Publish `{"type": "job_started", "job_id": ..., "total": total}` (total = число matching, НЕ limit).
  6. For message in matching: check `_cancelled` → `replace_link_in_post(chat_id, int(message.id), pattern, new_link)` → `_write_log` + `_update_progress` + publish `{"type": "progress", "job_id", "edited", "failed", "total", "message_id"}`.
  7. Done: `_mark_final(job_id, "done")` + publish `{"type": "completed", "job_id", "edited", "failed", "total"}`.
- `asyncio.Semaphore(max_concurrency)` — ОСТАВЛЕН (concurrent edits limit).
- Cancel logic — БЕЗ изменений (`_cancelled` set, cooperative `raise asyncio.CancelledError` перед каждым message).
- `replace_link_in_posts` orchestrator НЕ используется в runner — runner сам итерирует matching (нужно publish progress event на каждом шаге + write log в БД, orchestrator так не умеет).

### Шаг 4: Jobs router refactor (`src/telesoft/api/routers/jobs.py`)

- `POST /api/channels/{channel_id}/replace-link` body: `ReplaceLinkRequest` (новая — pattern, new_link, limit).
- Валидация: `validate_pattern(payload.pattern)` → 422 если невалидный regex; `_get_channel_or_404(db, channel_id)` → 404 если канал не существует.
- `job_model.create_job(db, channel_id, pattern, new_link, created_at=now_iso())` → `runner.submit(job_id=int(row["id"]), chat_id=int(channel["telegram_id"]), limit=payload.limit, pattern=payload.pattern, new_link=payload.new_link)`.
- Return 201 `{"job_id": int(row["id"]), "status": "pending"}`.
- `url_parser` import УБРАН (раньше использовался для парсинга `post_urls` → message_ids + проверка что URL принадлежит каналу — теперь не нужно, backend сам находит посты).
- `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/logs`, `POST /api/jobs/{id}/cancel` — БЕЗ изменений.

### Шаг 5: core/telegram.py — perf improvements (retroactive review PR#32)

- `_find_max_id(channel_input, max_probe_id, delay: float)` — `delay` теперь параметр (раньше читал `Settings.from_env()` на каждый probe = 15 чтений env).
- `get_last_messages` — `settings = Settings.from_env()` ОДИН раз в начале, передаёт `settings.telegram_request_delay` в `_find_max_id`.
- Убран trailing sleep: `if lo <= hi: await asyncio.sleep(delay)` (после последнего probe, когда `lo > hi` — выход без sleep).
- `_get_channel_input` — `getattr(entity, "access_hash", 0)` defensive (если `get_entity` вернёт не-Channel, `access_hash` может не быть → 0 вместо AttributeError).

### Шаг 6: url_parser — оставлен, не используется

- `src/telesoft/core/url_parser.py` — НЕ удалён (может пригодиться для future features).
- `tests/test_url_parser.py` — НЕ удалён (тесты для url_parser остаются зелёными).
- Import из `jobs.py` — убран.

### Шаг 7: Тесты

- `tests/test_api_jobs.py`:
  - `_matching_messages(link, count)` helper renamed: принимает literal URL (НЕ regex), embeds в text — раньше принимал regex-строку с `\.` → regex не матчился.
  - `_drain_until_settled(client, job_id, rounds=50)` helper — poll `GET /api/jobs/{id}` пока status не terminal, pump event loop через `GET /health` (sync TestClient не pump'ит asyncio loop автоматически, bg task не успевает выполниться до assert).
  - `test_replace_link_success` — body `{pattern, new_link, limit: 100}`, mock `get_last_messages` возвращает 3 matching + 1 non-match, assert 201.
  - `test_replace_link_invalid_channel` — 404, `get_last_messages` не вызывается.
  - `test_replace_link_invalid_pattern` — 422, `get_last_messages` не вызывается.
  - `test_replace_link_limit_validation` — NEW: `limit=0` → 422, `limit=1001` → 422, `limit=100` → 201.
  - `test_replace_link_default_limit` — NEW: body без `limit` → default 100. Poll job до terminal, assert `get_last_messages` awaited once с `called_limit == 100`.
  - `test_replace_link_url_wrong_channel` / `test_replace_link_invalid_url` — УДАЛЕНЫ (URL-валидации больше нет).
  - `test_replace_link_requires_auth` — 401 (БЕЗ изменений body, но `post_urls` убран, добавлен `limit` опционально).
- `tests/test_link_replacer.py`:
  - `test_find_posts_with_pattern_filters_matching` — 4 messages (matching, non-match, empty, None-text) → возвращает только matching.
  - `test_find_posts_with_pattern_no_matches` — empty list.
  - `test_replace_link_in_posts_summary` — orchestrator с 3 messages (2 matching + 1 non-match), `_on_progress` callback, asserts summary `{total: 3, edited: 2, failed: 0, skipped: 1}` + `progress_calls[-1] == (2, 0, 3)`.
  - `test_replace_link_in_posts_without_progress_callback` — orchestrator без callback работает.
- `tests/test_telegram_client.py`:
  - `test_delay_between_requests` — обновлён: `_find_max_id` принимает `delay` параметром, `Settings.from_env()` НЕ вызывается внутри.
  - `test_get_last_messages_reads_settings_once` — NEW: monkeypatch `Settings.from_env` с counter, stub `start_client`/`_get_channel_input` (чтобы их `from_env` вызовы не pollute count), assert `from_env_calls == 1` после `get_last_messages`.
- `tests/test_websocket.py`:
  - `test_ws_receives_events` — body `{pattern, new_link, limit}`, mock `get_last_messages` возвращает 1 matching MockMessage с literal URL в text (НЕ regex-строка), asserts `job_started` + `progress` + `completed`.
- `tests/conftest.py`:
  - `mock_telethon_get_last_messages` fixture — `AsyncMock(return_value=[])`, monkeypatch `telegram_module.get_last_messages`. Тесты переопределяют `return_value` для конкретных сценариев.

Все 115 тестов проходят, coverage 94.24% (требование ≥80%). ruff check + ruff format + mypy strict — зелёные.

## Почему

Spike PR#30 + production PR#32 добавили `get_last_messages(channel_id, limit)` через `channels.GetMessagesRequest` raw API + binary search max_id. Это снимает ограничение PR#14 (by-ID fetch only — юзер вручную собирал URLs постов через `parse_post_url`). Для 20 каналов × 100 постов = 2000 ручных URL-сборов — нереально. Теперь backend сам находит последние N постов канала — юзер даёт канал + pattern + new_link + limit.

Дополнительно учтены minor suggestions из retroactive code review PR#32:
- `delay` параметром в `_find_max_id` (было `Settings.from_env()` на каждый probe = 15 чтений env, стало 1 чтение в `get_last_messages`).
- Убран trailing sleep после последнего probe (когда `lo > hi` — выход без sleep, экономит ~1 секунду).
- Defensive `getattr(entity, "access_hash", 0)` (если `get_entity` вернёт не-Channel, `access_hash` может не быть → 0 вместо AttributeError).

## Pending

- **Frontend UI обновить** — `web/src/routes/channels/[id]/+page.svelte` (PR#26) использует `ReplaceLinkForm` с `postUrls` textarea. Нужно убрать textarea, добавить `limit` number input (default 100, 1..1000). Backend уже готов (этот PR). Отдельный PR (frontend).
- **Кеширование max_id в БД** — после первого binary search (~14 probes) можно кешировать `max_id` в `channels` table, чтобы при повторных `get_last_messages` пропускать binary search. Поле `last_known_max_id: int` + обновление после каждого вызова. Ускоряет с 15 до 1 запроса. Pending (PR#32 handoff уже упоминал).
- **Pattern preview** — endpoint "preview pattern match" — `POST /api/channels/{id}/preview-pattern { pattern, limit }` → возвращает N matching posts БЕЗ редактирования (dry-run). Полезно для UI: юзер видит какие посты попадут, потом подтверждает replace. Pending.

## Watch out

- **`job_started` event total = len(matching), НЕ limit** — spec issue #33 явно требует. `total` = число постов где pattern найден (после regex-фильтра), а не `limit` (верхняя граница auto-discovery). UI должен показывать "Found 3 matching posts out of 100 scanned" — `total` в event = 3, `limit` не в event (caller знает свой limit).
- **`replace_link_in_posts` orchestrator НЕ используется в runner** — runner сам итерирует matching потому что нужно: (a) publish progress event на каждом шаге, (b) write log в БД на каждом шаге, (c) check `_cancelled` перед каждым message. Orchestrator `replace_link_in_posts` — public API для future use (e.g. preview/dry-run). Не дублировать логику в runner → runner использует `replace_link_in_post` напрямую + свои helpers.
- **`_matching_messages(link, count)` helper в тестах** — принимает literal URL (НЕ regex). Раньше принимал regex-строку с `\.` → text содержал `\.` буквально → regex `https://old\.example\.com` (matches `.`) не матчит `\.example\.com` (literal backslash). Фикс: `link` параметр = plain URL, текст = `f"see {link} here"`, pattern передаётся отдельно в body. Тесты, использующие `_matching_messages`: `test_replace_link_success`, `test_replace_link_limit_validation`, `test_replace_link_default_limit`.
- **`_drain_until_settled(client, job_id)` helper** — sync `TestClient` НЕ pump'ит asyncio event loop автоматически между requests. Background task (`runner.submit` → `asyncio.create_task`) может не успеть выполниться к моменту assert. Helper: poll `GET /api/jobs/{id}` пока status terminal + `GET /health` между polls (pump loop). Без этого `mock_telethon_get_last_messages.assert_awaited_once()` падает (0 awaits — bg task не успел).
- **`test_get_last_messages_reads_settings_once` stubs `start_client`** — `get_last_messages` → `_get_channel_input` → `start_client` → `Settings.from_env()` (bot token). Чтобы изолировать count `from_env` вызовов внутри `get_last_messages` (1 раз для delay), нужно stub `start_client` И `_get_channel_input`. Иначе count = 3 (get_client + start_client + get_last_messages), assertion `== 1` падает. Spec intent: "not per-probe (15)", не "literally 1 in whole call stack".
- **`delay` параметр в `_find_max_id`** — `delay: float` (НЕ `int`), `settings.telegram_request_delay` — float (default 1.0). Передаётся из `get_last_messages` (1 чтение `Settings.from_env()`), НЕ читается внутри `_find_max_id`. Убирает 15× env-reads на каждый `_find_max_id` вызов.
- **Trailing sleep removed** — `if lo <= hi: await asyncio.sleep(delay)` (после probe, перед next iteration). Когда `lo > hi` (binary search done) — выход без sleep. Экономит 1 sleep (~1 секунду) после последнего probe.
- **Defensive `getattr(entity, "access_hash", 0)`** — `get_entity` может вернуть `Channel`/`Chat`/`User`. У `Channel` есть `access_hash`, у `User` — есть, у некоторых stub'ов — может не быть. `getattr(entity, "access_hash", 0)` → 0 если атрибута нет (вместо `AttributeError`). `InputChannel(id, 0)` — Telethon может reject'нуть, но это лучше краша на AttributeError.
- **`url_parser.py` сохранён** — НЕ удалён. Может пригодиться для future features (e.g. single-post replace по URL). Import убран из `jobs.py`, но `tests/test_url_parser.py` остаётся зелёным (тесты покрывают 95% url_parser).
- **Coverage 94.24%** — runner.py 80% (cancelled/failed paths не все покрыты), telegram.py 92%, link_replacer.py 97%, jobs.py 100%. Все ≥80% gate.
- **6 коммитов** — schemas → link_replacer → runner → api → telegram perf → tests. Логическая последовательность: каждый коммит self-contained, можно revert по отдельности. Без `docs(handoff)` коммита (handoff идёт отдельно после PR номера).
EOF