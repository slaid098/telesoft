# ADR — PR #__PR_NUMBER__: Finalize README and add end-to-end docker-compose smoke test

## Статус

Accepted (2026-07-20) — реализована финальная документация MVP (README + project-map итоговая схема) и standalone end-to-end smoke test для проверки docker-compose; добавлен healthcheck для `api` service в docker-compose.README.md обновлён с 12 секциями (Overview, Architecture, Stack, Prerequisites, Getting Started Docker, Getting Started Local Dev, Environment Variables, Testing, Project Structure, Bot setup, Limitations, License). `docs/project-map/README.md` — итоговая схема с архитектурной диаграммой, module index, quick links на ADRs/handoffs. `scripts/smoke_test.py` — standalone async скрипт через `httpx` (НЕ loguru, print), проверяет login + channels CRUD, exit 0/1. `docker-compose.yml` — `curl /health` healthcheck для api, `web` depends_on api с `condition: service_healthy`. `.env.example` — добавлен `JOBS_MAX_CONCURRENCY` (был в `Settings.from_env()` с PR#22, но не задокументирован).

## Контекст

telesoft — Telegram channel post editor (MVP). После PR#2-26: backend (auth, channels CRUD, jobs/replace-link runner, WS, telegram client) + frontend (login, channels list+detail, replace-link form, jobs list+detail с WS realtime). Docker-compose.yml + .env.example созданы в PR#2. README.md — минимальный placeholder (13 строк). `docs/project-map/README.md` — структура без архитектурной диаграммы и quick links на ADRs/handoffs. Smoke test отсутствовал — единственной end-to-end проверкой были unit tests (pytest, 101 тестов) + frontend Vitest (26 тестов), но интеграция HTTP API + lifespan (init_db, start_client) + DB не покрывалась. `docker-compose.yml` использовал bare `depends_on: - api` (только порядок запуска, без проверки health).

Решения, которые надо было принять:
1. README: перезаписать или обновить существующую структуру?
2. Архитектурная диаграмма: текстовая ASCII или Mermaid или image?
3. Smoke test: `httpx` (async) или `urllib` (sync, stdlib) или `requests` (sync, dep)?
4. Smoke test: loguru (как backend) или print (standalone)?
5. Smoke test: включать replace-link flow или только API plumbing?
6. Smoke test: standalone скрипт или pytest integration test marker?
7. docker-compose healthcheck: curl /health или python -c или wget?
8. `depends_on`: bare `depends_on: - api` или `condition: service_healthy`?
9. `.env.example`: какие vars включать (только что задокументированы в PR#2 или все из `Settings.from_env()`)?
10. Handoff/ADR: после PR number известен или с placeholder?

## Решение

### README: обновить, не перезаписать

- Сохранены существующие секции из PR#2 (Stack — расширен, Status — удалён т.к. README теперь полноценный). Добавлены Overview, Architecture, Prerequisites, Getting Started (Docker + Local Dev), Environment Variables (таблица), Testing, Project Structure, Bot setup, Limitations, License.
- **Почему не перезаписать**: сохранение git history — `git blame` показывает какие строки добавлены в каком PR. Полная перезапись потеряла бы context.
- **Альтернатива**: перезаписать с нуля (clean slate) — проще писать, но теряет git history.

### Архитектурная диаграмма: текстовая ASCII

- ASCII-арт (box-drawing символы `┌─┐│└┘├┤▼`) — рендерится в любом markdown viewer (GitHub, IDE, terminal), не требует JS.
- Три слоя: Browser (SvelteKit) ↔ FastAPI backend ↔ SQLite + Telegram MTProto. Стрелки с подписями (HTTP /api/*, WS /api/ws, aiosqlite, Telethon).
- **Почему не Mermaid**: Mermaid требует JS на GitHub (рендерится через GitHub's mermaid integration), не виден в plain text preview (IDE без mermaid plugin, terminal cat). ASCII — universal.
- **Альтернатива**: Mermaid ( prettier на GitHub, но требует JS), image (PNG/SVG — не version-control friendly, не обновляется с кодом).

### Smoke test: `httpx` (async)

- `httpx.AsyncClient` с `base_url=` и относительными путями в запросах. Async — соответствует backend stack (FastAPI/aiosqlite/Telethon все async). `httpx` уже в dev-deps (для FastAPI TestClient с PR#2).
- Cookie persistence: `httpx.AsyncClient` автоматически хранит cookies между запросами (login cookie → list/create/get/delete authenticated).
- **Почему не `urllib`**: stdlib (нет dep), но sync (threading для async-like behaviour — overkill), нет cookie persistence из коробки, verbose API (Request objects, manual headers).
- **Почему не `requests`**: sync, новый dep (не в dev-deps), нет async support (`requests` sync only, `httpx` — both).
- **Альтернатива**: `urllib` (stdlib, но sync + verbose), `requests` (sync, dep), `aiohttp` (async, но новый dep).

### Smoke test: `print` (НЕ loguru)

- `print` для вывода (`[OK]`/`[FAIL]` format), без loguru imports.
- **Почему не loguru**: standalone скрипт должен быть dependency-light. loguru — backend runtime dep, добавлять его в scripts/ расходует dev-deps budget без value (нет structured logging needs для smoke test). `print` — stdlib, достаточно для [OK]/[FAIL] формата.
- **Паттерн из `spike_telethon.py`**: тот же подход (PR#14) — `print` для вывода, без loguru. Консистентность.
- **Альтернатива**: loguru (structured logging, но overkill для smoke test), `logging` (stdlib, но verbose config для простого [OK]/[FAIL]).

### Smoke test: НЕ включает replace-link flow

- 5 шагов: login → list channels → create channel → get by id → delete. НЕ запускает `POST /api/channels/{id}/replace-link` (нужны реальные post URLs + подключенный бот + канал).
- **Почему только CRUD**: smoke test проверяет API plumbing (auth, DB, JSON serialization, HTTP status codes) — это min viable e2e проверка. Replace-link требует Telegram-зависимостей (бот, канал, post URLs) которые не доступны в CI/dev окружении без реальных кред.
- **Альтернатива**: включить replace-link с mock Telethon (но тогда это уже не smoke test, а integration test с mocks — юнит-тесты это уже покрывают). Или параметризовать через env (но усложняет скрипт, smoke test должен быть simple).

### Smoke test: standalone скрипт (НЕ pytest integration test)

- `scripts/smoke_test.py` — standalone, запускается через `uv run python scripts/smoke_test.py`. НЕ в `tests/` (CI pytest их не запускает как part of unit suite).
- **Почему не pytest**: smoke test требует running backend (Docker compose up или `uv run uvicorn`). pytest unit tests self-contained (TestClient + in-memory mocks). Mixing — разные setup requirements. Standalone скрипт с explicit env vars (`TELESOFT_API_URL`) — cleaner separation.
- **Альтернатива**: pytest integration test marker (`@pytest.mark.integration`) с skip if `TELESOFT_API_URL` not set — но pytest config `addopts = "--cov=telesoft --cov-report=term-missing --cov-fail-under=80"` сломается (smoke test не покрывает `src/telesoft/`, coverage падает). Отдельный скрипт — cleaner.

### docker-compose healthcheck: `curl /health`

- `test: ["CMD", "curl", "--fail", "--silent", "http://localhost:8000/health"]` — `curl` уже установлен в `Dockerfile.api` (`apt-get install -y --no-install-recommends curl git procps` с PR#2). `--fail` — exit non-zero если HTTP status >= 400. `--silent` — без progress output в logs.
- `interval: 10s`, `timeout: 5s`, `retries: 5`, `start_period: 10s` — стандартные значения для web service (не слишком частый, retries 5 даёт ~50s до unhealthy).
- **Почему не python**: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"` — работает без curl dep, но verbose и медленнее (python startup). `curl` — standard tool для HTTP health checks.
- **Почему не wget**: `wget` не всегда установлен в slim images. `curl` — уже в `Dockerfile.api`.
- **Альтернатива**: `python -c` (без curl dep, но verbose), `wget` (если нет curl), healthcheck endpoint на другой path (но `/health` уже есть с PR#2).

### `depends_on`: `condition: service_healthy`

- `web` service: `depends_on: { api: { condition: service_healthy } }` — web стартует только после того как api прошёл healthcheck (3 consecutive successful checks = healthy).
- **Почему не bare `depends_on: - api`**: bare `depends_on` только ordering — web стартует после api container start, но api может ещё не быть ready (uvicorn startup + init_db + start_client — секунды). Без healthcheck-gated startup web может упасть на first request если api ещё не ready.
- **Trade-off**: если healthcheck долго не проходит (uvicorn fail), web вообще не стартует. Но это desired behavior — нет смысла стартовать web без working backend.
- **Альтернатива**: bare `depends_on` (просто ordering), retry logic в web (но web не знает про api health), custom wait script в web entrypoint (overkill).

### `.env.example`: все 12 vars из `Settings.from_env()`

- Добавлен `JOBS_MAX_CONCURRENCY=3` (был в `Settings.from_env()` с PR#22, default 3, но отсутствовал в `.env.example`). Теперь 12 vars: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `HOST`, `PORT`, `LOG_LEVEL`, `DB_PATH`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`, `SESSION_PATH`, `JOBS_MAX_CONCURRENCY`.
- **Почему не было добавлено в PR#22**: oversight — `Settings.from_env()` обновлён, `.env.example` забыт. Этот PR фиксит.
- **Альтернатива**: оставить как есть (но тогда юзер не знает про `JOBS_MAX_CONCURRENCY` из `.env.example`).

### Handoff/ADR: placeholder для PR number

- Handoff файл: `docs/handoff/pr-__PR_NUMBER__-finalize-readme.md`. ADR файл: `docs/decisions/2026-07-20-pr-__PR_NUMBER__-finalize-readme.md`. После PR create, placeholder `__PR_NUMBER__` заменяется на реальный номер в обоих файлах + в handoff frontmatter `pr: __PR_NUMBER__`, отдельный коммит `docs(handoff): set PR number`.
- **Почему placeholder**: handoff/ADR создаются до PR create (нужны в branch). PR number известен только после `gh pr create`. Pattern: write with placeholder → push → create PR → get number → sed replace → amend-or-new-commit → push. Используем new commit (не amend — explicit history).
- **Альтернатива**: создать PR без handoff, потом commit handoff с реальным номером. Но тогда первый push не имеет handoff (CI/docs-reviewer не видит). Placeholder + fix commit — компромисс.

## Альтернативы

### README: перезаписать vs обновить
- **Обновить** (выбрано): сохраняет git history,渐进.
- **Перезаписать**: clean slate, но теряет context.

### Архитектурная диаграмма: ASCII vs Mermaid vs image
- **ASCII** (выбрано): universal, no JS, version-control friendly.
- **Mermaid**: prettier на GitHub, но требует JS.
- **Image**: не version-control friendly.

### Smoke test: httpx vs urllib vs requests
- **httpx** (выбрано): async, уже в dev-deps, cookie persistence.
- **urllib**: stdlib, но sync + verbose.
- **requests**: sync, новый dep.

### Smoke test: print vs loguru
- **print** (выбрано): standalone, dependency-light.
- **loguru**: backend dep, overkill для [OK]/[FAIL].

### Smoke test: CRUD only vs include replace-link
- **CRUD only** (выбрано): min viable e2e, no Telegram deps.
- **Include replace-link**: requires real bot + post URLs, не viable для CI.

### Smoke test: standalone vs pytest integration marker
- **Standalone** (выбрано): cleaner separation, не ломает coverage gate.
- **pytest integration marker**: mixing unit + integration, coverage gate conflict.

### docker-compose healthcheck: curl vs python vs wget
- **curl** (выбрано): уже установлен, standard tool.
- **python -c**: без curl dep, но verbose.
- **wget**: не всегда в slim images.

### `depends_on`: bare vs `condition: service_healthy`
- **`condition: service_healthy`** (выбрано): web ждёт ready api.
- **bare `depends_on`**: только ordering, web может упасть на first request.

## Последствия

- 4 коммита: README+project-map, smoke_test, docker healthcheck, handoff+ADR.
- README.md: 13 строк → ~150 строк, 12 секций.
- docs/project-map/README.md: обновлено с архитектурной диаграммой + quick links.
- scripts/smoke_test.py: новый файл, 164 строки, standalone async.
- docker-compose.yml: +6 строк (healthcheck + depends_on condition).
- .env.example: +1 строка (`JOBS_MAX_CONCURRENCY=3`).
- docs/project-map/scripts.md, docker.md: обновлены.
- `ruff check scripts/smoke_test.py` — green.
- `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"` — valid YAML.
- `docker compose config` НЕ проверялся (docker недоступен в dev окружении, как и в PR#2).

## Связанные ADR

- ADR PR#2 (repo init) — `.env.example`, `docker-compose.yml`, `Dockerfile.api` (curl installed).
- ADR PR#14 (telethon bot mode spike) — bot setup instructions, `BotMethodInvalidError` limitation.
- ADR PR#22 (replace-link runner + WS) — `JOBS_MAX_CONCURRENCY` setting (Settings.from_env field since PR#22).
- ADR PR#26 (channels UI) — MVP frontend complete, README Limitations section reflects UI state.