---
module: docker
purpose: Container orchestration — api + web services
key_files:
  - docker-compose.yml — 2 services (api + web), telesoft-network bridge
  - Dockerfile.api — python:3.13-slim + uv sync
  - Dockerfile.web — multi-stage build → adapter-node runtime
  - .env.example — all env vars with placeholders
  - .dockerignore — excludes .venv, caches, app_data
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# docker — container orchestration

## Structure

```
├── docker-compose.yml   # services: api + web, telesoft-network bridge, json-file logging
├── Dockerfile.api       # python:3.13-slim, COPY --from=ghcr.io/astral-sh/uv:latest, uv sync --frozen --extra dev, CMD uvicorn
├── Dockerfile.web       # multi-stage: build (npm ci + npm run build) → runtime (node:20-slim, adapter-node, PORT=3000)
├── .env.example         # ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, HOST, PORT, LOG_LEVEL, DB_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, SESSION_PATH
└── .dockerignore        # исключает .venv, .mypy_cache, .pytest_cache, .ruff_cache, app_data, web/node_modules
```

## Patterns

- **Bridge network** `telesoft-network` — изоляция сервисов
- **json-file logging** с ротацией 20m×3 файла
- **uv в Docker** через multi-stage COPY (`ghcr.io/astral-sh/uv:latest`)
- **adapter-node** для SvelteKit SSR (PORT=3000)
- **env_file** `.env` для api (все переменные)
- **depends_on** web → api (порядок запуска)
- **Volumes**: `./src` (hot reload для dev), `./app_data` (runtime storage)

## Services

| Service | Image base | Port | CMD |
|---------|-----------|------|-----|
| api     | python:3.13-slim | 8000 | `uvicorn telesoft.main:app --host 0.0.0.0 --port 8000` |
| web     | node:20-slim (runtime) | 3000 | `node build/index.js` (adapter-node) |