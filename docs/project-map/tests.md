---
module: tests
purpose: Backend + frontend unit tests
key_files:
  - tests/conftest.py — fixtures: mock_settings (sync), mock_db (async)
  - tests/test_health.py — TestClient → /health 200
  - tests/test_config.py — Settings: defaults, custom env, frozen check
  - web/src/tests/setup.ts — afterEach restoreAllMocks
  - web/src/tests/smoke.test.ts — expect(1+1).toBe(2) — гарантирует vitest зелёный
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# tests — backend + frontend

## Backend tests (`tests/`)

```
tests/
├── __init__.py       # Пустой — package marker
├── conftest.py       # Fixtures: mock_settings (sync, monkeypatch env), mock_db (async, init_db/close_db)
├── test_health.py    # TestClient → GET /health → 200 {"status":"ok"}
└── test_config.py    # 3 теста: defaults (env не задан), custom env (ADMIN_USERNAME и др.), frozen check (FrozenInstanceError)
```

### Patterns

- **pytest-asyncio** (asyncio_mode=auto) — async-тесты без `@pytest.mark.asyncio`
- **Coverage gate 80%** — `--cov=telesoft --cov-fail-under=80` (текущее покрытие 95.74%)
- **TestClient** (starlette) требует httpx — добавлен в dev-deps
- **conftest fixtures** — `mock_settings` (monkeypatch env vars), `mock_db` (async context manager)
- **per-file-ignores** для tests: S104 (`0.0.0.0`), S105 (secret_key/token assignment)

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