---
pr: 54
issue: 53
status: Accepted
created: 2026-07-21
---

# ADR — PR 54: merge compose files for production

## Статус

Accepted (2026-07-21). Реализует issue #53. Заменяет раздробленную структуру (dev `docker-compose.yml` + preview `docker-compose.preview.yml` override) одним production-ready compose-файлом.

## Контекст

telesoft развёртывается на Linux Server 1 (production). Структура Docker Compose была раздроблена:

- `docker-compose.yml` (dev): api (bind-mount src/, ports 8000) + web (bind-mount, ports 3000). Прямой доступ к обоим сервисам извне.
- `docker-compose.preview.yml` (override): добавлял nginx (порт 8080), убирал volumes, `VITE_API_BASE=""`. Запускался через `docker compose -f docker-compose.yml -f docker-compose.preview.yml up`.

Два файла усложняли деплой: нужно помнить флаг `-f`, override-файл мог рассинхронизироваться с основным. Внешний Nginx Proxy Manager (Server 2) терминирует HTTPS и проксирует на один порт Server 1.

Референс: Digital Factory (`github.com/slaid098/digital_factory`) — один compose-файл, YAML anchors для logging, `restart: unless-stopped`, healthcheck'и.

## Решение

**Единый `docker-compose.yml`** с 3 сервисами (api, web, nginx) и одной bridge-сетью:

1. **YAML anchor `x-default-logging: &default-logging`** (json-file, max-size 20m, max-file 3) — применяется через `<<: *default-logging` на все 3 сервиса. DRY для logging config. Паттерн из digital_factory.

2. **api**: bind-mount `./src:/app/src` + `./app_data:/app/app_data` сохранён (быстрое обновление через `git pull` без rebuild). `restart: unless-stopped`. Healthcheck на `/health`. Без `ports` (доступен только через nginx). `env_file: .env`.

3. **web**: `VITE_API_BASE=""` (относительный через nginx). Без bind-mount (код внутри образа, как в preview). `restart: unless-stopped`. `depends_on: api (service_healthy)`. Healthcheck: `curl --fail --silent http://localhost:3000/`. Без `ports`.

4. **nginx**: exposes один порт `8080:80`. `depends_on: web (service_started)` + `api (service_healthy)`. `restart: unless-stopped`. Проксирует `/api/` и `/health` → api:8000, `/` → web:3000.

5. **`nginx.preview.conf` → `nginx.conf`** — переименован (больше не "preview"). `Dockerfile.nginx` обновлён: `COPY nginx.conf /etc/nginx/conf.d/default.conf`.

6. **curl в web Dockerfile** — `node:22-slim` не содержит `curl`. Добавлен `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` в runtime stage для healthcheck.

7. **`docker-compose.preview.yml` удалён** — больше не нужен.

## Альтернативы

1. **Сохранить два compose-файла** (dev + preview override) — плюс: dev-окружение с прямыми портами для локальной разработки. Минус: усложняет деплой (`-f` флаг), override может рассинхронизироваться. Отклонено — issue явно требует один файл. Dev-окружение можно получить через `docker compose run` или profile (если понадобится).

2. **nginx depends_on web: service_healthy** вместо `service_started` — плюс: nginx стартует только когда web готов. Минус: если web healthcheck медленный (npm ci в runtime), nginx ждёт дольше. Отклонено — `service_started` достаточно (nginx возвращает 502 пока web поднимается, это acceptable для startup).

3. **`wget --spider` вместо curl** для healthcheck — плюс: `wget` есть в `node:22-slim` (не нужен apt-get install). Минус: issue spec явно указывает `curl --fail`. Отклонено — следуем spec.

4. **Убрать bind-mount с api** (полностью в образе, как web) — плюс: иммутабельный образ, воспроизводимость. Минус: для обновления кода нужен полный rebuild (`docker compose build api`). Отклонено — issue явно требует сохранить bind-mount для быстрого обновления через `git pull`.

5. **Profile-based compose** (dev profile с прямыми портами + production profile с nginx) — плюс: один файл, два режима. Минус: усложняет compose (profiles), избыточно для MVP. Отклонено — production-only достаточно; dev использует `uv run uvicorn` + `npm run dev` напрямую.
