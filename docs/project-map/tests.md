---
module: tests
purpose: Backend + frontend unit tests
key_files:
  - tests/conftest.py — fixtures: mock_settings, mock_db, create_channel/create_job factories, mock_message, mock_telethon_client
  - tests/test_health.py — TestClient → /health 200
  - tests/test_config.py — Settings: defaults, custom env, frozen check
  - tests/test_db.py — DB connection layer (6 тестов: file/idempotent/pragmas/schema/get_db/noop-close)
  - tests/test_models_channel.py — channels CRUD (7 тестов: CRUD + UNIQUE + whitelist)
  - tests/test_models_job.py — edit_jobs CRUD (5 тестов: CRUD + filters + CASCADE)
  - tests/test_models_log.py — edit_logs CRUD (4 теста: CRUD + pagination + CASCADE)
  - tests/test_telegram_client.py — bot-mode Telethon client wrapper (10 тестов: singleton/idempotent/by-ID fetch/batch/edit/resolve/bot-info/stop)
  - tests/test_url_parser.py — URL parser (9 тестов: public/private/comment/invalid/non-t.me/batch/index/is_valid)
  - tests/test_auth.py — session-based auth (8 тестов: login success/invalid, logout requires-auth/success, me requires-auth/after-login, session persists, concurrent sessions independent)
  - web/src/tests/setup.ts — afterEach restoreAllMocks
  - web/src/tests/smoke.test.ts — expect(1+1).toBe(2) — гарантирует vitest зелёный
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# tests — backend + frontend

## Backend tests (`tests/`)

```
tests/
├── __init__.py              # Пустой — package marker
├── conftest.py              # Fixtures: mock_settings (sync, monkeypatch env — SECRET_KEY 32+ chars, ADMIN_PASSWORD="secret"), mock_db (async, yields aiosqlite.Connection), create_channel/create_job (async factories, PEP 695 ChannelFactory/JobFactory), MockMessage dataclass, mock_message, mock_telethon_client (patch TelegramClient конструктор, реальный get_client/start_client упражняется против mock)
├── test_health.py           # TestClient → GET /health → 200 {"status":"ok"}
├── test_config.py           # 3 теста: defaults (env не задан), custom env (ADMIN_USERNAME и др.), frozen check (FrozenInstanceError)
├── test_db.py               # 6 тестов: init_db_creates_file, init_db_idempotent, pragmas_set (WAL+foreign_keys), schema_created (sqlite_master), get_db_yields_connection, close_db_noop_when_uninitialized
├── test_models_channel.py  # 7 тестов: create+get, get_by_telegram_id, list_active_only, update (title/username/is_active), update_rejects_unknown_field (ValueError), delete, unique_telegram_id_constraint (IntegrityError)
├── test_models_job.py       # 5 тестов: create+get, list_filter_by_channel, list_filter_by_status, update_job_status, delete_job_cascade_logs (FK CASCADE)
├── test_models_log.py       # 4 теста: create+list, list_limit_offset (pagination), delete_logs (returns count), delete_channel_cascade_jobs_logs (FK CASCADE channel→jobs→logs)
├── test_telegram_client.py  # 10 тестов: get_client_singleton, start_client_idempotent (await_count), get_message_by_id, get_message_returns_none_for_missing, get_messages_batch_filters_none, edit_message_success, edit_message_propagates_error (BadRequestError→RPCError), resolve_entity, get_bot_info, stop_client_resets_state
├── test_url_parser.py       # 9 тестов: public channel, private channel (-100<internal_id>), ?comment= query, invalid format, non-t.me domain, private non-digit, batch, batch with index, is_valid_post_url true/false
└── test_auth.py             # 8 тестов: login_success, login_invalid_credentials, logout_requires_auth, logout_success, me_requires_auth, me_after_login, session_persists_across_requests, concurrent_sessions_independent
```

### Patterns

- **pytest-asyncio** (asyncio_mode=auto) — async-тесты без `@pytest.mark.asyncio`
- **Coverage gate 80%** — `--cov=telesoft --cov-fail-under=80` (текущее покрытие 95.90% после PR #18)
- **TestClient** (starlette) требует httpx — добавлен в dev-deps
- **conftest fixtures** — `mock_settings` (monkeypatch env vars, SECRET_KEY 32+ chars для SessionMiddleware, ADMIN_PASSWORD="secret"), `mock_db` (async, `monkeypatch.setenv("DB_PATH", tmp_path/telesoft.db)`, yields `aiosqlite.Connection` для прямых запросов к моделям), `create_channel`/`create_job` (async factories с дефолтами), `MockMessage` dataclass (id/text/chat_id/message — Message-like), `mock_message`, `mock_telethon_client` (patch `TelegramClient` конструктор → AsyncMock с get_messages/edit_message/get_entity/get_me/start/disconnect; реальный `get_client`/`start_client` упражняется против mock; reset `_state` в setup/teardown)
- **PEP 695 type aliases** для фикстур — `type ChannelFactory = Callable[..., Awaitable[ChannelRow]]`, `type JobFactory = ...`
- **per-file-ignores** для tests: S104 (`0.0.0.0`), S105 (secret_key/token assignment)
- **FK CASCADE тесты** — `test_delete_job_cascade_logs`, `test_delete_channel_cascade_jobs_logs` проверяют каскадное удаление (требуют `PRAGMA foreign_keys=ON`)
- **Telethon mock design** — `mock_telethon_client` patch'ит `TelegramClient` конструктор (НЕ `get_client`/`start_client`), что позволяет тестировать singleton + idempotency + locking против mock client. `BadRequestError(request=None, message="...")` для эмуляции `RPCError` (конструктор требует `request`)
- **Auth test design** (`test_auth.py`) — `client` fixture: monkeypatch `SECRET_KEY` (32+ chars), `ADMIN_USERNAME=admin`, `ADMIN_PASSWORD=secret`, `DB_PATH=tmp`, `TestClient(app)` as context manager (trigger lifespan). Session cookies через `TestClient` (stateful). Concurrent sessions — два отдельных `TestClient` (независимые cookies). `test_concurrent_sessions_independent` проверяет, что logout одного клиента не влияет на другого

## Frontend tests (`web/src/tests/`)

```
web/src/tests/
├── setup.ts          # afterEach(restoreAllMocks) — очистка моков между тестами
└── smoke.test.ts     # expect(1+1).toBe(2) — минимальный тест (vitest падает без тестовых файлов)
```

### Patterns

- **Vitest + jsdom** — DOM-окружение для компонентных тестов
- **@testing-library/svelte** — рендеринг Svelte-компонентов в тестах
- **coverage v8** — через @vitest/coverage-v8
- **Smoke test** — гарантирует, что vitest-инфраструктура работает (без тестовых файлов vitest exit code 1)