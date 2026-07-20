---
pr: 2
issue: 1
branch: chore/repo/init-scaffolding
status: ready
created: 2026-07-20
---

# Handoff — PR #2: repo-init scaffolding

## Что сделано

Реализован issue #1 — стартовая структура проекта telesoft (Telegram channel post editor).

### Шаг 1: Backend skeleton (Python/FastAPI, src layout)

- `pyproject.toml` — name=`telesoft`, version=`0.1.0`, requires-python=`>=3.12`, build-system hatchling, packages=`["src/telesoft"]`. Dependencies: fastapi, uvicorn, pydantic[email], aiosqlite, telethon, python-multipart, itsdangerous, loguru. Optional dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, **httpx** (добавлен для FastAPI TestClient — без него `starlette.testclient` падает с `RuntimeError: requires httpx2`). Tool configs: ruff (target=py312, line-length=100, select E/W/F/I/B/UP/SIM/C90/PL/RUF/S/TRY/LOG, ignore S101/S311/RUF001-003/TRY003/PLR2004/S106), mypy strict, pytest (asyncio_mode=auto, --cov=telesoft --cov-fail-under=80), coverage (source=src/telesoft, branch=true).
- `src/telesoft/__init__.py` (пустой), `src/telesoft/py.typed` (пустой).
- `src/telesoft/main.py` — FastAPI app с lifespan (init_db/close_db placeholder), `GET /health` → `{"status":"ok"}`.
- `src/telesoft/config.py` — `Settings` frozen dataclass с `from_env()` classmethod, helper funcs `_get_int`/`_get_str`/`_get_list`. Поля: admin_username, admin_password, secret_key, host (с `# noqa: S104`), port, log_level, db_path, telegram_api_id, telegram_api_hash, telegram_bot_token, session_path. Префиксы env: `ADMIN_`, `SECRET_KEY`, `TELEGRAM_`.
- `Dockerfile.api` — `python:3.13-slim`, `COPY --from=ghcr.io/astral-sh/uv:latest`, `uv sync --frozen --extra dev`, CMD uvicorn.
- `tests/__init__.py`, `tests/conftest.py` (mock_settings sync, mock_db async с init_db/close_db), `tests/test_health.py` (TestClient → /health 200), `tests/test_config.py` (3 теста: defaults, custom env, frozen check) — **добавлен сверх спецификации**, т.к. одного test_health было недостаточно для покрытия 80% (config.py 67% → 93% с test_config.py, итого 95.74%).
- `.dockerignore`, `.editorconfig` (2-space для ts/js/json/yml, 4-space для py/toml, lf, utf-8).
- `uv.lock` — сгенерирован через `uv lock` (53 пакета).

### Шаг 2: Frontend skeleton (SvelteKit + TS)

- `web/package.json` — name=`telesoft-web`, scripts: dev/build/preview/lint/format/check/typecheck/test/test:watch/knip. devDependencies: @sveltejs/adapter-node, @sveltejs/kit, @sveltejs/vite-plugin-svelte, @biomejs/biome, @testing-library/svelte, @types/node, @vitest/coverage-v8, autoprefixer, jsdom, knip, postcss, svelte, svelte-check, tailwindcss, typescript, vite, vitest. dependencies: `{}` (пусто на MVP).
- `web/svelte.config.js` (adapter-node, vitePreprocess), `web/vite.config.ts` (sveltekit, proxy /api→localhost:8000 ws:true), `web/vitest.config.ts` (jsdom, @testing-library/svelte/vite, coverage v8).
- `web/tsconfig.json`, `web/biome.json` (recommended, noExplicitAny=error, useConst off для .svelte, 2-space, double quotes, semicolons always, trailingCommas all, lineWidth 100), `web/knip.json`, `web/postcss.config.js`, `web/tailwind.config.js` (минимальный).
- `web/src/app.html`, `web/src/app.css` (@tailwind base/components/utilities), `web/src/app.d.ts` (App.Locals пустой, App.Error).
- `web/src/routes/+layout.svelte` (Tailwind wrapper, `<slot />`), `web/src/routes/+page.svelte` (`<h1>telesoft</h1><p>Under construction</p>`).
- `web/src/tests/setup.ts` (afterEach restoreAllMocks), `web/src/tests/smoke.test.ts` — **добавлен сверх спецификации**, т.к. vitest падает с exit code 1 когда нет тестовых файлов ("No test files found"). Smoke-тест гарантирует `npm run test` → зелёный.
- `web/Dockerfile.web` (multi-stage build → runtime, adapter-node, PORT=3000).
- `web/.env.example` (`VITE_API_BASE=http://localhost:8000`), `web/.gitignore`.
- `web/package-lock.json` — сгенерирован через `npm install --package-lock-only` (428 пакетов).

### Шаг 3: Docker Compose + env

- `docker-compose.yml` — services: api (build Dockerfile.api, port 8000, env_file .env, volumes ./src + ./app_data, networks telesoft-network, logging json-file 20m×3), web (build Dockerfile.web, port 3000, depends_on api, networks). networks.telesoft-network.driver=bridge.
- `.env.example` — все переменные с placeholder значениями.
- `app_data/.gitkeep` — уже был на main.

### Шаг 4: CI + pre-commit + Dependabot

- `.github/workflows/ci.yml` — 3 job'а (backend-lint, backend-test, frontend), trigger push/PR в main. backend: checkout@v4 + setup-uv@v3 (enable-cache) + uv sync + ruff/mypy/pytest. frontend: checkout@v4 + setup-node@v4 (node 20, cache npm) + npm ci + lint/typecheck/test.
- `.pre-commit-config.yaml` — ruff (--fix + ruff-format v0.15.0) + mypy (v1.18.2, additional_dependencies: fastapi, pydantic, httpx, aiosqlite, telethon).
- `.github/dependabot.yml` — pip (/), npm (/web), github-actions (/), weekly.
- `.github/PULL_REQUEST_TEMPLATE.md` — Что сделано / Почему / Связанные issue.

### Шаг 5: AGENTS.md

- `AGENTS.md` — repo-level instruction: Project, Stack, Commands, Conventions (по спеке).

### Шаг 6: Docs structure

- `docs/project-map/README.md` — placeholder с frontmatter и деревом верхнего уровня.
- `docs/handoff/.gitkeep`, `docs/decisions/.gitkeep`.

## Почему

Первый issue проекта telesoft. Репозиторий был пустым (только README/LICENSE/.gitignore на main). Нужна стартовая структура: backend skeleton (FastAPI + uv), frontend skeleton (SvelteKit + TS), quality tooling (ruff, mypy, Biome, Vitest, Knip), CI workflows, pre-commit, Dependabot, AGENTS.md, docker-compose. Референс — `slaid098/media-gen` (копирование паттернов 1-в-1 где применимо).

## Pending

- Branch protection на GitHub (require status checks: backend-lint, backend-test, frontend) — настраивается вручную после первого зелёного CI, не через код.
- Реальная бизнес-логика (Telethon bot, DB models, роутеры) — будущие issues.
- `docs/.gitkeep` удалён в коммите handoff (избыточен после создания подпапок).

## Watch out

- **httpx добавлен в dev-зависимости**: спецификация issue #1 не упоминает httpx, но FastAPI `TestClient` (через `starlette.testclient`) требует httpx для работы. Без него `tests/test_health.py` падает с `RuntimeError: The starlette.testclient module requires the httpx2 package to be installed`. Добавил `httpx>=0.27` в `[project.optional-dependencies] dev`. Starlette выдаёт deprecation warning с httpx (рекомендует httpx2), но тесты проходят. Альтернатива — добавить httpx в main dependencies, но для MVP тестовый клиент — это dev-инструмент.
- **tests/test_config.py добавлен сверх спецификации**: issue #1 упоминает только `tests/test_health.py`. Одного теста health endpoint недостаточно для покрытия 80% (config.py имеет 67% — непокрытые helper funcs и from_env). Добавил 3 теста в `tests/test_config.py` (defaults, custom env, frozen check) → покрытие 95.74%.
- **web/src/tests/smoke.test.ts добавлен сверх спецификации**: vitest падает с exit code 1 и сообщением "No test files found, exiting with code 1" когда нет файлов по include pattern. Smoke-тест (`expect(1+1).toBe(2)`) гарантирует `npm run test` → зелёный.
- **knip.json упрощён**: спецификация говорит "копия media-gen", но media-gen knip.json ссылается на `src/lib/api.ts`, `src/lib/ws.ts`, `src/lib/types.ts` и `src/routes/**/+page.ts`/`+layout.ts`, которых нет в telesoft MVP. Knip выдаёт "Configuration hints" (ошибки) для patterns без matches. Упростил entry до `["src/**/*.svelte", "src/tests/**/*.ts"]`.
- **S104/S105 добавлены в per-file-ignores для tests**: тесты используют литерал `"0.0.0.0"` (S104) и присваивают значения secret_key/telegram_bot_token (S105). Глобальный ignore покрывает только S106 (hardcoded password string), не S104/S105.
- **docker compose config не проверён**: в окружении нет `docker compose` / `docker-compose` команды. YAML структура скопирована 1-в-1 из media-gen (где проходит `docker compose config`), но локальной валидации не было.
- **Старый `docs/.gitkeep` удалён**: на main был `docs/.gitkeep` (пустой docs). После создания подпапок handoff/decisions/project-map он избыточен — удалён в коммите handoff.
- **uv lock**: `uv lock` прошёл успешно (53 пакета), `uv sync --extra dev` — без ошибок. `uv.lock` закоммичен.
- **npm install --package-lock-only**: прошёл успешно, `package-lock.json` (428 пакетов) закоммичен. `npm ci` также проверен — работает.