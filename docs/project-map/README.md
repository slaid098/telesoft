---
module: /
purpose: telesoft — overall structure
key_files:
  - pyproject.toml — Python project config (uv, hatchling, ruff, mypy, pytest)
  - docker-compose.yml — 3 containers (api + web + nginx) with api+web healthchecks, single port 8080
  - Dockerfile.api — FastAPI backend image
  - Dockerfile.nginx — nginx:alpine reverse proxy image
  - web/Dockerfile.web — SvelteKit frontend image (adapter-node, curl for healthcheck)
  - nginx.conf — reverse proxy config (api:8000 + web:3000 → port 80)
  - .env.example — all env vars documented + production deployment notes (PR#62: MAX_PROBE_ID удалён)
  - README.md — project overview на русском (15 секций: описание, архитектура Mermaid, возможности, стек, env vars, настройка бота, тесты, структура, деплой)
  - AGENTS.md — repo-level agent instructions
  - .pre-commit-config.yaml — ruff + mypy hooks
dependencies: []
last_updated: 2026-07-22 (PR#87)
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

- **Backend** (`src/telesoft/`): FastAPI + aiosqlite + Telethon bot mode. Session auth via Starlette `SessionMiddleware` (signed cookies). Channels CRUD, replace-link runner with `asyncio.Semaphore`, EventBus pub/sub for WebSocket fan-out. Bot-mode Telethon client fetches posts by id and edits them (history iteration is forbidden for bots — see ADR PR#14). PR#62: `get_last_messages` принимает user-provided `max_id` (из `parse_post_link`), binary search удалён.
- **Frontend** (`web/`): SvelteKit 2 + Svelte 5 runes + TypeScript + Tailwind. Login, channels list + detail with replace-link form, jobs list with 5s auto-refresh + pagination (PR#84: номера страниц 1..N, Prev/Next, pageSize=20), job detail with WebSocket realtime progress + logs.
- **Telegram**: the bot is added as an admin to the target channel with "Edit Messages" permission. In-memory `StringSession` (no file on disk — bot-token auth is instant, no handshake to cache). PR#48: `TELEGRAM_SESSION_STRING` env var переиспользует auth_key между restarts. PR#62: integration tests используют module-scoped fixture с `TELEGRAM_SESSION_STRING` (no FloodWait).

## Tech stack

- **Backend:** Python 3.12+, uv, hatchling, FastAPI, aiosqlite, Telethon (bot mode), Pydantic v2, itsdangerous, loguru
- **Frontend:** SvelteKit 2 + Svelte 5 runes + TypeScript + TailwindCSS + Biome + Vitest + Knip + adapter-node
- **Tooling:** ruff, mypy strict, pytest-asyncio, pre-commit, Docker Compose, GitHub Actions (3 parallel CI jobs)
- **Runtime:** Docker (api = python:3.13-slim, web = node:22-slim, nginx = nginx:alpine), bridge network `telesoft-network`, api+web healthchecks, single port 8080 (nginx reverse proxy)

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
├── docker-compose.yml # 3 containers (api + web + nginx) — см. docker.md
├── Dockerfile.api     # Backend image — см. docker.md
├── Dockerfile.nginx   # nginx reverse proxy image — см. docker.md
├── web/Dockerfile.web # Frontend image — см. docker.md
├── nginx.conf         # nginx reverse proxy config — см. docker.md
├── .env.example       # Все env-переменные с placeholder + production notes
├── README.md          # Overview на русском, env vars, bot setup, тесты, деплой
├── .pre-commit-config.yaml  # ruff + mypy hooks — см. ci.md
├── .dockerignore
├── .editorconfig
└── AGENTS.md          # Repo-level agent instructions
```

## Module index

- [backend.md](backend.md) — `src/telesoft/` (FastAPI backend: main, config, core/{telegram,url_parser,pattern_compiler,link_replacer,events,runner}, db/, api/{auth,routers/{auth,channels,jobs,patterns,ws}}, schemas/{auth,channel,job}; PR#62: telegram.py +parse_post_link, get_last_messages +max_id, _find_max_id удалён, config.py -max_probe_id, schemas/job.py +post_link, runner.py +max_id; PR#64: telegram.py edit_message +formatting_entities, link_replacer.py +_adjust_entity_offsets +50-char preview context, pattern_compiler.py apply_keep_tail→full_replace, schemas/job.py keep_tail→full_replace; PR#66: link_replacer.py _adjust_entity_offsets crossing boundary case 3a/3b + defensive validation drop invalid bounds; PR#84: db/models/job.py +count_jobs, db/models/log.py +count_logs, api/routers/jobs.py total=count_jobs/count_logs вместо len(); PR#86: link_preview: bool=False прокинут через всю цепочку schemas/job.py→api/routers/jobs.py→runner.py→link_replacer.py→telegram.py edit_message/edit_message_entities, default False подавляет link preview card)
- [frontend.md](frontend.md) — `web/` (SvelteKit 2 + Svelte 5 runes + TS + Tailwind + Biome + Vitest + Knip; lib/{api,ws,types}.ts + components/{ChannelForm,ReplaceLinkForm,PreviewModal,PatternLibrary}, routes/{+layout,+page,login,channels,jobs}, tests; PR#62: ReplaceLinkForm +post_link field, types.ts +post_link; PR#64: ReplaceLinkForm keep_tail checkbox→radio "Полная"/"Частичная", types.ts keep_tail→full_replace; PR#84: jobs/+page.svelte +pagination controls, jobs/+page.ts limit=20 offset=0; PR#86: workflow preview-confirm-run — «Запустить»→handlePreview()→PreviewModal→confirm→run (вместо прямого запуска), старый чекбокс «Показать предпросмотр»+кнопка «Предпросмотр» убраны, +linkPreview=$state(false) чекбокс «Включить превью ссылки», PreviewModal кнопки renamed «Отменить»/«Запустить», types.ts +link_preview)
- [docker.md](docker.md) — `docker-compose.yml` (3 services: api + web + nginx), `Dockerfile.api`, `Dockerfile.nginx`, `web/Dockerfile.web`, `nginx.conf`, `.env.example`, `.dockerignore`
- [ci.md](ci.md) — `.github/`, `.pre-commit-config.yaml`
- [tests.md](tests.md) — `tests/` (backend unit tests + integration tests PR#44, 191→202 unit PR#64 + 4 integration opt-in; PR#64: +7 _adjust_entity_offsets +4 replace_link_in_post preserves entity +3 full_replace API +2 preview context +1 frontend full_replace default; PR#84: test_models_job +4 count_jobs, test_api_jobs +3 total tests, jobs.test.ts +4 pagination), `web/src/tests/` (frontend 37→41 tests PR#84: login 3, channels 9, replace-link 10, jobs 9, layout 3, api 2; PR#86: replace-link.test.ts updated — submit→previewReplace, +link_preview checkbox tests, runNonce +link_preview tests)
- [scripts.md](scripts.md) — `scripts/` (standalone spike/PoC + smoke test, НЕ часть backend)

## Patterns

- **src layout** для backend (`src/telesoft/`)
- **Monorepo**: backend + frontend в одном репо
- **uv** для Python, **npm** для frontend
- **Frozen dataclass** для конфига (`Settings.from_env()`)
- **Adapter-node** для SvelteKit (SSR в Docker), но `ssr=false` — pure CSR MVP
- **Coverage gate 80%** для backend (pytest --cov-fail-under=80)
- **Raw aiosqlite без ORM** — `CREATE TABLE IF NOT EXISTS` на startup, без миграций
- **Bot-mode Telethon** — by-ID fetch only (`iter_messages`/`get_messages(limit=...)` forbidden for bots). PR#62: `get_last_messages(channel_id, limit, max_id)` — caller передаёт `max_id` (из `parse_post_link`), без binary search (binary search ломался на дырах удалённых постов)
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
- [PR#46 — StringSession instead of file session](../decisions/2026-07-21-pr-46-string-session.md)
- [PR#48 — TELEGRAM_SESSION_STRING env var (supersedes PR#46)](../decisions/2026-07-21-pr-48-session-string.md)
- [PR#54 — merge compose files for production](../decisions/2026-07-21-pr-54-production-compose.md)
- [PR#56 — pattern compiler + preview + pattern library](../decisions/2026-07-21-pr-56-pattern-compiler.md)
- [PR#58 — three replace modes + preview UI](../decisions/2026-07-21-pr-58-three-modes-ui.md)
- [PR#60 — seed built-in link patterns](../decisions/2026-07-21-pr-60-seed-patterns.md)
- [PR#62 — replace binary search with user-provided post link + fix integration tests FloodWait](../decisions/2026-07-21-pr-62-post-link-and-floodwait.md)
- [PR#64 — preserve formatting entities + preview context + full/partial radio](../decisions/2026-07-21-pr-64-formatting-preview-radio.md)
- [PR#84 — jobs pagination + count_jobs/count_logs total fix](../decisions/2026-07-22-pr-84-jobs-pagination.md)
- [PR#86 — link_preview configurable + preview-confirm-run workflow](../decisions/2026-07-22-pr-86-preview-ux.md)

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
- [PR#46 — StringSession instead of file session](../handoff/pr-46-string-session.md)
- [PR#48 — TELEGRAM_SESSION_STRING env var (supersedes PR#46)](../handoff/pr-48-session-string.md)
- [PR#54 — merge compose files for production](../handoff/pr-54-production-compose.md)
- [PR#56 — pattern compiler + preview + pattern library](../handoff/pr-56-pattern-compiler.md)
- [PR#58 — three replace modes + preview UI](../handoff/pr-58-three-modes-ui.md)
- [PR#60 — seed built-in link patterns](../handoff/pr-60-seed-patterns.md)
- [PR#62 — replace binary search with user-provided post link + fix integration tests FloodWait](../handoff/pr-62-post-link-and-floodwait.md)
- [PR#64 — preserve formatting entities + preview context + full/partial radio](../handoff/pr-64-formatting-preview-radio.md)
- [PR#84 — jobs pagination + count_jobs/count_logs total fix](../handoff/pr-84-jobs-pagination.md)
- [PR#86 — link_preview configurable + preview-confirm-run workflow](../handoff/pr-86-preview-ux.md)