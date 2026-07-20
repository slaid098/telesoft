---
module: scripts
purpose: Standalone spike/PoC + smoke test scripts — НЕ часть backend (src/telesoft/), не импортируют Settings
key_files:
  - scripts/spike_telethon.py — Telethon bot mode PoC #1 (connect/get_entity/get_messages/send_message/edit_message/session)
  - scripts/spike_telethon_v2.py — Telethon raw API spike #2 (channels.GetMessagesRequest, binary search max_id, range fetch, 5 tests)
  - scripts/smoke_test.py — end-to-end API smoke test (login, channels CRUD, exit 0/1, print output)
dependencies: [telethon, httpx]
last_updated: 2026-07-20
---

# scripts — standalone spike/PoC + smoke test scripts

## Structure

```
scripts/
├── spike_telethon.py       # Telethon bot mode PoC #1 (PR#14) — проверка edit_message для бота-админа на канале
├── spike_telethon_v2.py    # Telethon raw API spike #2 (PR#30) — channels.GetMessagesRequest + binary search + range fetch
└── smoke_test.py           # End-to-end API smoke test (PR#28) — login + channels CRUD against a running backend
```

## Purpose

`scripts/` содержит standalone async Python скрипты для spike'ов, proof-of-concept проверок и smoke test'ов. Эти скрипты **НЕ** являются частью backend (`src/telesoft/`) — они не импортируют `Settings.from_env()`, не используют `aiosqlite` слой, и не попадают под `mypy strict` (CI проверяет только `src/`). Читают env напрямую через `os.environ`.

## Key files

- `scripts/spike_telethon.py` — Telethon bot mode PoC (PR #14, issue #13). Standalone async скрипт: `TelegramClient(session, api_id, api_hash)` + `await client.start(bot_token=...)`. Шаги: `get_me` → `get_entity` → `get_messages` → `send_message` → `edit_message` → проверка session file. Результаты: `get_me`/`get_entity`/`send_message`/`edit_message`/session OK; `get_messages` FAIL (`BotMethodInvalidError` — боты не могут читать историю через MTProto). Exit codes: `0`=SUCCESS, `1`=connect/entity fail, `2`=send_message fail, `3`=edit_message fail.
- `scripts/spike_telethon_v2.py` — Telethon raw API spike #2 (PR #30, issue #29). Standalone async скрипт, проверяет `channels.GetMessagesRequest` (namespace `telethon.tl.functions.channels`, raw API — НЕ `messages.*`) для чтения постов канала через бота-админа. Обходит ограничение PR#14 (`iter_messages`/`get_messages(limit=N)` → `BotMethodInvalidError`). **5 тестов**: (1) `channels.GetMessagesRequest(id=[1,2,3])` → 3 поста ✅; (2) **Binary search max_id** — `lo=1, hi=MAX_PROBE_ID(10000)`, probe `mid=(lo+hi)//2`, если `messages[0].date is not None` → существует (`lo=mid+1`), иначе `hi=mid-1`; найден `max_id=113` за **13 probes** (O(log N), log2(10000)≈13.3) ✅; (3) **Range fetch** `id=list(range(max_id, max_id-N, -1))` → N постов **одним запросом** (вместо N при by-ID fetch) ✅; (4) контроль `messages.GetHistoryRequest` → `BotMethodInvalidError` (expected fail) ✅; (5) контроль `client.iter_messages` → `BotMethodInvalidError` (expected fail, под капотом `GetHistoryRequest`) ✅. Ключевое отличие от PR#14: `channels.GetMessagesRequest` (raw API, namespace `channels.*`) работает для bot-admin, `messages.GetHistoryRequest` (namespace `messages.*`) — нет. `asyncio.sleep(REQUEST_DELAY=1.0)` между запросами (flood control), `FloodWaitError` → `await asyncio.sleep(e.seconds + 1)` → retry через `_retry_on_flood` helper. `InputChannel(id, access_hash)` — id без `-100` prefix, access_hash из `get_entity`. Возвращает `ChannelMessages` (`.messages` атрибут). Креды через `os.environ`: `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`/`TELEGRAM_BOT_TOKEN`. Session `app_data/bot.session` (переиспользуется с PR#14).
- `scripts/smoke_test.py` — end-to-end API smoke test (PR #28, issue #27). Standalone async скрипт через `httpx.AsyncClient`: `POST /api/auth/login` → `GET /api/channels` → `POST /api/channels` (test channel) → `GET /api/channels/{id}` → `DELETE /api/channels/{id}`. Каждый шаг печатает `[OK]`/`[FAIL]`, exit `0` если все шаги прошли, `1` если хотя бы один упал. НЕ запускает replace-link (нужны реальные post URLs — вне scope). Env: `TELESOFT_API_URL` (default `http://localhost:8000`), `TELESOFT_ADMIN_USER` (default `admin`), `TELESOFT_ADMIN_PASS` (default `changeme`). НЕ часть pytest suite (integration test, требует запущенный backend).

## Patterns

- **Standalone, не часть `src/telesoft/`** — нет импорта `Settings`, нет зависимости от DB layer. Env через `os.environ` напрямую.
- **Spike/smoke, не production код** — цель снять риск до/после реализации основной фичи. Не типизируется строго (mypy не проверяет `scripts/`).
- **Изолированные шаги** — каждый шаг в отдельной async функции (`_step_*` для spike, `_<verb>` для smoke), оркестрация в `main()`.
- **Вывод через `print`** (НЕ loguru) — keeps standalone scripts dependency-light. loguru — backend-only dep.
- **Ruff per-file-ignore `scripts/*` = [T201, S603, S101, TRY300]** (PR#30) — `T201` (print), `S603` (subprocess), `S101` (assert) добавлены preemptively; `TRY300` (return inside try) добавлен в PR#30 для `spike_telethon_v2.py` (тест-функции со множеством try/except — ruff предлагает перенести `return` в `else` блоки, но это менее читаемо). PR#14 (`spike_telethon.py`) не требовал per-file-ignore (T201/S603/S101 не в `[tool.ruff.lint.select]`), но PR#30 добавил `TRY300` → пришлось добавить весь список.
- **Session file в `app_data/`** — `app_data/bot.session` создаётся Telethon автоматически, в `.gitignore` (`app_data/*` кроме `.gitkeep`). Переиспользуется между spike #1 (PR#14) и spike #2 (PR#30) — без повторного логина.
- **httpx в dev-deps** — smoke test использует `httpx.AsyncClient` (httpx уже в `[project.optional-dependencies] dev` для FastAPI TestClient). Базовый URL через `base_url=`, относительные пути в запросах.

## Dependencies

- `telethon` (MTProto client library) — для `spike_telethon.py`.
- `httpx` (async HTTP client) — для `smoke_test.py` (уже в dev-deps).
- Остальные (env vars) через `os.environ`.