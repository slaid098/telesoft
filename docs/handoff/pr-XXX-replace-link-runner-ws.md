---
pr: XXX
issue: 21
branch: feat/jobs/replace-link-runner-ws
status: ready
created: 2026-07-20
---

# Handoff — PR #XXX: replace-link endpoint with background runner and websocket

## Что сделано

Реализован issue #21 — ядро MVP telesoft: эндпоинт `POST /api/channels/{id}/replace-link`
запускает background job, который fetch'ит посты канала by-ID через Telethon bot
client (PR#16), regex-заменяет `pattern` на `new_link` в тексте постов, вызывает
`edit_message` для каждого поста и пишет результат в `edit_logs` (PR#12). Прогресс
стримится через WebSocket `/api/ws` (события `job_started`/`progress`/`completed`/
`failed`/`cancelled`). Статус и логи доступны через `GET /api/jobs/{id}` и
`GET /api/jobs/{id}/logs`. Отмена — `POST /api/jobs/{id}/cancel`.

### Шаг 1: Link replacer (`src/telesoft/core/link_replacer.py`)

- `validate_pattern(pattern: str) -> str` — `re.compile` для проверки; `ValueError`
  при невалидном regex.
- `replace_link(text, pattern, new_link) -> tuple[str, int]` — `re.sub` + `len(re.findall)`
  для подсчёта. Бросает `re.error` при невалидном pattern.
- `replace_link_in_post(chat_id, message_id, pattern, new_link) -> dict[str, Any]` —
  fetch через `core.telegram.get_message` (by-ID, spike PR#14). Если None →
  `{"success": False, "error": "Message not found"}`. Если `count == 0` → skipped
  (edit_message НЕ вызывается). Иначе `await core.telegram.edit_message(...)` в
  try/except; success=True/edited=True на успех, success=False на исключение.
  `text = message.text or ""` (media-only posts → text=None → skipped).

### Шаг 2: EventBus + JobRunner (`src/telesoft/core/events.py`, `core/runner.py`)

- `EventBus` — pub/sub на `asyncio.Queue` per subscriber. `subscribe()`/`publish()`/
  `unsubscribe()`. Паттерн 1-в-1 из media-gen `core/events.py`.
- `JobRunner`:
  - `__init__(*, max_concurrency: int = 3, event_bus: EventBus | None = None)`.
  - `start()` — создаёт `asyncio.Semaphore(max_concurrency)`. Idempotent.
  - `stop()` — отменяет все задачи, await cleanup, очищает registry + semaphore.
  - `submit(job_id, chat_id, message_ids, pattern, new_link)` — кладёт задачу в
    `asyncio.create_task`, registry `_tasks[job_id] = task`.
  - `cancel(job_id) -> bool` — добавляет job_id в `_cancelled` set + `task.cancel()`.
  - Worker (`_run_job`): `async with sem` → mark running + publish `job_started` →
    set total → loop по message_ids: проверка `_cancelled` → `replace_link_in_post` →
    update progress (edited/failed) → write log → publish `progress`. В конце:
    `done` + `completed` event. На `CancelledError` → `cancelled` event + re-raise.
    На Exception → `failed` event.
  - `finally` — `_tasks.pop(job_id, None)` + `_cancelled.discard(job_id)`.

### Шаг 3: Jobs router (`src/telesoft/api/routers/jobs.py`)

- `router = APIRouter(tags=["jobs"], dependencies=[Depends(require_auth)])` БЕЗ
  prefix — полный путь указывается в `@router.post("/api/channels/{channel_id}/replace-link")`.
- `POST /api/channels/{channel_id}/replace-link` — body `ReplaceLinkRequest(post_urls,
  pattern, new_link)`. Валидация: channel 404, pattern 422 (через `validate_pattern`),
  post_urls 422 (через `parse_post_urls`). `_resolve_chat_and_ids` сверяет parsed
  URL chat_id/username с `channel.telegram_id`/`channel.username` (422 при
  mismatch). Создаёт `edit_job` в БД (`status='pending'`), submit в runner.
  Возвращает `{"job_id": ..., "status": "pending"}` с 201.
- `GET /api/jobs` — query `channel_id`, `status` (alias), `limit` (1-100), `offset`.
  `JobListResponse`.
- `GET /api/jobs/{job_id}` — 404 если нет. `JobResponse` с progress.
- `GET /api/jobs/{job_id}/logs` — 404 если job нет. Query `limit` (1-500), `offset`.
  `LogListResponse`.
- `POST /api/jobs/{job_id}/cancel` — 404 если нет, 409 если уже terminal
  (`done`/`failed`/`cancelled`). `runner.cancel(job_id)` + update DB status.

### Шаг 4: WebSocket router (`src/telesoft/api/routers/ws.py`)

- `router = APIRouter(tags=["ws"])` — без auth dependency на роутере (WS не работает
  с `Depends` через cookie).
- `@router.websocket("/api/ws")` — `ws_current_user(websocket)` check (через
  `websocket.scope["session"]`); None → `websocket.close(code=4001)` (custom
  application-level unauthenticated). Иначе `websocket.accept()` →
  `bus.subscribe()` → sender task (`_forward_events` loop: `queue.get()` →
  `websocket.send_json({"type", "data"})`) + receive loop (`_drain_client`:
  `receive_text()` пока клиент не отключится). На `WebSocketDisconnect` —
  cancel sender + `bus.unsubscribe(queue)`.
- Heartbeat НЕ реализован (MVP, явный пункт в спеке).

### Шаг 5: Schemas (`src/telesoft/schemas/job.py`)

- `ReplaceLinkRequest(post_urls: list[str], pattern: str, new_link: str)`.
- `JobResponse(id, channel_id, pattern, new_link, status, total, edited, failed,
  created_at, completed_at: str | None)` + `from_row(cls, row: JobRow)`.
- `JobListResponse(jobs: list[JobResponse], total: int)`.
- `LogResponse(id, job_id, message_id, old_text: str | None, success, error: str | None,
  edited_at)` + `from_row`.
- `LogListResponse(logs: list[LogResponse], total: int)`.
- `WsEvent(type: str, job_id: int | None = None, ...)` — опциональные поля для
  разных event types + `from_event(event)` classmethod.
- `now_iso()` — `datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` (с `Z`,
  паттерн из PR#20).

### Шаг 6: Интеграция в main.py и config.py

- `config.py`: добавлено `jobs_max_concurrency: int = 3` (env `JOBS_MAX_CONCURRENCY`).
- `main.py` lifespan: создаёт `EventBus` + `JobRunner(max_concurrency=
  settings.jobs_max_concurrency, event_bus=event_bus)`, `runner.start()` в startup,
  `runner.stop()` в shutdown (try/except). Сохраняет в `app.state.event_bus` и
  `app.state.job_runner`. `app.include_router(jobs_router)` + `ws_router`.
- `test_config.py` обновлён — env vars list + `Settings(...)` ctor + assertions
  для нового поля.

### Шаг 7: Тесты

- `tests/test_link_replacer.py` — 10 тестов: replace_link (basic/multiple/no-match/
  invalid-pattern), validate_pattern (valid/invalid), replace_link_in_post
  (success/not-found/no-replacements/edit-fails/empty-text).
- `tests/test_api_jobs.py` — 14 тестов: replace-link (success/invalid-channel/
  invalid-pattern/invalid-url/url-wrong-channel/requires-auth), list (2 jobs +
  filter-by-channel), get (by-id/not-found), logs (with-logs/not-found),
  cancel (success/already-done), jobs-endpoints-requires-auth.
- `tests/test_websocket.py` — 8 тестов: ws-requires-auth, ws-receives-events
  (job_started/progress/completed), ws-disconnect-unsubscribes,
  ws-publish-event-directly, EventBus unit (subscribe/publish/unsubscribe,
  unsubscribe-idempotent), JobRunner unit (start-idempotent,
  cancel-returns-false-for-unknown).
- `tests/conftest.py` — добавлены фикстуры:
  - `mock_telethon_get_message` — monkeypatch `core.telegram.get_message` →
    AsyncMock(return_value=mock_message).
  - `mock_telethon_edit_message` — monkeypatch `core.telegram.edit_message` →
    AsyncMock(return_value=None).
  - `mock_runner` — заменяет `app.state.job_runner` + `app.state.event_bus` на
    свежкие in-memory экземпляры, restore в teardown.
  - Хелперы `_install_runner` / `_restore_default_runner` (из media-gen паттерна).
  - `mock_settings` — добавлен `JOBS_MAX_CONCURRENCY` в env delenv list.

## Почему

Ядро MVP telesoft — замена ссылок в постах канала через бота-админа. Юзер даёт
список post URLs + old_pattern (regex) + new_link, софт fetch'ит посты by-ID,
regex-заменяет, edit'ит каждый пост. Background runner нужен чтобы не блокировать
HTTP-запрос (Telegram rate limits, десятки постов). EventBus + WS — realtime
прогресс для фронтенда (без polling). By-ID fetch — единственный способ для
ботов (spike PR#14: `iter_messages`/`get_messages(limit=...)` запрещены для
ботов, `BotMethodInvalidError`). Парсинг post URLs через `core.url_parser`
(PR#16) — юзер даёт URL, софт извлекает message_id и проверяет принадлежность
к каналу. Auth на все эндпоинты через `Depends(require_auth)` на роутере (DRY,
PR#20 паттерн). WS auth через session cookie — `ws_current_user` читает
`websocket.scope["session"]` (Starlette SessionMiddleware кладёт туда signed
cookie data).

## Pending

- **Frontend jobs UI** — список jobs, запуск replace-link из UI, WS-стриминг
  прогресса. Отдельный issue.
- **Job retry** — повторный запуск failed/cancelled job. Отдельный issue (media-gen
  имеет retry, telesoft MVP не требует).
- **Job delete** — DELETE /api/jobs/{id} для очистки истории. Отдельный issue.
- **Heartbeat для WS** — ping/pong для отслеживания живых соединений. Сейчас
  disconnect детектится через `receive_text` исключение.
- **Edit logs API pagination total** — сейчас `total` = `len(logs)` (текущая
  страница); для правильной пагинации нужен `count_logs` в model. MVP достаточно.

## Watch out

- **`Depends(require_auth)` НЕ работает для WebSocket** — FastAPI `Depends` для
  WS-endpoint не может читать session cookie через `request.session` (WebSocket
  не имеет `Request`). Решение: `ws_current_user(websocket)` читает
  `websocket.scope["session"]` напрямую (Starlette SessionMiddleware кладёт
  session data в scope). Без сессии → `websocket.close(code=4001)` (custom code,
  application-level unauthenticated). Это отклонение от media-gen референса,
  который использовал `current_user(websocket)` — в telesoft mypy strict
  запрещает передавать WebSocket где ожидается Request.
- **`router = APIRouter(tags=["jobs"], dependencies=[Depends(require_auth)])` БЕЗ
  prefix** — эндпоинт `/api/channels/{channel_id}/replace-link` не подходит под
  `/api/jobs` prefix. Решение: роутер без prefix, полный путь в `@router.post(...)`.
  Auth dependency на роутере применяется ко всем эндпоинтам (DRY, PR#20 паттерн).
- **`edit_jobs` таблица НЕ имеет `error` column** — schema из PR#12 (issue #11)
  имеет `status`, `total`, `edited`, `failed`, `created_at`, `completed_at`, но
  НЕТ `error`. Runner НЕ persist'ит error в БД (только в event bus + logger).
  Если `error` column понадобится — миграция в новом PR.
- **`runner.cancel(job_id)` — cooperative cancellation** — `task.cancel()` +
  `_cancelled` set. Worker loop проверяет `if job_id in self._cancelled: raise
  CancelledError` перед каждым message_id. Сancellation между edits — между
  post fetch'ами НЕ прерывается (Telethon call уже в полёте). Для MVP достаточно
  (Telegram edits быстрые).
- **`submit(job_id, chat_id, message_ids, pattern, new_link)` — все параметры
  передаются в runner, НЕ загружаются из БД** — отличается от media-gen, где
  `submit_job(job_id)` загружает params из `params_json`/`channel_ids_json`.
  Telesoft `edit_jobs` не имеет JSON-колонок (поля в schema), runner получает
  всё на старте. `chat_id` = `channel.telegram_id` (runner не знает про
  channels table).
- **`_resolve_chat_and_ids` — username vs telegram_id matching** — parsed URL
  для public channel возвращает `(username: str, msg_id)`, для private —
  `(chat_id: int, msg_id)`. Сверка: `isinstance(identifier, int)` → private
  (сравнение с `channel.telegram_id`), иначе public (сравнение с
  `channel.username`). 422 при mismatch. `chat_id` для runner = `channel.telegram_id`
  всегда (Telethon принимает и int, и username, но int надёжнее — не требует
  resolve_entity).
- **`mock_telethon_get_message` / `mock_telethon_edit_message` — module-level
  monkeypatch** — `monkeypatch.setattr(telegram_module, "get_message", AsyncMock)`.
  Это заменяет функцию в модуле `core.telegram`, так что `link_replacer.py`
  (который импортирует `telegram_module` и вызывает `telegram_module.get_message`)
  видит mock. НЕ нужно patch'ить `core.link_replacer.telegram_module` —
  `link_replacer` использует `from telesoft.core import telegram as
  telegram_module`, monkeypatch на `telegram_module.get_message` меняет атрибут
  модуля, виден всем importer'ам.
- **`mock_runner` fixture НЕ isolates test from real runner** — `mock_runner`
  создаёт real `JobRunner` с fresh `EventBus`, но `submit` запускает real
  `_run_job` (которая вызывает `replace_link_in_post` → Telethon mock). Если
  нужен no-op runner — override `submit` в тесте или используй `_install_runner`
  с custom work_fn (media-gen паттерн). Для API tests (только 201 + job_id
  check) real runner OK — Telethon mock'и возвращают success.
- **`test_replace_link_success` НЕ asserts `status == "pending"`** — после
  POST `runner.submit` запускает background task, которая может завершиться
  до возврата response (Telethon mock'и мгновенны). Тест только проверяет
  201 + `job_id` + initial `status` ("pending" в response body, т.к. DB row
  создан до submit). Гонка между response return и task start — OK, response
  формируется до `runner.submit` (no wait).
- **`mock_telethon_edit_message` return_value=None** — `core.telegram.edit_message`
  возвращает `Message`, но `link_replacer.replace_link_in_post` игнорирует
  return value (только success/edited в result dict). None — OK для mock.
- **`WsEvent.from_event(event)` — kwargs из event.data** — `Event.data` —
  `dict[str, object]`, WsEvent fields — specific (job_id, edited, failed, total,
  message_id, error). Extra keys в data → Pydantic v2 по умолчанию ignore
  extra fields (NO `model_config = ConfigDict(extra="forbid")`). Если key
  совпадает с field name — Pydantic coerces. `type` — отдельный positional
  field, не в data.
- **Coverage 94.08%** — `core/runner.py` 80% (uncovered: defensive `assert sem
  is not None`, `is_running`/`get_task`/`active_count` методы, exception path в
  `_mark_final` без error column). `api/routers/jobs.py` 95% (uncovered:
  defensive `assert row is not None` после `_get_job_or_404`, username match
  branch в `_resolve_chat_and_ids`). `schemas/job.py` 94% (uncovered:
  `WsEvent.from_event` classmethod — tested via integration, не unit). Общий
  gate ≥80% пройден.
- **mypy strict** — `ws_current_user(websocket: Any) -> str | None` — `Any`
  для WebSocket (избегаем import WebSocket в auth.py, чтобы не тащить fastapi
  dependency в auth module). `cast("JobRunner", runner)` в `get_runner` —
  mypy-safe. `runner._semaphore` access в tests — `SLF001` не в ruff select.
- **ruff** — `B008` (Depends в default args) добавлен в `per-file-ignores`
  для `src/telesoft/api/routers/*` (тот же подход что в media-gen). `TRY301`
  (raise в inner function) — `# noqa: TRY301` на `raise asyncio.CancelledError`
  в worker loop (cooperative cancellation, нельзя вынести в helper).