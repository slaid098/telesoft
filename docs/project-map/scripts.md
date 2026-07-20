---
module: scripts
purpose: Standalone spike/PoC scripts — НЕ часть backend (src/telesoft/), не импортируют Settings
key_files:
  - scripts/spike_telethon.py — Telethon bot mode PoC (connect/get_entity/get_messages/send_message/edit_message/session)
dependencies: [telethon]
last_updated: 2026-07-20
---

# scripts — standalone spike/PoC scripts

## Structure

```
scripts/
└── spike_telethon.py   # Telethon bot mode PoC — проверка edit_message для бота-админа на канале
```

## Purpose

`scripts/` содержит standalone async Python скрипты для spike'ов и proof-of-concept проверок. Эти скрипты **НЕ** являются частью backend (`src/telesoft/`) — они не импортируют `Settings.from_env()`, не используют `aiosqlite` слой, и не попадают под `mypy strict` (CI проверяет только `src/`). Читают env напрямую через `os.environ`.

## Key files

- `scripts/spike_telethon.py` — Telethon bot mode PoC (PR #14, issue #13). Standalone async скрипт: `TelegramClient(session, api_id, api_hash)` + `await client.start(bot_token=...)`. Шаги: `get_me` → `get_entity` → `get_messages` → `send_message` → `edit_message` → проверка session file. Результаты: `get_me`/`get_entity`/`send_message`/`edit_message`/session OK; `get_messages` FAIL (`BotMethodInvalidError` — боты не могут читать историю через MTProto). Exit codes: `0`=SUCCESS, `1`=connect/entity fail, `2`=send_message fail, `3`=edit_message fail.

## Patterns

- **Standalone, не часть `src/telesoft/`** — нет импорта `Settings`, нет зависимости от DB layer. Env через `os.environ` напрямую.
- **Spike, не production код** — цель снять риск до реализации основной фичи. Не типизируется строго (mypy не проверяет `scripts/`).
- **Изолированные шаги** — каждый шаг spike'а в отдельной async функции (`_step_*`), оркестрация в `main()`.
- **Ruff per-file-ignore НЕ нужен** — `T201` (print), `S603` (subprocess), `S101` (assert) не включены в `[tool.ruff.lint.select]`. Скрипт проходит `ruff check` без additional ignores.
- **Session file в `app_data/`** — `app_data/bot.session` создаётся Telethon автоматически, в `.gitignore` (`app_data/*` кроме `.gitkeep`).

## Dependencies

- `telethon` (MTProto client library) — единственная runtime зависимость. Остальные (env vars) через `os.environ`.