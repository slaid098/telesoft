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
├── src/telesoft/      # Backend (FastAPI)
│   ├── main.py        # FastAPI app: lifespan + GET /health
│   └── config.py      # Settings frozen dataclass
├── tests/             # Unit tests
├── web/               # SvelteKit frontend
├── app_data/          # Runtime storage (gitignored except .gitkeep)
├── docs/              # Project map, handoffs, ADRs
├── .github/           # CI workflows, dependabot, PR template
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.web
└── .env.example
```