---
module: scripts
purpose: Standalone spike/PoC + smoke test scripts — НЕ часть backend (src/telesoft/), не импортируют Settings
key_files:
  - scripts/spike_telethon.py — Telethon bot mode PoC (connect/get_entity/get_messages/send_message/edit_message/session)
  - scripts/smoke_test.py — end-to-end API smoke test (login, channels CRUD, exit 0/1, print output)
dependencies: [telethon, httpx]
last_updated: 2026-07-20
---

# scripts — standalone spike/PoC + smoke test scripts

## Structure

```
scripts/
├── spike_telethon.py   # Telethon bot mode PoC — проверка edit_message для бота-админа на канале
└── smoke_test.py       # End-to-end API smoke test — login + channels CRUD against a running backend
```

## Purpose

`scripts/` содержит standalone async Python скрипты для spike'ов, proof-of-concept проверок и smoke test'ов. Эти скрипты **НЕ** являются частью backend (`src/telesoft/`) — они не импортируют `Settings.from_env()`, не используют `aiosqlite` слой, и не попадают под `mypy strict` (CI проверяет только `src/`). Читают env напрямую через `os.environ`.

## Key files

- `scripts/spike_telethon.py` — Telethon bot mode PoC (PR #14, issue #13). Standalone async скрипт: `TelegramClient(session, api_id, api_hash)` + `await client.start(bot_token=...)`. Шаги: `get_me` → `get_entity` → `get_messages` → `send_message` → `edit_message` → проверка session file. Результаты: `get_me`/`get_entity`/`send_message`/`edit_message`/session OK; `get_messages` FAIL (`BotMethodInvalidError` — боты не могут читать историю через MTProto). Exit codes: `0`=SUCCESS, `1`=connect/entity fail, `2`=send_message fail, `3`=edit_message fail.
- `scripts/smoke_test.py` — end-to-end API smoke test (PR #28, issue #27). Standalone async скрипт через `httpx.AsyncClient`: `POST /api/auth/login` → `GET /api/channels` → `POST /api/channels` (test channel) → `GET /api/channels/{id}` → `DELETE /api/channels/{id}`. Каждый шаг печатает `[OK]`/`[FAIL]`, exit `0` если все шаги прошли, `1` если хотя бы один упал. НЕ запускает replace-link (нужны реальные post URLs — вне scope). Env: `TELESOFT_API_URL` (default `http://localhost:8000`), `TELESOFT_ADMIN_USER` (default `admin`), `TELESOFT_ADMIN_PASS` (default `changeme`). НЕ часть pytest suite (integration test, требует запущенный backend).

## Patterns

- **Standalone, не часть `src/telesoft/`** — нет импорта `Settings`, нет зависимости от DB layer. Env через `os.environ` напрямую.
- **Spike/smoke, не production код** — цель снять риск до/после реализации основной фичи. Не типизируется строго (mypy не проверяет `scripts/`).
- **Изолированные шаги** — каждый шаг в отдельной async функции (`_step_*` для spike, `_<verb>` для smoke), оркестрация в `main()`.
- **Вывод через `print`** (НЕ loguru) — keeps standalone scripts dependency-light. loguru — backend-only dep.
- **Ruff per-file-ignore НЕ нужен** — `T201` (print), `S603` (subprocess), `S101` (assert) не включены в `[tool.ruff.lint.select]`. Скрипты проходят `ruff check` без additional ignores.
- **Session file в `app_data/`** — `app_data/bot.session` создаётся Telethon автоматически, в `.gitignore` (`app_data/*` кроме `.gitkeep`).
- **httpx в dev-deps** — smoke test использует `httpx.AsyncClient` (httpx уже в `[project.optional-dependencies] dev` для FastAPI TestClient). Базовый URL через `base_url=`, относительные пути в запросах.

## Dependencies

- `telethon` (MTProto client library) — для `spike_telethon.py`.
- `httpx` (async HTTP client) — для `smoke_test.py` (уже в dev-deps).
- Остальные (env vars) через `os.environ`.