# telesoft

Telegram channel post editor — replace links in channel posts via a bot admin.

## Overview

telesoft is an MVP that lets a channel administrator replace links across many posts of a Telegram channel in one click. The user logs into a small admin UI, picks a channel, provides a list of post URLs plus a regex pattern and the new link, and the bot edits each post in the background. Progress is streamed to the UI in real time over a WebSocket.

MVP scope: list channels, start a replace-link job from post URLs + regex + new link, watch progress over WebSocket, cancel a running job, view per-post logs.

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

- Backend (`src/telesoft/`): FastAPI + aiosqlite + Telethon. Session auth, channels CRUD, background runner with cooperative cancellation, WebSocket fan-out via EventBus. Bot-mode Telethon client fetches posts by message id and edits them.
- Frontend (`web/`): SvelteKit 2 + Svelte 5 runes + TypeScript. Login, channels list + detail with replace-link form, jobs list with auto-refresh, job detail with WebSocket realtime progress + logs.
- Telegram: the bot is added as an admin to the target channel with "Edit Messages" permission. The bot cannot iterate channel history (MTProto limitation for bots), so the user supplies post URLs explicitly.

See [`docs/project-map/`](docs/project-map/) for the full module index.

## Stack

- **Backend**: Python 3.12+, FastAPI, aiosqlite (SQLite), Telethon (bot mode), uvicorn, Pydantic v2, itsdangerous (session cookies), loguru
- **Frontend**: SvelteKit 2 + Svelte 5 runes + TypeScript, TailwindCSS, Biome, Vitest, Knip, adapter-node
- **Tooling**: uv (Python), npm (frontend), ruff, mypy strict, pytest-asyncio, pre-commit, Docker Compose
- **CI**: GitHub Actions — backend-lint, backend-test, frontend (3 parallel jobs)

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker and Docker Compose (for the containerised run)
- A Telegram bot: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN` (see [Bot setup](#bot-setup))
- An `ADMIN_PASSWORD` and a `SECRET_KEY` (32+ characters) for the admin login and session cookie signing

## Getting Started (Docker)

```bash
git clone https://github.com/slaid098/telesoft.git
cd telesoft
cp .env.example .env  # fill in TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN,
                      # ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY (32+ chars)
docker compose up --build
# Backend: http://localhost:8000  (health: GET /health)
# Frontend: http://localhost:3000
```

The `api` container exposes a `/health` probe used by the compose healthcheck. The `web` container waits for `api` to become healthy before starting.

## Getting Started (Local Dev)

Backend (port 8000):

```bash
uv sync --extra dev
uv run uvicorn telesoft.main:app --reload  # http://localhost:8000
```

Frontend (port 5173, Vite proxies `/api` → `:8000`):

```bash
cd web
npm ci
npm run dev  # http://localhost:5173
```

Smoke test against a running backend (any of the two options above):

```bash
uv run python scripts/smoke_test.py  # uses TELESOFT_API_URL or http://localhost:8000
```

## Environment Variables

All variables are read by `Settings.from_env()` in `src/telesoft/config.py`. Copy `.env.example` to `.env` and fill in the values.

| Variable                 | Description                                            | Required | Default                |
| ------------------------ | ------------------------------------------------------ | -------- | ---------------------- |
| `ADMIN_USERNAME`         | Admin login username                                   | yes      | `admin`                |
| `ADMIN_PASSWORD`         | Admin login password                                   | yes      | `changeme`             |
| `SECRET_KEY`             | Session cookie signing key, must be 32+ characters    | yes      | `""` (empty = invalid) |
| `HOST`                   | Bind host for uvicorn                                  | no       | `0.0.0.0`              |
| `PORT`                   | Bind port for uvicorn                                  | no       | `8000`                 |
| `LOG_LEVEL`              | loguru level                                           | no       | `INFO`                 |
| `DB_PATH`                | SQLite database path                                   | no       | `app_data/telesoft.db` |
| `TELEGRAM_API_ID`        | Telegram API id from my.telegram.org                   | yes      | `0`                    |
| `TELEGRAM_API_HASH`      | Telegram API hash from my.telegram.org                 | yes      | `""`                   |
| `TELEGRAM_BOT_TOKEN`     | Bot token from @BotFather                              | yes      | `""`                   |
| `SESSION_PATH`           | Telethon session file path (deprecated, unused — StringSession is in-memory) | no       | `app_data/bot.session` |
| `JOBS_MAX_CONCURRENCY`   | Max concurrent post edits per runner                    | no       | `3`                    |

## Testing

Backend (pytest, coverage gate 80%):

```bash
uv run pytest
```

Frontend (Vitest, jsdom):

```bash
cd web
npm run test
```

End-to-end smoke (requires a running backend, not part of the pytest suite):

```bash
uv run python scripts/smoke_test.py
```

## Project Structure

```
telesoft/
├── src/telesoft/        # Backend (FastAPI) — see docs/project-map/backend.md
│   ├── main.py          # App entrypoint, lifespan, routers
│   ├── config.py        # Settings.from_env()
│   ├── core/            # telegram, url_parser, link_replacer, events, runner
│   ├── db/              # aiosqlite connection + models (channel, job, log)
│   ├── api/             # auth helpers + routers (auth, channels, jobs, ws)
│   └── schemas/         # Pydantic request/response models
├── tests/               # Backend unit tests — see docs/project-map/tests.md
├── web/                 # SvelteKit frontend — see docs/project-map/frontend.md
├── scripts/             # Standalone scripts (spike, smoke test) — see docs/project-map/scripts.md
├── app_data/            # Runtime storage (db), gitignored
├── docs/
│   ├── project-map/     # Module-by-module structure
│   ├── handoff/         # PR handoff documents
│   └── decisions/       # ADRs
├── .github/             # CI workflows, Dependabot, PR template
├── docker-compose.yml   # api + web services
├── Dockerfile.api       # Backend image (python:3.13-slim + uv)
├── Dockerfile.web       # Frontend image (node:22-slim, adapter-node)
├── pyproject.toml       # Backend config (uv, ruff, mypy, pytest)
└── .env.example         # All env vars with placeholders
```

See [`docs/project-map/README.md`](docs/project-map/README.md) for the full module index and links to ADRs and handoffs.

## Bot setup

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the bot token (`TELEGRAM_BOT_TOKEN`).
2. Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` at [my.telegram.org](https://my.telegram.org) → "API development tools".
3. Add the bot to the target channel as an administrator and grant the "Edit Messages" permission (and "Post Messages" if you want the smoke/spike scripts to create test posts).
4. The bot uses an in-memory `StringSession` (no file on disk). Bot-token auth is instant, so there is no MTProto handshake to cache across restarts.

**Known limitation**: Telegram bots cannot iterate channel history (`get_messages`/`iter_messages` raise `BotMethodInvalidError`). The user must therefore supply the exact post URLs; telesoft fetches each post by id and edits it. See the spike ADR at `docs/decisions/2026-07-20-pr-14-spike-telethon.md` for details.

## Limitations (MVP)

- The bot cannot list channel history, so post URLs are entered by the user (one per line in the replace-link form).
- No edit/delete of channels from the UI (backend `PATCH`/`DELETE` endpoints are ready).
- No retry or delete of jobs from the UI (backend `POST /api/jobs/{id}/cancel` is wired; retry/delete are pending).
- WebSocket client is per-page (no shared client in the layout) — each job detail page opens its own socket.
- No polling fallback on the job detail page — if the WebSocket fails, progress is not updated until refresh.

## License

MIT — see [LICENSE](LICENSE).