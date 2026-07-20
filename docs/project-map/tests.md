---
module: tests
purpose: Backend + frontend unit tests
key_files:
  - tests/conftest.py — fixtures: mock_settings, mock_db, create_channel/create_job factories, mock_message, mock_telethon_client, mock_telethon_get_message, mock_telethon_edit_message, mock_runner, authed_client
  - tests/test_health.py — TestClient → /health 200
  - tests/test_config.py — Settings: defaults, custom env, frozen check
  - tests/test_db.py — DB connection layer (6 тестов: file/idempotent/pragmas/schema/get_db/noop-close)
  - tests/test_models_channel.py — channels CRUD (7 тестов: CRUD + UNIQUE + whitelist)
  - tests/test_models_job.py — edit_jobs CRUD (5 тестов: CRUD + filters + CASCADE)
  - tests/test_models_log.py — edit_logs CRUD (4 теста: CRUD + pagination + CASCADE)
  - tests/test_telegram_client.py — bot-mode Telethon client wrapper (10 тестов: singleton/idempotent/by-ID fetch/batch/edit/resolve/bot-info/stop)
  - tests/test_url_parser.py — URL parser (9 тестов: public/private/comment/invalid/non-t.me/batch/index/is_valid)
  - tests/test_auth.py — session-based auth (8 тестов: login success/invalid, logout requires-auth/success, me requires-auth/after-login, session persists, concurrent sessions independent)
  - tests/test_api_channels.py — channels CRUD API (14 тестов: list empty/all/active_only, create success/duplicate 409/requires_auth, get by_id/not_found 404, update success/not_found 404/no_fields 422, delete success 204/not_found 404/cascade jobs+logs)
  - tests/test_link_replacer.py — link replacer (11 тестов: replace_link basic/multiple/no-match/invalid-pattern, validate_pattern valid/invalid, replace_link_in_post success/not-found/no-replacements/edit-fails/empty-text)
  - tests/test_api_jobs.py — jobs API (15 тестов: replace-link success/invalid-channel/invalid-pattern/invalid-url/url-wrong-channel/requires-auth, list 2-jobs/filter-by-channel, get by-id/not-found, logs with-logs/not-found, cancel success/already-done, jobs-endpoints-requires-auth)
  - tests/test_websocket.py — WebSocket + EventBus + JobRunner (8 тестов: ws-requires-auth, ws-receives-events, ws-disconnect-unsubscribes, ws-publish-event-directly, EventBus subscribe/publish/unsubscribe, EventBus unsubscribe-idempotent, JobRunner start-idempotent, JobRunner cancel-returns-false-for-unknown)
  - web/src/tests/setup.ts — import @testing-library/svelte; afterEach(vi.restoreAllMocks)
  - web/src/tests/LayoutHarness.svelte — обёртка для +layout.svelte в тестах (передаёт data, рендерит child slot)
  - web/src/tests/login.test.ts — 3 теста: form render, submit+redirect, 401 error
  - web/src/tests/channels.test.ts — 9 тестов: 3 rows/empty/delete + 3 Add button + 3 ChannelForm
  - web/src/tests/replace-link.test.ts — 4 теста: disabled, URLs empty, invalid regex, submit+redirect
  - web/src/tests/jobs.test.ts — 5 тестов: render, cancel, WS progress, WS completed refetch, WS ignore other job_ids
  - web/src/tests/layout.test.ts — 3 теста: Channels nav, Logout button, username display
  - web/src/tests/api.test.ts — 2 теста: query serialization, ApiError on non-ok
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# tests — backend + frontend

## Backend tests (`tests/`)

```
tests/
├── __init__.py              # Пустой — package marker
├── conftest.py              # Fixtures: mock_settings (sync, monkeypatch env — SECRET_KEY 32+ chars, ADMIN_PASSWORD="secret", JOBS_MAX_CONCURRENCY в delenv list), mock_db (async, yields aiosqlite.Connection), create_channel/create_job (async factories, PEP 695 ChannelFactory/JobFactory), MockMessage dataclass, mock_message, mock_telethon_client (patch TelegramClient конструктор, реальный get_client/start_client упражняется против mock), mock_telethon_get_message (monkeypatch core.telegram.get_message → AsyncMock(return_value=mock_message)), mock_telethon_edit_message (monkeypatch core.telegram.edit_message → AsyncMock(return_value=None)), mock_runner (заменяет app.state.job_runner + app.state.event_bus на fresh in-memory, restore в teardown), authed_client (async, TestClient(app) as ctx mgr + POST /api/auth/login → залогиненная сессия). Хелперы _install_runner/_restore_default_runner (media-gen паттерн)
├── test_health.py           # TestClient → GET /health → 200 {"status":"ok"}
├── test_config.py           # 3 теста: defaults (env не задан), custom env (ADMIN_USERNAME и др.), frozen check (FrozenInstanceError)
├── test_db.py               # 6 тестов: init_db_creates_file, init_db_idempotent, pragmas_set (WAL+foreign_keys), schema_created (sqlite_master), get_db_yields_connection, close_db_noop_when_uninitialized
├── test_models_channel.py  # 7 тестов: create+get, get_by_telegram_id, list_active_only, update (title/username/is_active), update_rejects_unknown_field (ValueError), delete, unique_telegram_id_constraint (IntegrityError)
├── test_models_job.py       # 5 тестов: create+get, list_filter_by_channel, list_filter_by_status, update_job_status, delete_job_cascade_logs (FK CASCADE)
├── test_models_log.py       # 4 теста: create+list, list_limit_offset (pagination), delete_logs (returns count), delete_channel_cascade_jobs_logs (FK CASCADE channel→jobs→logs)
├── test_telegram_client.py  # 10 тестов: get_client_singleton, start_client_idempotent (await_count), get_message_by_id, get_message_returns_none_for_missing, get_messages_batch_filters_none, edit_message_success, edit_message_propagates_error (BadRequestError→RPCError), resolve_entity, get_bot_info, stop_client_resets_state
├── test_url_parser.py       # 9 тестов: public channel, private channel (-100<internal_id>), ?comment= query, invalid format, non-t.me domain, private non-digit, batch, batch with index, is_valid_post_url true/false
├── test_auth.py             # 8 тестов: login_success, login_invalid_credentials, logout_requires_auth, logout_success, me_requires_auth, me_after_login, session_persists_across_requests, concurrent_sessions_independent
├── test_api_channels.py     # 14 тестов: list_channels_empty, list_channels_returns_all, list_channels_active_only, create_channel_success, create_channel_duplicate_telegram_id (409), create_channel_requires_auth (401, отдельный TestClient без authed_client), get_channel_by_id, get_channel_not_found (404), update_channel_success, update_channel_not_found (404), update_channel_no_fields (422), delete_channel_success (204), delete_channel_not_found (404), delete_channel_cascade_jobs_logs (FK CASCADE через db_handle fixture)
├── test_link_replacer.py    # 11 тестов: replace_link_basic, replace_link_multiple, replace_link_no_match, replace_link_invalid_pattern_raises, validate_pattern_valid, validate_pattern_invalid_raises, replace_link_in_post_success, replace_link_in_post_message_not_found, replace_link_in_post_no_replacements, replace_link_in_post_edit_fails, replace_link_in_post_empty_text
├── test_api_jobs.py         # 15 тестов: replace_link_success, replace_link_invalid_channel, replace_link_invalid_pattern, replace_link_invalid_url, replace_link_url_wrong_channel, replace_link_requires_auth, list_jobs (2 jobs), list_jobs_filter_by_channel, get_job_by_id, get_job_not_found, get_job_logs, get_job_logs_job_not_found, cancel_job_success, cancel_job_already_done, jobs_endpoints_require_auth
└── test_websocket.py        # 8 тестов: ws_requires_auth (anon_ws_client → close 4001), ws_receives_events (job_started/progress/completed), ws_disconnect_unsubscribes, ws_publish_event_directly, test_event_bus_subscribe_publish_unsubscribe, test_event_bus_unsubscribe_idempotent, test_runner_start_idempotent, test_runner_cancel_returns_false_for_unknown_job
```

### Patterns

- **pytest-asyncio** (asyncio_mode=auto) — async-тесты без `@pytest.mark.asyncio`
- **Coverage gate 80%** — `--cov=telesoft --cov-fail-under=80` (текущее покрытие 94.08% после PR #22)
- **TestClient** (starlette) требует httpx — добавлен в dev-deps
- **conftest fixtures** — `mock_settings` (monkeypatch env vars, SECRET_KEY 32+ chars для SessionMiddleware, ADMIN_PASSWORD="secret", `JOBS_MAX_CONCURRENCY` в delenv list), `mock_db` (async, `monkeypatch.setenv("DB_PATH", tmp_path/telesoft.db)`, yields `aiosqlite.Connection` для прямых запросов к моделям), `create_channel`/`create_job` (async factories с дефолтами), `MockMessage` dataclass (id/text/chat_id/message — Message-like), `mock_message`, `mock_telethon_client` (patch `TelegramClient` конструктор → AsyncMock с get_messages/edit_message/get_entity/get_me/start/disconnect; реальный `get_client`/`start_client` упражняется против mock; reset `_state` в setup/teardown), `mock_telethon_get_message` (monkeypatch `core.telegram.get_message` → AsyncMock(return_value=mock_message); module-level patch, виден всем importer'ам `link_replacer`), `mock_telethon_edit_message` (monkeypatch `core.telegram.edit_message` → AsyncMock(return_value=None); return_value=None OK — `link_replacer` игнорирует return), `mock_runner` (заменяет `app.state.job_runner` + `app.state.event_bus` на fresh in-memory `JobRunner(max_concurrency=2)` + `EventBus`, restore prev в teardown), `authed_client` (async, TestClient(app) as ctx mgr + POST /api/auth/login → залогиненная сессия)
- **PEP 695 type aliases** для фикстур — `type ChannelFactory = Callable[..., Awaitable[ChannelRow]]`, `type JobFactory = ...`
- **per-file-ignores** для tests: S104 (`0.0.0.0`), S105 (secret_key/token assignment)
- **FK CASCADE тесты** — `test_delete_job_cascade_logs`, `test_delete_channel_cascade_jobs_logs` проверяют каскадное удаление (требуют `PRAGMA foreign_keys=ON`)
- **Telethon mock design** — `mock_telethon_client` patch'ит `TelegramClient` конструктор (НЕ `get_client`/`start_client`), что позволяет тестировать singleton + idempotency + locking против mock client. `BadRequestError(request=None, message="...")` для эмуляции `RPCError` (конструктор требует `request`)
- **Auth test design** (`test_auth.py`) — `client` fixture: monkeypatch `SECRET_KEY` (32+ chars), `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `DB_PATH=tmp`, `TestClient(app)` as context manager (trigger lifespan). Session cookies через `TestClient` (stateful). Concurrent sessions — два отдельных `TestClient` (независимые cookies). `test_concurrent_sessions_independent` проверяет, что logout одного клиента не влияет на другого
- **`authed_client` fixture** (`conftest.py`, async) — аналог `client` из `test_auth.py`, но с предзаполненной сессией: monkeypatch env vars → `TestClient(app)` as context manager (trigger lifespan → init_db) → `POST /api/auth/login` с admin/secret → assert 200 → yield client. Используется в `test_api_channels.py` (13 из 14 тестов) и `test_api_jobs.py`. `test_create_channel_requires_auth`/`test_replace_link_requires_auth`/`test_jobs_endpoints_require_auth` используют отдельный TestClient без `authed_client` для проверки 401. pytest-asyncio `auto` mode поддерживает async fixtures без декоратора, работает в sync- и async-тестах
- **`db_handle` fixture** (`test_api_channels.py`) — exposes shared app DB connection (`connection._state.db`) для прямых SQL-запросов в cascade-тесте (`test_delete_channel_cascade_jobs_logs` создаёт job+log через model functions напрямую). Приватный API, но `connection` module стабилен (PR#12)
- **`mock_telethon_get_message` / `mock_telethon_edit_message` — module-level monkeypatch** — `monkeypatch.setattr(telegram_module, "get_message", AsyncMock)`. Это заменяет функцию в модуле `core.telegram`, так что `link_replacer.py` (который импортирует `telegram_module` и вызывает `telegram_module.get_message`) видит mock. НЕ нужно patch'ить `core.link_replacer.telegram_module` — `link_replacer` использует `from telesoft.core import telegram as telegram_module`, monkeypatch на `telegram_module.get_message` меняет атрибут модуля, виден всем importer'ам
- **`mock_runner` fixture** — НЕ isolates test from real runner: `mock_runner` создаёт real `JobRunner` с fresh `EventBus`, но `submit` запускает real `_run_job` (которая вызывает `replace_link_in_post` → Telethon mock). Если нужен no-op runner — override `submit` в тесте или используй `_install_runner` с custom work_fn (media-gen паттерн). Для API tests (только 201 + job_id check) real runner OK — Telethon mock'и возвращают success
- **WebSocket test design** (`test_websocket.py`) — `ws_client`/`anon_ws_client` fixtures (TestClient with `websocket_connect("/api/ws")`). `test_ws_receives_events` — `mock_runner` + `mock_telethon_get_message`/`mock_telethon_edit_message`, submit job via runner, receive events via WS, assert `job_started`/`progress`/`completed`. `test_ws_requires_auth` — `anon_ws_client` (без login) → close code 4001. EventBus unit tests — direct `EventBus()` instance. JobRunner unit tests — direct `JobRunner()` instance (start_idempotent, cancel_returns_false_for_unknown)
- **Coverage 94.08%** после PR #22 (gate 80% пройден). Uncovered: `core/runner.py` 80% (defensive `assert sem is not None`, `is_running`/`get_task`/`active_count`, exception path в `_mark_final` без error column), `api/routers/jobs.py` 95% (defensive `assert row is not None` после `_get_job_or_404`, username match branch), `schemas/job.py` 94% (`WsEvent.from_event` — tested via integration, не unit)

## Frontend tests (`web/src/tests/`)

```
web/src/tests/
├── setup.ts              # import "@testing-library/svelte"; afterEach(vi.restoreAllMocks) — очистка моков между тестами
├── LayoutHarness.svelte # обёртка для +layout.svelte (передаёт data prop, рендерит child slot)
├── login.test.ts         # 3 теста: form render (username/password fields), submit+redirect (POST /api/auth/login → goto), 401 error display
├── channels.test.ts      # 9 тестов: 3 rows render (title+active badge)/empty state/delete action + 3 Add button (open form/submit+refresh/cancel) + 3 ChannelForm (disabled when empty/enabled when filled/calls onSaved after POST)
├── replace-link.test.ts  # 4 теста: disabled when empty, disabled when URLs empty, invalid regex error display, parses textarea URLs and submits with correct body + redirects to /jobs/{id}
├── jobs.test.ts          # 5 тестов: renders header/status/progress/logs, cancel button calls POST /api/jobs/{id}/cancel, WS progress event updates progress, WS completed event refetches logs, WS events for other job_ids ignored
├── layout.test.ts        # 3 теста: Channels nav item, Logout button, signed-in username display
└── api.test.ts           # 2 теста: query serialization (URLSearchParams, undefined пропущен), ApiError on non-ok response
```

### Patterns

- **Vitest + jsdom** — DOM-окружение для компонентных тестов
- **@testing-library/svelte** — рендеринг Svelte-компонентов в тестах (import в setup.ts)
- **coverage v8** — через @vitest/coverage-v8
- **Mocking через `vi.hoisted` + `vi.mock`** — mock `../lib/api` (api.post/del), `$app/navigation` goto, `$app/state` page
- **`mockImplementation` для fresh Response** — `vi.fn().mockResolvedValue(response)` возвращает тот же Response → "Body is unusable" на втором вызове. Использовать `mockImplementation(() => Promise.resolve(jsonResponse(...)))` для fresh Response каждый вызов
- **LayoutHarness.svelte** — обёртка для рендера `+layout.svelte` в тестах (передаёт `data` prop, рендерит child slot через `{@render children()}`)
- **WebSocket mock pattern** (PR#26, `jobs.test.ts`) — `vi.mock("../lib/ws", ...)` с class mock. `onMessage(handler)` регистрирует handler в `Set<WsMessageHandler>` (НЕ static `vi.fn()`), `emitWsEvent(type, data)` helper дёргает все handlers. `beforeEach` очищает `onMessageHandlers` Set между тестами. `connect()`/`close()` — `vi.fn()` no-op. Позволяет тестировать WS event handling без реального соединения.
- **26 тестов, 6 файлов** (PR#26, было 11/4) — login (3), channels (9), replace-link (4, новый), jobs (5, новый), layout (3), api (2). Все зелёные. Smoke-тест из PR#2 удалён (реальные тесты заменяют)
- **Vitest НЕ имеет coverage gate** (в отличие от backend pytest `--cov-fail-under=80`). `+page.ts`/`+layout.ts` load functions не покрыты (требуют SvelteKit load context). `ws.ts` покрыт косвенно через mock в `jobs.test.ts`.