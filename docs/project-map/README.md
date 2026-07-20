---
module: /
purpose: telesoft — overall structure
key_files:
  - pyproject.toml — Python project config (uv, hatchling, ruff, mypy, pytest)
  - docker-compose.yml — 2 containers (api + web)
  - Dockerfile.api — FastAPI backend image
  - Dockerfile.web — SvelteKit frontend image (adapter-node)
  - .env.example — all env vars documented
  - AGENTS.md — repo-level agent instructions
  - .pre-commit-config.yaml — ruff + mypy hooks
dependencies: []
last_updated: 2026-07-20
---

# telesoft — Project Map

Project map — обновляется docs-reviewer на каждый PR. Содержит схему структуры кода.

## Tech stack

- **Backend:** Python 3.12+, uv, hatchling, FastAPI, aiosqlite, Telethon, loguru
- **Frontend:** SvelteKit 2 + Svelte 5 runes + TypeScript + TailwindCSS + Biome + Vitest + Knip

## Дерево верхнего уровня

```
telesoft/
├── src/telesoft/      # Backend (FastAPI) — см. backend.md
├── tests/             # Backend unit tests — см. tests.md
├── web/               # SvelteKit frontend — см. frontend.md
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
├── .pre-commit-config.yaml  # ruff + mypy hooks — см. ci.md
├── .dockerignore
├── .editorconfig
└── AGENTS.md          # Repo-level agent instructions
```

## Module index

- [backend.md](backend.md) — `src/telesoft/` (FastAPI backend)
- [frontend.md](frontend.md) — `web/` (SvelteKit frontend)
- [docker.md](docker.md) — `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.web`
- [ci.md](ci.md) — `.github/`, `.pre-commit-config.yaml`
- [tests.md](tests.md) — `tests/`, `web/src/tests/`

## Patterns

- **src layout** для backend (`src/telesoft/`)
- **Monorepo**: backend + frontend в одном репо
- **uv** для Python, **npm** для frontend
- **Frozen dataclass** для конфига (`Settings.from_env()`)
- **Adapter-node** для SvelteKit (SSR в Docker)
- **Coverage gate 80%** для backend (pytest --cov-fail-under=80)