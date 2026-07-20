---
pr: 14
issue: 13
branch: spike/telegram/telethon-bot-poc
status: ready
created: 2026-07-20
---

# Handoff — PR #14: Telethon bot mode PoC on test channel

## Что сделано

Реализован issue #13 — standalone async spike-скрипт `scripts/spike_telethon.py` (Telethon bot mode) для подтверждения возможности подключения, чтения и редактирования постов канала через бота-админа. Скрипт запущен на тестовом канале `-1003903711726`, результаты зафиксированы.

### Шаг 1: Spike скрипт

- `scripts/spike_telethon.py` — standalone async Python скрипт (НЕ часть `src/telesoft/`, НЕ импортирует `Settings.from_env()` — читает env напрямую через `os.environ`).
- `TelegramClient(SESSION_PATH, api_id, api_hash)` + `await client.start(bot_token=bot_token)` — bot mode.
- `SESSION_PATH = "app_data/bot.session"` (Telethon сам создаёт файл).
- Структура: `_require_env`, `_print_section`, `_print_me`, `_print_entity`, `_print_messages` (helpers), `_step_get_messages`, `_step_send_test_post`, `_step_edit_post`, `_step_session_file` (изолированные шаги), `main()` (оркестрация).
- `TEST_CHANNEL_ID = -1003903711726`, `OLD_LINK = "https://old.example.com/path"`, `NEW_LINK = "https://new.example.com/path"`, `POST_TEXT = f"Test post for spike: {OLD_LINK}"`.
- Возвращает exit code: `0` = SUCCESS, `1` = критический fail (connect/entity), `2` = send_message failed, `3` = edit_message failed.
- НЕ удаляет тестовый пост (оставляет для ручной проверки в канале).

### Шаг 2: .env.example

`.env.example` уже содержит `TELEGRAM_API_ID=`, `TELEGRAM_API_HASH=`, `TELEGRAM_BOT_TOKEN=`, `SESSION_PATH=app_data/bot.session` (из PR #2) — изменений не требуется.

### Шаг 3: Запуск и результаты spike

Команда: `cd /root/workspace/telesoft && uv run python scripts/spike_telethon.py`

**Фактический вывод скрипта:**

```
=== 1. connect (bot mode) ===
bot id:       6164770162
bot username: @server10bot
bot first_name: СЕРВЕР 10 БОТ
bot is_bot:   True

=== 2. resolve channel entity ===
entity type:  Channel
channel id:   3903711726
channel title: Тест portfolio
channel username: (none)

=== 3. get_messages (last 10) — known to fail for bots ===
get_messages FAILED: BotMethodInvalidError: The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by GetHistoryRequest)
note: bots cannot use GetHistoryRequest (MTProto) — expected limitation

=== 4. create test post via send_message ===
send_message OK: id=113 text='Test post for spike: https://old.example.com/path'

=== 5. edit_message (replace link) by id ===
editing post id=113
  old text: 'Test post for spike: https://old.example.com/path'
  new text: 'Test post for spike: https://new.example.com/path'
edit_message OK: link replaced = True

=== 6. session file ===
session file: app_data/bot.session (28672 bytes)

=== spike result: SUCCESS (edit_message works; get_messages does not) ===
```

### Результаты spike по шагам

| Шаг | Ожидание | Факт | Статус |
|-----|----------|------|--------|
| 1. connect (bot mode) | `get_me()` возвращает User с `bot=True` | `id=6164770162`, `@server10bot`, `first_name="СЕРВЕР 10 БОТ"`, `bot=True` | ✅ PASS |
| 2. resolve channel entity | `get_entity(-1003903711726)` → Channel | `Channel id=3903711726 title="Тест portfolio" username=None` | ✅ PASS |
| 3. get_messages (last 10) | Получить последние 10 постов | `BotMethodInvalidError: ...caused by GetHistoryRequest` — боты не могут читать историю через MTProto | ❌ FAIL (ожидаемо) |
| 4. send_message (test post) | Создать пост со ссылкой | `id=113 text='Test post for spike: https://old.example.com/path'` | ✅ PASS |
| 5. edit_message (replace link) | Заменить `old.example.com` → `new.example.com` | `new text='Test post for spike: https://new.example.com/path'`, `link replaced = True` | ✅ PASS |
| 6. session file | `app_data/bot.session` создан | `28672 bytes` | ✅ PASS |

**Итог spike:** SUCCESS — бот-админ может редактировать посты канала через `edit_message` (главная цель). НО `get_messages` (чтение истории) НЕ работает для ботов — это критическое ограничение для архитектуры MVP.

## Почему

До реализации `src/telesoft/core/telegram.py` (Telegram client wrapper для MVP — замена ссылок в постах каналов) нужно было подтвердить, что Telethon в bot mode может:
1. Подключиться как бот — ✅ подтверждено.
2. Читать посты канала (`get_messages`/`iter_messages`) — ❌ НЕ подтверждено (MTProto `GetHistoryRequest` запрещён для ботов).
3. Редактировать посты канала (`edit_message`) — ✅ подтверждено (критический риск снят).
4. Сохранять сессию в файл — ✅ подтверждено.

Spike снял главный риск (edit_message работает), но вскрыл новый: для получения списка постов канала нужен другой подход, т.к. бот не может читать историю через MTProto. Это влияет на архитектуру `core/telegram.py` — см. "Pending".

## Pending

- **Архитектура получения постов канала**: `get_messages`/`iter_messages` НЕ работают для ботов. Варианты для MVP:
  1. **Хранить message_id в БД** (channels + edit_jobs + edit_logs уже спроектированы под это) — пользователь вручную указывает ID поста для редактирования, бот вызывает `edit_message(entity, message_id, text=...)`. Самый простой путь.
  2. **Bot API HTTP** (`/getUpdates`) — но это для входящих сообщений боту, не для истории канала.
  3. **User session (не bot)** — отдельный Telethon client с user-аккаунтом (не бот), у него `get_messages` работает. Но это усложняет auth (phone + code).
  4. **Webhook на новые посты** — бот подписывается на новые посты канала через channel updates, но это не даёт историю.
  - Рекомендация: вариант 1 (message_id в БД) для MVP, вариант 3 (user session) — если нужна история.
- **`core/telegram.py` реализация**: обёртка над Telethon с методами `connect()`, `get_entity(channel_id)`, `edit_message(channel_id, message_id, new_text)`. НЕ использовать `get_messages` — бот не может.
- **Cleanup тестовых постов**: в канале "Тест portfolio" остались 2 тестовых поста (id=112, id=113) с `old.example.com`/`new.example.com`. Не критично, но при желании можно удалить вручную.
- **Telethon version**: `telethon>=1.36` в pyproject (из PR #2) — работает, обновлять не нужно.

## Watch out

- **`get_messages`/`iter_messages` НЕ работают для ботов** — `BotMethodInvalidError: The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by GetHistoryRequest)`. Это ограничение MTProto для bot-аккаунтов. Критично для архитектуры `core/telegram.py` — нельзя использовать `iter_messages` для обхода постов канала. См. "Pending" — альтернативы.
- **`send_message` работает для бота-админа** — бот может создавать посты в канале, где он админ. Это не было главной целью spike, но подтверждено (id=112, id=113).
- **`edit_message` работает для бота-админа** — главная цель spike подтверждена. Бот заменил ссылку в посте канала (`old.example.com` → `new.example.com`). Права админа с "Post Messages" + "Edit Messages" достаточны.
- **`get_entity(channel_id)` работает для ботов** — `Channel` объект с `id`, `title`, `username` (None для приватных каналов). Можно использовать для валидации канала при добавлении.
- **`get_me()` работает для ботов** — возвращает `User` с `bot=True`, `id`, `username`, `first_name`. Подтверждает подключение.
- **Session file**: `app_data/bot.session` (28672 bytes) создаётся автоматически при `client.start(bot_token=...)`. Файл в `.gitignore` (`app_data/*` кроме `.gitkeep`) — НЕ коммитить. При повторном запуске сессия переиспользуется (без повторного логина).
- **Channel ID vs entity ID**: `get_entity(-1003903711726)` возвращает `Channel` с `id=3903711726` (без `-100` prefix). Telethon сам обрабатывает `-100` prefix при resolve. Для `edit_message(entity, msg_id)` можно передавать и исходный `-1003903711726`, и resolved entity.
- **Тестовые посты в канале**: скрипт НЕ удаляет созданные посты (оставляет для ручной проверки). При повторных запусках создаёт новые (id инкрементируется). Если нужно cleanup — добавить `await client.delete_messages(entity, [msg_id])` в конце.
- **Ruff per-file-ignore для `scripts/*` НЕ понадобился** — `T201` (print), `S603` (subprocess), `S101` (assert) не включены в `[tool.ruff.lint.select]`. Скрипт проходит `ruff check` без additional ignores. BLE001 (blind except) не в select — noqa не нужен.
- **mypy не проверяет `scripts/`** — `[tool.mypy]` без `files` опции, CI использует `uv run mypy src/` (только src/). Скрипт не типизирован строго (использует `object` для Telethon-объектов), но это spike — не production код.
- **Exit codes**: `0` = SUCCESS, `1` = критический fail (connect/entity/get_me), `2` = send_message failed (нельзя тестировать edit), `3` = edit_message failed (нет прав или другая ошибка). Полезно для CI/автоматизации.