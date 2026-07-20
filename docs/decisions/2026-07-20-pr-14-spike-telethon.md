# ADR — PR #14: Telethon bot mode PoC on test channel

## Статус

Accepted (2026-07-20) — spike прошёл: главная цель (edit_message для бота-админа на канале) подтверждена. Найдено ограничение: `get_messages` не работает для ботов (MTProto `GetHistoryRequest` запрещён) — влияет на архитектуру `core/telegram.py`, но не блокирует MVP (см. "Решение").

## Контекст

До реализации `src/telesoft/core/telegram.py` (Telegram client wrapper для MVP — замена ссылок в постах каналов через бота-админа) нужно было подтвердить, что Telethon в bot mode может:

1. Подключиться как бот (`TelegramClient` + `bot_token`) — проверить через `get_me()`.
2. Читать посты канала, где бот — админ (`get_messages`/`iter_messages`).
3. Редактировать посты канала (`edit_message`) — критично, т.к. не все admin rights дают это право, и Telegram API для каналов имеет особенности (posts vs messages, signed forwards, media).
4. Сохранять сессию в файл (`app_data/bot.session`) для переиспользования между запусками без повторного логина.

Тестовый канал: `-1003903711726` ("Тест portfolio"), бот `@server10bot` (id `6164770162`) — админ с правом редактирования постов. Креды в окружении: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`.

Это **spike** — proof-of-concept скрипт `scripts/spike_telethon.py`, НЕ production код. Цель: снять риск до основной работы.

## Решение

Spike выполнен через standalone async скрипт `scripts/spike_telethon.py` (НЕ часть `src/telesoft/`, читает env через `os.environ` напрямую — без `Settings.from_env()`). Результаты по шагам:

1. **Connect (bot mode)** — ✅ PASS. `TelegramClient(session, api_id, api_hash)` + `await client.start(bot_token=bot_token)` + `get_me()` → `User(id=6164770162, username="server10bot", first_name="СЕРВЕР 10 БОТ", bot=True)`. Подключение как бот работает, сессия сохраняется в `app_data/bot.session` (28672 bytes).
2. **Resolve channel entity** — ✅ PASS. `get_entity(-1003903711726)` → `Channel(id=3903711726, title="Тест portfolio", username=None)`. Telethon корректно обрабатывает `-100` prefix.
3. **get_messages (last 10)** — ❌ FAIL. `BotMethodInvalidError: The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by GetHistoryRequest)`. **Боты не могут читать историю сообщений через MTProto** — это ограничение Telegram API, не Telethon. `iter_messages` использует тот же `GetHistoryRequest` → тоже не работает.
4. **send_message (test post)** — ✅ PASS. `send_message(entity, POST_TEXT)` создал пост `id=113 text='Test post for spike: https://old.example.com/path'`. Бот-админ может писать в канал.
5. **edit_message (replace link)** — ✅ PASS. `edit_message(entity, post, text=new_text)` заменил `old.example.com` → `new.example.com`. `new text='Test post for spike: https://new.example.com/path'`, `link replaced = True`. **Главная цель spike подтверждена.**
6. **Session file** — ✅ PASS. `app_data/bot.session` (28672 bytes) создан, в `.gitignore` (`app_data/*` кроме `.gitkeep`).

**Итог:** spike прошёл. `core/telegram.py` можно реализовывать на Telethon bot mode для `connect`/`get_entity`/`send_message`/`edit_message`. НО для получения списка постов канала нужен альтернативный подход (не `get_messages`):

- **Вариант 1 (рекомендация для MVP): message_id в БД** — пользователь вручную указывает ID поста для редактирования, бот вызывает `edit_message(channel_id, message_id, new_text). Схема БД (channels/edit_jobs/edit_logs из PR #12) уже хранит `message_id` в `edit_logs` — подходит.
- **Вариант 2: user session** — отдельный Telethon client с user-аккаунтом (не бот), у него `get_messages` работает. Усложняет auth (phone + code).
- **Вариант 3: Bot API HTTP `/getUpdates`** — только входящие сообщения боту, не история канала.
- **Вариант 4: webhook на новые посты** — channel updates, но не даёт историю.

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `get_messages` не работает для ботов — спецификация предполагала, что сработает. Скрипт адаптирован: шаг 3 обёрнут в try/except с пояснением, шаг 4 создаёт новый пост (вместо поиска существующего).
- Ruff per-file-ignore для `scripts/*` НЕ понадобился — `T201`/`S603`/`S101` не включены в `[tool.ruff.lint.select]`. Скрипт проходит `ruff check` без additional ignores.
- Тестовые посты (id=112, id=113) НЕ удалены — оставлены для ручной проверки в канале.

## Альтернативы

- **pyrogram vs Telethon**: выбран Telethon (уже в deps из PR #2, паттерн media-gen). Альтернатива — pyrogram (другая MTProto библиотека). У pyrogram те же ограничения для ботов (`get_history` запрещён) — смена библиотеки не решит проблему `get_messages`.
- **aiogram (Bot API HTTP) vs Telethon (MTProto)**: выбран Telethon (MTProto даёт `edit_message` для каналов — Bot API HTTP тоже поддерживает `editMessageText`, но требует `chat_id` + `message_id` и не даёт `get_entity` для проверки канала). Альтернатива — aiogram, но `get_messages` через Bot API HTTP тоже не работает для истории канала (только `/getUpdates` для входящих). Telethon предпочтительнее для MVP из-за единого client API.
- **raw Bot API HTTP vs Telethon**: выбран Telethon (Pythonic API, сессия в файле, `get_entity` для валидации канала). Альтернатива — raw HTTP-запросы к `https://api.telegram.org/bot<token>/...` — больше boilerplate, нет `get_entity` (нужен отдельный `/getChat`), но проще для deploy (нет MTProto dependency). Для MVP с `edit_message` — Telethon удобнее.
- **Bot mode vs user session**: выбран bot mode (есть `TELEGRAM_BOT_TOKEN`, не требует phone+code auth). Альтернатива — user session (Telethon с phone+code) — даёт `get_messages`, но усложняет auth flow и требует user-аккаунта. Для MVP с ручным указанием `message_id` — bot mode достаточен.
- **Хранение message_id в БД vs обход истории**: выбран вариант 1 (message_id в БД) — пользователь указывает ID поста, бот редактирует. Альтернатива — обход истории (вариант 2, user session) — даёт автоматический поиск постов по pattern, но усложняет auth. Для MVP — ручной ввод ID проще и достаточен.