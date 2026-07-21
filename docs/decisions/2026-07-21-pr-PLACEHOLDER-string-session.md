---
pr: PLACEHOLDER
issue: 45
status: Accepted
created: 2026-07-21
supersedes: 2026-07-20-pr-16-telegram-client.md (session storage decision)
---

# ADR — PR PLACEHOLDER: use StringSession always instead of file session

## Статус

Accepted (2026-07-21). Пересматривает решение о session storage из ADR `docs/decisions/2026-07-20-pr-16-telegram-client.md` (Status=Accepted, file session). Старый ADR остаётся как immutable record; этот ADR документирует новое решение.

## Контекст

`src/telesoft/core/telegram.py:41` (с PR#16) использовал file session (`settings.session_path` = `app_data/bot.session`) для переиспользования MTProto handshake между restarts. ADR PR#16 явно отклонил `MemorySession` (теряется при restart) в пользу file session.

Проблема проявилась после PR#44 (integration tests): `tests/integration/test_real_edit.py:42` открывал тот же `bot.session` файл через `TelegramClient(settings.session_path, ...)`. При одновременном запуске:
- Running контейнер (`docker compose up`) держит `bot.session` open.
- Локальный `uv run pytest -m integration` пытается открыть тот же файл.

SQLite (которую Telethon использует для file session) выдаёт lock conflict — integration tests нельзя запустить локально при работающем контейнере.

Дополнительно: bot-token auth мгновенная (`client.start(bot_token=...)` — без phone+code flow, handshake тривиален). File session кэширует handshake, но для bot это не выгода — ms-операция при каждом restart, незаметная на cold start.

## Решение

**`StringSession()` (in-memory) всегда** — в `core/telegram.py` `get_client()` и в `tests/integration/test_real_edit.py` `_client()`.

```python
from telethon.sessions import StringSession

_state.client = TelegramClient(
    StringSession(),
    settings.telegram_api_id,
    settings.telegram_api_hash,
    receive_updates=False,
)
```

- Нет файла на диске → нет SQLite lock conflicts.
- Bot-token auth мгновенная → нет кэшируемого handshake.
- `Settings.session_path` и env `SESSION_PATH` сохранены для backwards compat (не ломать существующие `.env` файлы), но `telegram.py` больше не использует это поле.

## Альтернативы

1. **File session with lock (`settings.session_path`)** — текущее решение PR#16. Плюс: переиспользование handshake между restarts (но для bot это ms-операция). Минус: SQLite lock conflicts при одновременном запуске tests + container. Отклонено — lock conflicts блокируют локальный запуск integration tests.

2. **`MemorySession()`** — Telethon in-memory session, аналог `StringSession()` но без сериализации. Теряется при restart. Для bot-token auth это не проблема (auth мгновенная). `StringSession()` выбран вместо `MemorySession()` потому что: (a) `StringSession` — standard Telethon pattern для bot mode, (b) `StringSession` может быть сериализована в строку и передана через env var (будущая опция, не используется сейчас), (c) digital_factory референс использует `MemorySession` — `StringSession` чуть более гибкий без дополнительных затрат.

3. **DB session (custom `Session` subclass)** — Telethon позволяет кастомные session backends (хранить в PostgreSQL/Redis вместо SQLite). Избыточно для MVP — добавляет зависимость и сложность. Отклонено.

4. **Env var session string (`StringSession(save_this_string)`)** — `StringSession` может быть сериализована в строку и передана через env var (`TELEGRAM_SESSION_STRING`). Позволяет переиспользовать handshake между restarts без файла. Отклонено для текущего PR — bot-token auth мгновенная, не нужна. Может быть добавлено в будущем если понадобится кэширование handshake (но для bot это unlikely).

5. **Убрать `Settings.session_path` полностью** — убрать поле из `Settings` и env `SESSION_PATH` из `.env.example`. Отклонено — ломает frozen dataclass signature (tests `test_config.py` assertions) и существующие `.env` файлы. Поле сохранено для backwards compat, не используется.

## Последствия

- `app_data/bot.session` файл больше не создаётся при запуске бота.
- `uv run pytest -m integration` запускается локально без lock conflict с контейнером.
- `Settings.session_path` и env `SESSION_PATH` — deprecated, сохранены для backwards compat.
- ADR PR#16 session storage решение пересмотрено (file session → StringSession).
- Spike скрипты (`scripts/spike_telethon.py`, `scripts/spike_telethon_v2.py`) не обновлены — standalone, не production код, используют file session (создают `bot.session` при запуске, не влияют на app).