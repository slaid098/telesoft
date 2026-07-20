---
module: docker
purpose: Container orchestration — api + web services
key_files:
  - docker-compose.yml — 2 services (api + web), telesoft-network bridge, api healthcheck on /health
  - Dockerfile.api — python:3.13-slim + uv sync (curl available for healthcheck)
  - Dockerfile.web — multi-stage build → adapter-node runtime
  - .env.example — all env vars with placeholders (incl. JOBS_MAX_CONCURRENCY)
  - .dockerignore — excludes .venv, caches, app_data
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# docker — container orchestration

## Structure

```
├── docker-compose.yml   # services: api (healthcheck /health) + web (depends_on api healthy), telesoft-network bridge, json-file logging
├── Dockerfile.api       # python:3.13-slim, COPY --from=ghcr.io/astral-sh/uv:latest, uv sync --frozen --extra dev, CMD uvicorn (curl installed for healthcheck)
├── Dockerfile.web       # multi-stage: build (npm ci + npm run build) → runtime (node:20-slim, adapter-node, PORT=3000)
├── .env.example         # ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, HOST, PORT, LOG_LEVEL, DB_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, SESSION_PATH, JOBS_MAX_CONCURRENCY
└── .dockerignore        # исключает .venv, .mypy_cache, .pytest_cache, .ruff_cache, app_data, web/node_modules
```

## Patterns

- **Bridge network** `telesoft-network` — изоляция сервисов
- **json-file logging** с ротацией 20m×3 файла
- **uv в Docker** через multi-stage COPY (`ghcr.io/astral-sh/uv:latest`)
- **adapter-node** для SvelteKit SSR (PORT=3000)
- **env_file** `.env` для api (все переменные)
- **api healthcheck** — `curl --fail --silent http://localhost:8000/health` каждые 10s (timeout 5s, retries 5, start_period 10s). `curl` установлен в `Dockerfile.api` (`apt-get install -y --no-install-recommends curl`)
- **web depends_on api (service_healthy)** — web стартует только после того как api прошёл healthcheck (заменяет старый bare `depends_on: - api`)
- **Volumes**: `./src` (hot reload для dev), `./app_data` (runtime storage)

## Services

| Service | Image base | Port | Healthcheck | CMD |
|---------|-----------|------|------------|-----|
| api     | python:3.13-slim | 8000 | `curl --fail --silent /health` (10s interval, 5 retries) | `uvicorn telesoft.main:app --host 0.0.0.0 --port 8000` |
| web     | node:20-slim (runtime) | 3000 | (none) | `node build/index.js` (adapter-node) |