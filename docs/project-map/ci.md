---
module: .github
purpose: CI workflows, Dependabot, PR template, pre-commit hooks
key_files:
  - .github/workflows/ci.yml — 3 jobs: backend-lint, backend-test, frontend
  - .github/dependabot.yml — pip, npm, github-actions (weekly)
  - .github/PULL_REQUEST_TEMPLATE.md — Что сделано / Почему / Связанные issue
  - .pre-commit-config.yaml — ruff (--fix + format) + mypy
dependencies: [backend, frontend]
last_updated: 2026-07-20
---

# ci — .github/ + pre-commit

## Structure

```
.github/
├── workflows/
│   └── ci.yml                    # 3 jobs, trigger push/PR в main
├── dependabot.yml                # pip (/), npm (/web), github-actions (/), weekly
└── PULL_REQUEST_TEMPLATE.md      # Что сделано / Почему / Связанные issue

.pre-commit-config.yaml           # ruff (--fix + ruff-format v0.15.0) + mypy (v1.18.2)
```

## CI jobs (`.github/workflows/ci.yml`)

| Job | Runner | Steps |
|-----|--------|-------|
| backend-lint | ubuntu-latest | checkout@v4 → setup-uv@v3 (enable-cache) → uv sync → ruff check → ruff format --check → mypy src/ |
| backend-test | ubuntu-latest | checkout@v4 → setup-uv@v3 → uv sync → pytest |
| frontend | ubuntu-latest | checkout@v4 → setup-node@v4 (node 20, cache npm) → npm ci → lint → typecheck → test |

Trigger: push + pull_request в main.

## Pre-commit hooks (`.pre-commit-config.yaml`)

- **ruff** — `--fix` + `ruff-format` v0.15.0
- **mypy** — v1.18.2, additional_dependencies: fastapi, pydantic, httpx, aiosqlite, telethon

## Dependabot (`.github/dependabot.yml`)

- pip (`/`) — weekly
- npm (`/web`) — weekly
- github-actions (`/`) — weekly

## Patterns

- **uv cache** в CI (enable-cache: true в setup-uv)
- **npm cache** в CI (cache: npm в setup-node)
- **3 параллельных job'а** — backend-lint, backend-test, frontend независимы
- **Branch protection** (вручную после первого зелёного CI): require backend-lint, backend-test, frontend