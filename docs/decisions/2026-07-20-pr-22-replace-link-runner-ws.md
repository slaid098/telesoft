---
status: Accepted
date: 2026-07-20
pr: 22
issue: 21
title: Background replace-link runner with EventBus, WebSocket, by-ID fetch and regex substitution
---

# ADR — PR #22: replace-link runner + WS

## Контекст

Issue #21 требует ядро MVP telesoft: эндпоинт `POST /api/channels/{id}/replace-link`
запускает background job, который fetch'ит посты канала by-ID через Telethon bot
client (PR#16), regex-заменяет `pattern` на `new_link` в тексте постов, вызывает
`edit_message` для каждого, пишет результат в `edit_logs` (PR#12). Прогресс
стримится через WebSocket `/api/ws`. Статус/логи/отмена — через REST.

Зависимости: PR#2 (repo), PR#12 (db models: channels/edit_jobs/edit_logs), PR#16
(telegram client + url_parser, by-ID fetch only), PR#18 (auth), PR#20 (channels
CRUD API). Референс: `/root/workspace/media-gen/src/media_gen/core/{runner,events}.py`
+ `api/routers/{jobs,ws}.py` (PR#42, PR#47).

## Решение

**Background runner + EventBus + WS + by-ID fetch + regex замена.**

1. **Link replacer** (`core/link_replacer.py`):
   - `validate_pattern` — `re.compile` для fail-fast на невалидный regex (422 в
     router).
   - `replace_link(text, pattern, new_link) -> (new_text, count)` — `re.sub` +
     `len(re.findall)`.
   - `replace_link_in_post(chat_id, message_id, pattern, new_link) -> dict` —
     fetch через `core.telegram.get_message(chat_id, message_id)` (by-ID, spike
     PR#14 — bots не могут `iter_messages`). Если None → `success=False, error=
     "Message not found"`. Если count==0 → skipped (edit_message НЕ вызывается).
     Иначе `await core.telegram.edit_message(...)` в try/except — success=True/
     edited=True на успех, success=False на исключение (caller решает retry/log).

2. **EventBus** (`core/events.py`):
   - Pub/sub на `asyncio.Queue` per subscriber. `subscribe() -> Queue`,
     `publish(event) -> None` (fan-out через `put_nowait`), `unsubscribe(queue)`.
   - Паттерн 1-в-1 из media-gen `core/events.py`. One instance per app
     (`app.state.event_bus`).

3. **JobRunner** (`core/runner.py`):
   - `asyncio.Semaphore(max_concurrency)` для лимита concurrent edits (Telegram
     rate limits). `max_concurrency=3` default (env `JOBS_MAX_CONCURRENCY`).
   - `submit(job_id, chat_id, message_ids, pattern, new_link)` — `asyncio.create_task(
     self._run_job(...))`, registry `_tasks[job_id] = task`. Все параметры
     передаются явно (НЕ загружаются из БД — отличается от media-gen, telesoft
     `edit_jobs` не имеет JSON-колонок).
   - Worker: `async with sem` → mark running + publish `job_started` → set total →
     loop message_ids: check `_cancelled` → `replace_link_in_post` → update
     progress (edited/failed) → write log → publish `progress`. В конце:
     `done` + `completed` event. CancelledError → `cancelled` event. Exception →
     `failed` event.
   - `cancel(job_id) -> bool` — cooperative: `task.cancel()` + `_cancelled.add(
     job_id)`. Worker проверяет `_cancelled` перед каждым message_id.

4. **Jobs router** (`api/routers/jobs.py`):
   - `router = APIRouter(tags=["jobs"], dependencies=[Depends(require_auth)])`
     БЕЗ prefix — эндпоинт `/api/channels/{channel_id}/replace-link` не подходит
     под `/api/jobs` prefix. Auth на весь роутер (PR#20 паттерн).
   - `POST /api/channels/{id}/replace-link` — validates channel (404), pattern
     (422 через `validate_pattern`), post_urls (422 через `parse_post_urls`),
     chat_id matching (422 через `_resolve_chat_and_ids`). Создаёт `edit_job`
     (`status='pending'`), submit в runner. Возвращает `{job_id, status}` с 201.
   - `GET /api/jobs` — list с filters `channel_id`, `status`, pagination
     `limit`/`offset`.
   - `GET /api/jobs/{id}` — 404 если нет.
   - `GET /api/jobs/{id}/logs` — 404 если job нет, pagination.
   - `POST /api/jobs/{id}/cancel` — 404 если нет, 409 если уже terminal,
     `runner.cancel` + DB update.

5. **WebSocket router** (`api/routers/ws.py`):
   - `@router.websocket("/api/ws")` — auth через `ws_current_user(websocket)`
     (читает `websocket.scope["session"]`). None → `websocket.close(code=4001)`.
   - На connect: `bus.subscribe()` → sender task (`queue.get()` → `send_json`)
     + receive loop (`receive_text()` до disconnect). На `WebSocketDisconnect`:
     cancel sender + `bus.unsubscribe(queue)`.
   - Heartbeat НЕ реализован (MVP, явный пункт в спеке).

6. **Schemas** (`schemas/job.py`):
   - `ReplaceLinkRequest`, `JobResponse` (+ `from_row`), `JobListResponse`,
     `LogResponse` (+ `from_row`), `LogListResponse`, `WsEvent` (+ `from_event`).
   - `now_iso()` — `strftime("%Y-%m-%dT%H:%M:%SZ")` (PR#20 паттерн).

7. **main.py integration**:
   - Lifespan: создаёт `EventBus` + `JobRunner(max_concurrency=
     settings.jobs_max_concurrency, event_bus=event_bus)`, `runner.start()` в
     startup, `runner.stop()` в shutdown (try/except). Сохраняет в
     `app.state.event_bus` / `app.state.job_runner`.
   - `app.include_router(jobs_router)` + `ws_router`.
   - `config.py`: `jobs_max_concurrency: int = 3` (env `JOBS_MAX_CONCURRENCY`).

## Альтернативы

- **Sync endpoint (без background runner)** — BLOCKING. Telegram edits медленные
  (rate limits, десятки постов) → HTTP timeout. Отклонено.
- **Celery / RQ / внешняя queue** — overkill для MVP (single-process, SQLite,
  single admin user). `asyncio.create_task` достаточно. Отклонено.
- **Polling для прогресса (`GET /api/jobs/{id}` каждые N сек)** — realtime UX
  хуже, лишняя нагрузка. WS — event-driven, лучше для UI. Отклонено для
  прогресса, но `GET /api/jobs/{id}` остаётся для snapshot статуса.
- **`iter_messages` / `get_messages(limit=...)` для fetch постов** — запрещено
  для ботов (`BotMethodInvalidError`, spike PR#14). Only by-ID fetch через
  `get_messages(chat_id, ids=[...])`. Отклонено.
- **User session (phone+code) для `iter_messages`** — усложняет auth (нужен
  phone login flow, code input, session management). Бот-админ с by-ID fetch
  + URL parsing — проще. Отклонено для MVP.
- **JWT auth для WS** — session cookie уже есть (PR#18), `ws_current_user`
  читает `websocket.scope["session"]`. JWT — лишний layer. Отклонено.
- **`Depends(require_auth)` для WS** — FastAPI `Depends` для WS-endpoint не
  может читать session cookie через `request.session` (WebSocket не имеет
  `Request`). `ws_current_user(websocket: Any)` — reads `websocket.scope[
  "session"]` напрямую. Отклонено `Depends` для WS.
- **Persist error в `edit_jobs.error` column** — schema из PR#12 НЕ имеет
  `error` column. Добавить миграцию — отдельный PR. Пока error только в event
  bus + logger. Отклонено для этого PR.
- **`submit_job(job_id)` с params из БД (media-gen паттерн)** — telesoft
  `edit_jobs` не имеет JSON-колонок (поля в schema). `submit(job_id, chat_id,
  message_ids, pattern, new_link)` — все параметры явно. Отклонено media-gen
  паттерн.

## Ключевые отклонения от спеки

- **`edit_jobs.error` column не существует** — спека не упоминает error persist,
  но media-gen runner persist'ит error. Telesoft runner НЕ persist'ит error в
  БД (только в event bus + logger). Зафиксировано в handoff. Если понадобится —
  миграция в новом PR.
- **`ws_current_user` вместо `current_user(websocket)`** — media-gen референс
  использует `current_user(websocket)`, но mypy strict в telesoft запрещает
  передавать WebSocket где ожидается Request. Создан `ws_current_user(
  websocket: Any) -> str | None` в `api/auth.py` — reads `websocket.scope[
  "session"]` напрямую.
- **`router = APIRouter(tags=["jobs"], dependencies=[...])` БЕЗ prefix** —
  эндпоинт `/api/channels/{channel_id}/replace-link` не подходит под `/api/jobs`
  prefix. Спека явно предлагает "создать router БЕЗ prefix, указывать полный
  путь в `@router.post(...)`". Реализовано так.

## Ключевые отклонения от media-gen референса

- **`submit(job_id, chat_id, message_ids, pattern, new_link)` vs `submit_job(
  job_id)`** — telesoft `edit_jobs` не имеет JSON-колонок, все параметры
  передаются явно.
- **`ws_current_user` vs `current_user(websocket)`** — mypy strict отклоняет
  media-gen паттерн (WebSocket vs Request).
- **`router` без prefix** — media-gen jobs router имеет `prefix="/api/jobs"`;
  telesoft replace-link endpoint не подходит под этот prefix.
- **Нет retry endpoint** — media-gen имеет `POST /api/jobs/{id}/retry`; telesoft
  MVP не требует (спека не упоминает).
- **Нет delete endpoint** — media-gen имеет `DELETE /api/jobs/{id}`; telesoft
  MVP не требует (спека не упоминает).
- **Нет initial snapshot of running jobs** — media-gen WS отправляет текущие
  running jobs на connect; telesoft MVP не требует (спека не упоминает).

## Ссылки

- Issue: #21
- Spike: PR#14 (`docs/decisions/2026-07-20-pr-14-spike-telethon.md`) — by-ID
  fetch only, bot mode.
- Telegram client: PR#16 (`docs/decisions/2026-07-20-pr-16-telegram-client.md`).
- Auth: PR#18 (`docs/decisions/2026-07-20-pr-18-auth.md`).
- Channels API: PR#20 (`docs/decisions/2026-07-20-pr-20-channels-api.md`).
- DB models: PR#12 (`docs/decisions/2026-07-20-pr-12-db-layer.md`).
- Референс: `/root/workspace/media-gen/src/media_gen/core/{runner,events}.py`
  + `api/routers/{jobs,ws}.py` (PR#42, PR#47).