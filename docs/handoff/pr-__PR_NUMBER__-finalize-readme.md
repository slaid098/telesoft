---
pr: __PR_NUMBER__
issue: 27
branch: docs/repo/finalize-readme
status: ready
created: 2026-07-20
---

# Handoff — PR #__PR_NUMBER__: Finalize README and add end-to-end docker-compose smoke test

## Что сделано

Реализован issue #27 — финальная документация MVP + standalone smoke test для проверки docker-compose.

### Шаг 1: `README.md` — итоговый обзор

- Обновлённый `README.md` со следующими секциями:
  - `## Overview` — telesoft: Telegram channel post editor, MVP scope (channels list, replace-link from post URLs + regex + new link, WebSocket realtime progress).
  - `## Architecture` — текстовая ASCII-диаграмма: Browser (SvelteKit) ↔ FastAPI (auth, channels, jobs, EventBus/JobRunner) ↔ SQLite + Telegram MTProto (bot mode, by-ID fetch). Ссылка на `docs/project-map/`.
  - `## Stack` — Python 3.12+/FastAPI/aiosqlite/Telethon/uvicorn/Pydantic v2/itsdangerous/loguru (backend); SvelteKit 2/Svelte 5/TS/Tailwind/Biome/Vitest/Knip/adapter-node (frontend); uv/npm/ruff/mypy strict/pytest-asyncio/pre-commit/Docker Compose (tooling); GitHub Actions 3 jobs (CI).
  - `## Prerequisites` — Python 3.12+, uv, Node 20+, npm, Docker, Telegram bot token + api_id + api_hash, `ADMIN_PASSWORD` + `SECRET_KEY` (32+ chars).
  - `## Getting Started (Docker)` — `git clone` → `cp .env.example .env` → `docker compose up --build`. Backend http://localhost:8000 (health `GET /health`), Frontend http://localhost:3000. Упоминается что `api` exposition `/health` для compose healthcheck.
  - `## Getting Started (Local Dev)` — `uv sync --extra dev` + `uv run uvicorn telesoft.main:app --reload` (backend :8000); `cd web && npm ci && npm run dev` (frontend :5173, Vite proxy `/api` → :8000); `uv run python scripts/smoke_test.py` для smoke test.
  - `## Environment Variables` — таблица из 12 переменных (var | description | required | default). Все из `.env.example`: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `HOST`, `PORT`, `LOG_LEVEL`, `DB_PATH`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`, `SESSION_PATH`, `JOBS_MAX_CONCURRENCY`.
  - `## Testing` — `uv run pytest` (backend, coverage gate 80%); `cd web && npm run test` (frontend Vitest); `uv run python scripts/smoke_test.py` (end-to-end smoke, NOT part of pytest suite — requires running backend).
  - `## Project Structure` — краткое дерево (`src/telesoft/`, `tests/`, `web/`, `scripts/`, `app_data/`, `docs/`, `.github/`, `docker-compose.yml`, `Dockerfile.*`, `pyproject.toml`, `.env.example`). Ссылки на `docs/project-map/`.
  - `## Bot setup` — 4 шага: (1) создать бота через @BotFather, скопировать token (`TELEGRAM_BOT_TOKEN`); (2) получить `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` на my.telegram.org → "API development tools"; (3) добавить бота админом в канал с "Edit Messages" (+ "Post Messages" для spike/smoke); (4) file session `app_data/bot.session` — MTProto handshake только один раз. Описание ограничения: боты не могут итерировать историю (`BotMethodInvalidError`), юзер даёт post URLs. Ссылка на spike ADR `docs/decisions/2026-07-20-pr-14-spike-telethon.md`.
  - `## Limitations (MVP)` — bot не может читать историю канала (только edit по message_id), нет edit/delete channels из UI (backend готов), нет retry/delete jobs из UI (cancel wired), WebSocket per-page (no shared client in layout), нет polling fallback на job detail page.
  - `## License` — MIT, ссылка на `LICENSE`.

### Шаг 2: `docs/project-map/README.md` — итоговая схема

- Текстовая ASCII-диаграмма архитектуры (Browser ↔ FastAPI ↔ SQLite + Telegram).
- Описание backend/frontend/telegram responsibilities.
- `## Tech stack` — список технологий (backend, frontend, tooling, runtime).
- `## Дерево верхнего уровня` — дерево с ссылками на `*.md` (backend.md, frontend.md, docker.md, ci.md, tests.md, scripts.md).
- `## Module index` — ссылки на все 6 module-map файлов с кратким описанием.
- `## Patterns` — src layout, monorepo, uv/npm, frozen dataclass, adapter-node (SSR=false), coverage gate 80%, raw aiosqlite, bot-mode Telethon, session auth, WebSocket realtime.
- `## Quick links` — два списка: ADRs (`docs/decisions/`, 9 файлов PR#2-26) и handoffs (`docs/handoff/`, 9 файлов PR#2-26).

### Шаг 3: `scripts/smoke_test.py` — end-to-end API smoke test

- Standalone async Python скрипт, использует `httpx.AsyncClient` (async HTTP client, уже в dev-deps для FastAPI TestClient).
- НЕ loguru — вывод через `print` (keeps standalone scripts dependency-light, нет лишних imports).
- Шаги:
  1. `POST /api/auth/login` — `{username, password}` → 200 (cookie set через `httpx.AsyncClient` автоматически).
  2. `GET /api/channels` → 200, body `{channels, total}`.
  3. `POST /api/channels` — `{telegram_id=-1003903711726, title="Smoke Test", username=null}` → 201 (channel id extracted).
  4. `GET /api/channels/{id}` → 200, проверка `telegram_id` matches.
  5. `DELETE /api/channels/{id}` → 204.
- Каждый шаг печатает `[OK]   <label>` или `[FAIL] <label> — <detail>`. detail — status code + body или network error message.
- Exit codes: `0` если все шаги passed, `1` если хотя бы один failed.
- НЕ запускает replace-link flow (нужны реальные post URLs + подключенный бот — вне scope smoke test).
- Env vars: `TELESOFT_API_URL` (default `http://localhost:8000`), `TELESOFT_ADMIN_USER` (default `admin`), `TELESOFT_ADMIN_PASS` (default `changeme`).
- Docstring в начале файла — полный usage/env/exit codes. **Нет inline comments** (по AGENTS.md конвенции).
- `ruff check` + `ruff format --check` — green (T201/print НЕ в ruff select, S101/S603 тоже НЕ в select — per-file-ignore НЕ нужен, как и для `spike_telethon.py`).
- `mypy` НЕ проверяет `scripts/` (CI проверяет только `src/`).
- НЕ часть pytest suite (integration test, требует запущенный backend — описано в docstring + README).
- `docs/project-map/scripts.md` обновлён с описанием нового файла.

### Шаг 4: `docker-compose.yml` — healthcheck для api

- `api` service: добавлен `healthcheck` — `curl --fail --silent http://localhost:8000/health`. `interval: 10s`, `timeout: 5s`, `retries: 5`, `start_period: 10s`. `curl` уже установлен в `Dockerfile.api` (`apt-get install -y --no-install-recommends curl git procps` — был с PR#2).
- `web` service: `depends_on` изменён с `depends_on: - api` (bare, только порядок запуска) на `depends_on: { api: { condition: service_healthy } }` — web стартует только после того как api прошёл healthcheck (более надёжная startup ordering).
- `docker compose config` НЕ проверялся в окружении (docker недоступен — как и в PR#2), но YAML валидность проверена через `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`.
- `docs/project-map/docker.md` обновлён: описан healthcheck + `depends_on: condition: service_healthy` semantics.

### Шаг 4b: `.env.example` — добавлен `JOBS_MAX_CONCURRENCY`

- Добавлен `JOBS_MAX_CONCURRENCY=3` — переменная читается `Settings.from_env()` с PR#22 (default 3), но отсутствовала в `.env.example`. Теперь все 12 env vars документированы.

## Почему

MVP telesoft готов: backend (auth, channels, jobs, ws, telegram client) + frontend (login, channels list+detail, replace-link form, jobs list+detail с WS realtime). Docker-compose.yml + .env.example созданы в PR#2, README.md был минимальным placeholder (13 строк). Этот PR финализирует документацию: (1) README с инструкциями запуска (Docker + Local Dev), архитектурой, env vars таблицей, bot setup, limitations; (2) project-map с итоговой схемой и quick links на ADRs/handoffs; (3) standalone smoke test для проверки что docker-compose (или локальный backend) поднимается и API работает (login + channels CRUD) — без необходимости запускать replace-link (нужны реальные post URLs); (4) healthcheck для api в docker-compose — web стартует только после того как api прошёл `/health` probe, более надёжно чем bare `depends_on`. Smoke test НЕ часть pytest suite (integration test, требует запущенный backend) — документирован в README как отдельная команда. Использует `httpx` (async, уже в dev-deps для TestClient) и `print` (НЕ loguru — keeps standalone scripts dependency-light).

## Pending

- **`docker compose config` валидация в CI** — docker недоступен в текущем окружении. CI не имеет шага для compose validation. Можно добавить отдельный job (`docker compose config` quick sanity check) — follow-up.
- **Smoke test в CI** — smoke test требует запущенный backend (с реальными кредами Telegram для replace-link, но login+channels CRUD работают и без `TELEGRAM_BOT_TOKEN`). Можно добавить CI job: `docker compose up -d api` → wait health → `uv run python scripts/smoke_test.py` → `docker compose down`. Низкий приоритет (нужен `services` runner с Docker-in-Docker или Docker daemon).
- **README на русском vs английском** — README написан на английском (т.к. GitHub repo публичный, если станет публичным — англоязычная аудитория). AGENTS.md/PR body на русском. Сохранено как есть.

## Watch out

- **`docker compose config` НЕ проверялся** — docker недоступен в окружении разработчика (как и в PR#2). YAML валидность проверена через `python -c "import yaml; yaml.safe_load(...)"`. Если compose file содержит ошибки синтаксиса — `docker compose up` упадёт. Healthcheck syntax `["CMD", "curl", "--fail", "--silent", "http://localhost:8000/health"]` — стандартный Docker compose format.
- **`curl` в `Dockerfile.api`** — уже установлен с PR#2 (`apt-get install -y --no-install-recommends curl git procps`). НЕ нужно добавлять в Dockerfile в этом PR. Если `curl` убрать — healthcheck упадёт с "executable file not found".
- **`httpx` в standalone скрипте** — `httpx` в `[project.optional-dependencies] dev` (для FastAPI TestClient), НЕ в `dependencies` (runtime). `uv run python scripts/smoke_test.py` работает т.к. `uv sync --extra dev` ставит httpx. Если запускать smoke test в production окружении без dev deps — `ImportError: httpx`. Альтернатива — `urllib` (sync, без deps), но async + cleaner API httpx предпочтительнее для dev/CI скрипта.
- **smoke test НЕ запускает replace-link** — намеренно. Replace-link требует реальные post URLs + подключенный бот (TELEGRAM_BOT_TOKEN, канал с ботом-админом). Smoke test проверяет только API plumbing (login + channels CRUD) — это min viable e2e проверка.
- **`JOBS_MAX_CONCURRENCY` отсутствовал в `.env.example`** с PR#22 — переменная читается `Settings.from_env()` (default 3), но не была задокументирована. Этот PR добавляет. Если юзер не задал — default 3 (.semaphore в JobRunner).
- **README license section** — MIT, ссылка на `LICENSE` файл (существует с PR#2). LICENSE не модифицирован.
- **`depends_on: condition: service_healthy`** — compose v2 syntax. Если используется compose v1 (legacy) — syntax может отличаться. CI/dev использует compose v2 (ACME standard). Если на проде compose v1 — fallback на bare `depends_on: - api` (но без healthcheck-gated startup).
- **`docs/project-map/scripts.md` обновлён** — добавлен `smoke_test.py` в Structure + Key files + Patterns (httpx dep, print output, no inline comments). `dependencies` frontmatter обновлён: `[telethon, httpx]` (было `[telethon]`).

## Coverage

- `README.md` — финальный, 12 секций (Overview, Architecture, Stack, Prerequisites, Getting Started Docker, Getting Started Local Dev, Environment Variables, Testing, Project Structure, Bot setup, Limitations, License).
- `docs/project-map/README.md` — итоговая схема с architecture diagram, module index, tech stack, patterns, quick links (ADRs + handoffs).
- `scripts/smoke_test.py` — новый, standalone async, httpx, print, exit 0/1, не part of pytest suite.
- `docker-compose.yml` — healthcheck для api, web depends_on api healthy.
- `.env.example` — добавлен `JOBS_MAX_CONCURRENCY=3` (12 vars total).
- `docs/project-map/scripts.md`, `docs/project-map/docker.md` — обновлены для reflect новых files / healthcheck.
- 4 коммита: README+project-map, smoke_test, docker healthcheck, handoff+ADR (этот коммит).