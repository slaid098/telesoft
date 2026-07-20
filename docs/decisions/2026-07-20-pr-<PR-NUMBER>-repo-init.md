# ADR — PR #<PR-NUMBER>: repo-init scaffolding

## Статус

Accepted (2026-07-20)

## Контекст

Проект telesoft (Telegram channel post editor) начинает разработку с пустого репозитория (только README/LICENSE/.gitignore на main). Нужна стартовая структура: backend (FastAPI + uv, src layout), frontend (SvelteKit + TS), quality tooling (ruff, mypy, Biome, Vitest, Knip), CI, pre-commit, Dependabot, AGENTS.md, docker-compose.

Референс структуры — репо `slaid098/media-gen` (FastAPI + SvelteKit monorepo, src layout, aiosqlite, Biome, Vitest, Knip, adapter-node). Паттерны копируются 1-в-1 где применимо.

## Решение

Создана структура каталогов и файлов по 6 шагам спецификации issue #1:

1. **Backend skeleton** (Python/FastAPI, src layout): `pyproject.toml` (hatchling, ruff E/W/F/I/B/UP/SIM/C90/PL/RUF/S/TRY/LOG, mypy strict, pytest asyncio_mode=auto --cov-fail-under=80), `src/telesoft/{__init__,py.typed,main,config}.py`, `Dockerfile.api`, `tests/{__init__,conftest,test_health,test_config}.py`, `.dockerignore`, `.editorconfig`, `uv.lock`.
2. **Frontend skeleton** (SvelteKit + TS): `web/package.json`, `web/svelte.config.js`, `web/vite.config.ts`, `web/vitest.config.ts`, `web/tsconfig.json`, `web/biome.json`, `web/knip.json`, `web/postcss.config.js`, `web/tailwind.config.js`, `web/src/{app.html,app.css,app.d.ts,routes/+layout.svelte,routes/+page.svelte,tests/setup.ts,tests/smoke.test.ts}`, `web/Dockerfile.web`, `web/.env.example`, `web/.gitignore`, `web/package-lock.json`.
3. **Docker Compose + env**: `docker-compose.yml` (api + web, telesoft-network bridge, json-file logging), `.env.example` (все переменные с placeholder).
4. **CI + pre-commit + Dependabot**: `.github/workflows/ci.yml` (backend-lint, backend-test, frontend), `.pre-commit-config.yaml` (ruff + mypy), `.github/dependabot.yml` (pip, npm, github-actions), `.github/PULL_REQUEST_TEMPLATE.md`.
5. **AGENTS.md**: repo-level instruction file (Project, Stack, Commands, Conventions).
6. **Docs structure**: `docs/project-map/README.md`, `docs/handoff/.gitkeep`, `docs/decisions/.gitkeep`.

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `httpx>=0.27` добавлен в dev-зависимости (нужен для FastAPI TestClient).
- `tests/test_config.py` добавлен сверх спецификации (покрытие 80% невозможно с одним test_health).
- `web/src/tests/smoke.test.ts` добавлен сверх спецификации (vitest падает без тестовых файлов).
- `web/knip.json` упрощён (media-gen patterns ссылаются на файлы, которых нет в telesoft MVP).
- S104/S105 добавлены в per-file-ignores для tests.

## Альтернативы

- **httpx в main dependencies vs dev**: выбран dev, т.к. TestClient — тестовый инструмент. Альтернатива — main deps (как в media-gen, где httpx используется в рантайме для ComfyClient). Для telesoft MVP httpx в рантайме не нужен.
- **Покрытие 80%**: можно было снизить `--cov-fail-under` до 70%, чтобы пройти с одним test_health. Выбрано добавить test_config.py — сохраняет gate 80% и покрывает реальный код (Settings.from_env).
- **Smoke test для vitest**: можно было использовать `--passWithNoTests` флаг vitest. Выбрано добавить smoke-тест — даёт реальный тестовый файл и гарантирует, что vitest-инфраструктура работает (jsdom, setup.ts).
- **Knip patterns**: можно было оставить media-gen patterns (с hint-ошибками). Выбрано упростить — knip должен быть зелёным.