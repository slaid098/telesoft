---
module: /
purpose: telesoft — overall structure
key_files:
  - pyproject.toml — Python project config (uv, hatchling, ruff, mypy, pytest)
  - docker-compose.yml — 2 containers (api + web) with api healthcheck
  - Dockerfile.api — FastAPI backend image
  - Dockerfile.web — SvelteKit frontend image (adapter-node)
  - .env.example — all env vars documented
  - README.md — project overview, getting started, env vars table, bot setup
  - AGENTS.md — repo-level agent instructions
  - .pre-commit-config.yaml — ruff + mypy hooks
dependencies: []
last_updated: 2026-07-21
---

# telesoft — Project Map

Project map — обновляется docs-reviewer на каждый PR. Содержит схему структуры кода.

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │                   Browser                │
                        │  SvelteKit 2 + Svelte 5 + TypeScript     │
                        │  (login, channels, jobs, WebSocket UI)   │
                        └───────────────┬───────────────┬──────────┘
                                        │ HTTP /api/*   │ WS /api/ws
                                        │ (cookie auth) │ (cookie auth)
                                        ▼               ▼
                        ┌─────────────────────────────────────────┐
                        │              FastAPI backend             │
                        │  auth (session) · channels CRUD · jobs  │
                        │  EventBus + JobRunner (asyncio.Semaphore)│
                        └───────┬───────────────┬──────────────────┘
                                │ aiosqlite      │ Telethon (bot mode)
                                ▼                ▼
                        ┌──────────────┐  ┌────────────────────────┐
                        │   SQLite     │  │  Telegram MTProto API  │
                        │  telesoft.db │  │  (by-ID fetch + edit)  │
                        └──────────────┘  └────────────────────────┘
```

- **Backend** (`src/telesoft/`): FastAPI + aiosqlite + Telethon bot mode. Session auth via Starlette `SessionMiddleware` (signed cookies). Channels CRUD, replace-link runner with `asyncio.Semaphore`, EventBus pub/sub for WebSocket fan-out. Bot-mode Telethon client fetches posts by id and edits them (history iteration is forbidden for bots — see ADR PR#14).
- **Frontend** (`web/`): SvelteKit 2 + Svelte 5 runes + TypeScript + Tailwind. Login, channels list + detail with replace-link form, jobs list with 5s auto-refresh, job detail with WebSocket realtime progress + logs.
- **Telegram**: the bot is added as an admin to the target channel with "Edit Messages" permission. File session (`app_data/bot.session`) is reused across restarts.

## Tech stack

- **Backend:** Python 3.12+, uv, hatchling, FastAPI, aiosqlite, Telethon (bot mode), Pydantic v2, itsdangerous, loguru
- **Frontend:** SvelteKit 2 + Svelte 5 runes + TypeScript + TailwindCSS + Biome + Vitest + Knip + adapter-node
- **Tooling:** ruff, mypy strict, pytest-asyncio, pre-commit, Docker Compose, GitHub Actions (3 parallel CI jobs)
- **Runtime:** Docker (api = python:3.13-slim, web = node:22-slim), bridge network `telesoft-network`, api healthcheck on `/health`

## Дерево верхнего уровня

```
telesoft/
├── src/telesoft/      # Backend (FastAPI) — см. backend.md
├── tests/             # Backend unit tests — см. tests.md
├── web/               # SvelteKit frontend — см. frontend.md
├── scripts/           # Standalone spike/PoC + smoke test — см. scripts.md
├── app_data/          # Runtime storage (gitignored except .gitkeep)
├── docs/              # Project map, handoffs, ADRs
│   ├── project-map/   # Структура проекта (этот файл)
│   ├── handoff/       # Handoff-документы на каждый PR
│   └── decisions/     # ADR (Architecture Decision Records)
├── .github/           # CI workflows, dependabot, PR template — см. ci.md
├── pyproject.toml     # Backend config (uv, ruff, mypy, pytest)
├── docker-compose.yml # 2 containers — см. docker.md
├── Dockerfile.api     # Backend image — см. docker.md
├── Dockerfile.web     # Frontend image — см. docker.md
├── .env.example       # Все env-переменные с placeholder
├── README.md          # Overview, getting started, env vars, bot setup
├── .pre-commit-config.yaml  # ruff + mypy hooks — см. ci.md
├── .dockerignore
├── .editorconfig
└── AGENTS.md          # Repo-level agent instructions
```

## Module index

- [backend.md](backend.md) — `src/telesoft/` (FastAPI backend: main, config, core/{telegram,url_parser,link_replacer,events,runner}, db/, api/{auth,routers/{auth,channels,jobs,ws}}, schemas/{auth,channel,job})
- [frontend.md](frontend.md) — `web/` (SvelteKit 2 + Svelte 5 runes + TS + Tailwind + Biome + Vitest + Knip; lib/{api,ws,types}.ts + components/, routes/{+layout,+page,login,channels,jobs}, tests)
- [docker.md](docker.md) — `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.web`, `.env.example`, `.dockerignore`
- [ci.md](ci.md) — `.github/`, `.pre-commit-config.yaml`
- [tests.md](tests.md) — `tests/` (backend unit tests + integration tests PR#44, 122 unit + 4 integration opt-in), `web/src/tests/` (frontend 26 tests: login 3, channels 9, replace-link 4, jobs 5, layout 3, api 2)
- [scripts.md](scripts.md) — `scripts/` (standalone spike/PoC + smoke test, НЕ часть backend)

## Patterns

- **src layout** для backend (`src/telesoft/`)
- **Monorepo**: backend + frontend в одном репо
- **uv** для Python, **npm** для frontend
- **Frozen dataclass** для конфига (`Settings.from_env()`)
- **Adapter-node** для SvelteKit (SSR в Docker), но `ssr=false` — pure CSR MVP
- **Coverage gate 80%** для backend (pytest --cov-fail-under=80)
- **Raw aiosqlite без ORM** — `CREATE TABLE IF NOT EXISTS` на startup, без миграций
- **Bot-mode Telethon** — by-ID fetch only (`iter_messages`/`get_messages(limit=...)` forbidden for bots)
- **Session auth** — Starlette `SessionMiddleware` (signed cookie via `itsdangerous`), `secrets.compare_digest` for credentials
- **WebSocket realtime** — per-page client in job detail, polling on jobs list (5s)

## Quick links

### ADRs (`docs/decisions/`)

- [PR#2 — repo init](../decisions/2026-07-20-pr-2-repo-init.md)
- [PR#12 — db layer](../decisions/2026-07-20-pr-12-db-layer.md)
- [PR#14 — telethon bot mode spike](../decisions/2026-07-20-pr-14-spike-telethon.md)
- [PR#16 — telegram client wrapper](../decisions/2026-07-20-pr-16-telegram-client.md)
- [PR#18 — session-based admin auth](../decisions/2026-07-20-pr-18-auth.md)
- [PR#20 — channels CRUD API](../decisions/2026-07-20-pr-20-channels-api.md)
- [PR#22 — replace-link runner + WS](../decisions/2026-07-20-pr-22-replace-link-runner-ws.md)
- [PR#24 — frontend skeleton](../decisions/2026-07-20-pr-24-frontend-skeleton.md)
- [PR#26 — channels UI](../decisions/2026-07-20-pr-26-channels-ui.md)
- [PR#28 — finalize README + smoke test](../decisions/2026-07-20-pr-28-finalize-readme.md)
- [PR#30 — spike v2 channels.GetMessagesRequest](../decisions/2026-07-20-pr-30-spike-telethon-v2.md)
- [PR#44 — entity URL handling](../decisions/2026-07-21-pr-44-entity-url-handling.md)

### Handoffs (`docs/handoff/`)

- [PR#2 — repo init](../handoff/pr-2-repo-init.md)
- [PR#12 — db layer](../handoff/pr-12-db-layer.md)
- [PR#14 — telethon spike](../handoff/pr-14-spike-telethon.md)
- [PR#16 — telegram client](../handoff/pr-16-telegram-client.md)
- [PR#18 — auth](../handoff/pr-18-auth.md)
- [PR#20 — channels API](../handoff/pr-20-channels-api.md)
- [PR#22 — replace-link runner + WS](../handoff/pr-22-replace-link-runner-ws.md)
- [PR#24 — frontend skeleton](../handoff/pr-24-frontend-skeleton.md)
- [PR#26 — channels UI](../handoff/pr-26-channels-ui.md)
- [PR#28 — finalize README + smoke test](../handoff/pr-28-finalize-readme.md)
- [PR#30 — spike v2 channels.GetMessagesRequest](../handoff/pr-30-spike-telethon-v2.md)
- [PR#44 — entity URL handling](../handoff/pr-44-entity-url-handling.md)