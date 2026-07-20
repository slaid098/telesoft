# AGENTS.md

## Project

telesoft — Telegram channel post editor (замена ссылок в постах каналов через бота-админа).

## Stack

- **Backend**: Python 3.12+, FastAPI, uvicorn, Pydantic, aiosqlite, Telethon, Loguru
- **Frontend**: SvelteKit 2 + Svelte 5 + TypeScript, Biome, Vitest, Knip
- **Package manager**: uv (backend) + npm (frontend)
- **Quality**: ruff, mypy strict, pytest-asyncio, Biome, pre-commit

## Commands

```bash
uv sync --extra dev                    # Install all deps
uv run ruff check src/ tests/          # Lint
uv run ruff format src/ tests/         # Format
uv run mypy src/                       # Typecheck
uv run pytest                          # Run tests
uv run pre-commit run --all-files      # Run all hooks
cd web && npm ci                       # Install frontend deps
cd web && npm run lint                 # Lint
cd web && npm run typecheck            # Typecheck
cd web && npm run test                 # Run tests
docker compose up --build              # Run full stack
```

## Conventions

- Backend source in `src/telesoft/` (src layout)
- Config via `.env` (see `.env.example` for all variables)
- Session storage in `app_data/bot.session`
- DB in `app_data/telesoft.db`
- Commit style: `type(scope): description` (English, ≤72 chars)
- No comments unless explicitly requested
- One issue = one PR