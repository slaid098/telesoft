---
pr: 54
issue: 53
branch: refactor/docker/production-compose
status: ready
created: 2026-07-21
---

# Handoff — PR 54: merge compose files for production

## Что сделано

Реализован issue #53 — `docker-compose.yml` + `docker-compose.preview.yml` слиты в один production-ready `docker-compose.yml`. nginx проксирует api + web через один порт 8080. Внешний Nginx Proxy Manager (Server 2) терминирует HTTPS и проксирует на этот порт. 3 коммита, 7 файлов изменено (2 создано, 1 удалён, 4 изменено).

### Шаг 1: Слить compose-файлы (commit 1)

- `docker-compose.yml` — единый production-файл. YAML anchor `x-default-logging: &default-logging` (json-file, max-size 20m, max-file 3) применяется через `<<: *default-logging` на все 3 сервиса.
- **api**: bind-mount `./src:/app/src` + `./app_data:/app/app_data` сохранён (быстрое обновление через git pull). `restart: unless-stopped`. Healthcheck на `/health` (существующий). Без `ports` (доступен только через nginx).
- **web**: `VITE_API_BASE=""` (относительный через nginx). Без bind-mount (код внутри образа). `restart: unless-stopped`. `depends_on: api (service_healthy)`. Без `ports` (доступен только через nginx).
- **nginx**: exposes один порт `8080:80`. `depends_on: web (service_started)` + `api (service_healthy)`. `restart: unless-stopped`.
- Network: одна bridge-сеть `telesoft-network`.
- `docker-compose.preview.yml` удалён (был untracked, удалён из filesystem).
- `.env.example` — добавлен комментарий про production deployment (порт 8080, bind-mounts, VITE_API_BASE).
- `Dockerfile.api` — включены pre-existing локальные фиксы (не были закоммичены на main): `PYTHONPATH=/app/src` (was `/app`), `COPY ... README.md ./` (добавлен README.md для hatchling build backend).

### Шаг 2: Переименовать nginx.preview.conf → nginx.conf (commit 2)

- `nginx.conf` создан (контент идентичен `nginx.preview.conf`: upstream api:8000 + web:3000, location /api/ + /health + /).
- `nginx.preview.conf` удалён.
- `Dockerfile.nginx` — `COPY nginx.conf /etc/nginx/conf.d/default.conf` (был `nginx.preview.conf`). Dockerfile.nginx теперь tracked.

### Шаг 3: Healthcheck на web (commit 3)

- `docker-compose.yml` — добавлен healthcheck на web: `["CMD", "curl", "--fail", "--silent", "http://localhost:3000/"]`, interval 10s, timeout 5s, retries 5, start_period 10s.
- `web/Dockerfile.web` — добавлен `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` в runtime stage. `node:22-slim` не содержит curl — без него healthcheck падает с "OCI runtime exec failed: exec: \"curl\": executable file not found".

## Почему

telesoft развёртывается на Linux Server 1 (production). Раздробленная структура (dev compose + preview override) усложняла деплой. Единый compose-файл упрощает `docker compose up --build -d` до одной команды. Внешний Nginx Proxy Manager (Server 2) терминирует HTTPS и проксирует на nginx (Server 1:8080).

### Почему curl добавлен в web Dockerfile

Issue spec требует healthcheck через `curl --fail http://localhost:3000/`. Базовый образ `node:22-slim` (Debian slim) не содержит `curl`. Без установки `curl` healthcheck-команда падает с "executable file not found", контейнер помечается unhealthy. Альтернатива — `wget --spider` (есть в slim), но spec явно указывает curl.

### Почему api и web без ports

В production весь трафик идёт через nginx (порт 8080). Прямой доступ к api (8000) и web (3000) извне не нужен и небезопасен. Docker-сеть `telesoft-network` обеспечивает внутреннюю маршрутизацию.

## Pending

- **Прогон `docker compose up --build -d`** на Server 1 — главный агент должен проверить на реальном сервере. В окружении разработки Docker недоступен (`docker compose` не установлен). YAML валиден структурно, но runtime-проверка не выполнялась.
- **`curl http://localhost:8080/health`** и остальные проверки из issue — выполнить после деплоя.
- **Pre-existing Dockerfile.api изменения** (PYTHONPATH=/app/src, README.md) — были локальными uncommitted изменениями на main, включены в commit 1. Если main уже имеет эти фиксы к моменту merge — конфликтов не будет (same content).
- **Deploy на Server 1** — отдельная задача после этого PR (issue упоминает "Deploy на Server 1 — отдельная задача").

## Watch out

- **YAML anchor `<<: *default-logging`** — merge key syntax. Docker Compose v2 поддерживает. Если используется старый docker-compose v1 (Python) — может не работать. Проверить `docker compose version` на Server 1.
- **curl в web Dockerfile** — добавляет ~5MB к образу. Если размер критичен — переключить healthcheck на `wget --spider --quiet` и убрать curl. Сейчас spec требует curl.
- **nginx depends_on web: service_started** (не `service_healthy`) — nginx стартует до того как web пройдёт healthcheck. Если web падает на старте, nginx возвращает 502. Это намеренно — nginx не должен ждать web healthcheck (может быть долгим при npm ci). Рассмотреть `service_healthy` если нужны stricter guarantees.
- **`Dockerfile.api` PYTHONPATH=/app/src** — src layout: пакет `telesoft` в `/app/src/telesoft/`. `PYTHONPATH=/app/src` позволяет `import telesoft`. Без этого uvicorn не найдёт `telesoft.main:app`.
- **bind-mount `./src:/app/src`** — код монтируется поверх скопированного в образе. Изменения через `git pull` видны сразу (без rebuild). Но `pip install` deps требует rebuild образа (deps в `/app/.venv/`).
