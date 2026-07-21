---
module: docker
purpose: Container orchestration — api + web + nginx (production single-port)
key_files:
  - docker-compose.yml — 3 services (api + web + nginx), telesoft-network bridge, YAML anchor logging, restart: unless-stopped
  - Dockerfile.api — python:3.13-slim + uv sync (curl available for healthcheck), PYTHONPATH=/app/src
  - Dockerfile.nginx — nginx:alpine + COPY nginx.conf
  - web/Dockerfile.web — multi-stage build → adapter-node runtime (curl installed for healthcheck)
  - nginx.conf — upstream api:8000 + web:3000, locations /api/ /health /
  - .env.example — all env vars + production deployment notes (port 8080, bind-mounts, VITE_API_BASE)
  - .dockerignore — excludes .venv, caches, app_data
dependencies: [backend, frontend]
last_updated: 2026-07-21
---

# docker — container orchestration

## Structure

```
├── docker-compose.yml   # 3 services: api (healthcheck /health, no ports) + web (healthcheck curl /, depends_on api healthy, no ports) + nginx (port 8080:80, depends_on web started + api healthy); telesoft-network bridge; YAML anchor x-default-logging; restart: unless-stopped
├── Dockerfile.api       # python:3.13-slim, COPY --from=ghcr.io/astral-sh/uv:latest, PYTHONPATH=/app/src, COPY pyproject.toml uv.lock README.md, uv sync --frozen --extra dev, CMD uvicorn (curl installed for healthcheck)
├── Dockerfile.nginx     # nginx:alpine, COPY nginx.conf /etc/nginx/conf.d/default.conf
├── web/Dockerfile.web   # multi-stage: build (npm ci + npm run build) → runtime (node:22-slim, apt-get install curl, adapter-node, PORT=3000)
├── nginx.conf           # upstream api_backend (api:8000) + web_frontend (web:3000); server listen 80; location /api/ (proxy_pass api, WS upgrade, 300s timeout) + /health (proxy_pass api) + / (proxy_pass web)
├── .env.example         # ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, HOST, PORT, LOG_LEVEL, DB_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, TELEGRAM_SESSION_STRING (PR#48), SESSION_PATH, JOBS_MAX_CONCURRENCY + production deployment notes
└── .dockerignore        # исключает .venv, .mypy_cache, .pytest_cache, .ruff_cache, app_data, web/node_modules
```

## Patterns

- **Single production compose** — один `docker-compose.yml` (PR#54 merged dev + preview override). Внешний Nginx Proxy Manager (Server 2) терминирует HTTPS, проксирует на nginx (Server 1:8080).
- **YAML anchor `x-default-logging: &default-logging`** (json-file, max-size 20m, max-file 3) — DRY для logging, применяется через `<<: *default-logging` на все 3 сервиса.
- **Bridge network** `telesoft-network` — изоляция сервисов.
- **uv в Docker** через multi-stage COPY (`ghcr.io/astral-sh/uv:latest`).
- **adapter-node** для SvelteKit SSR (PORT=3000).
- **env_file** `.env` для api (все переменные).
- **restart: unless-stopped** на все 3 сервиса.
- **api healthcheck** — `curl --fail --silent http://localhost:8000/health` каждые 10s (timeout 5s, retries 5, start_period 10s). `curl` установлен в `Dockerfile.api`.
- **web healthcheck** — `curl --fail --silent http://localhost:3000/` каждые 10s. `curl` установлен в `web/Dockerfile.web` runtime stage (`node:22-slim` не содержит curl по умолчанию).
- **web depends_on api (service_healthy)** — web стартует только после того как api прошёл healthcheck.
- **nginx depends_on web (service_started) + api (service_healthy)** — nginx стартует когда web запущен (не ждёт healthcheck) и api здоров.
- **No direct ports** на api и web — весь трафик через nginx (порт 8080). Безопаснее для production.
- **Volumes on api**: `./src` (hot reload через git pull без rebuild), `./app_data` (runtime storage). Web без bind-mount (код внутри образа).
- **VITE_API_BASE=""** — относительные пути через nginx (не абсолютный URL).

## Services

| Service | Image base | Port (host) | Healthcheck | CMD |
|---------|-----------|-------------|------------|-----|
| api     | python:3.13-slim | (none, internal) | `curl --fail --silent /health` (10s interval, 5 retries) | `uvicorn telesoft.main:app --host 0.0.0.0 --port 8000` |
| web     | node:22-slim (runtime) | (none, internal) | `curl --fail --silent /` (10s interval, 5 retries) | `node build/index.js` (adapter-node) |
| nginx   | nginx:alpine | 8080:80 | (none) | nginx default (uses nginx.conf) |