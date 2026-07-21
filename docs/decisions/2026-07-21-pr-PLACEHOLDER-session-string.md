---
pr: PLACEHOLDER
issue: 47
status: Accepted
created: 2026-07-21
supersedes: 2026-07-21-pr-46-string-session.md (session storage decision)
---

# ADR — PR PLACEHOLDER: add TELEGRAM_SESSION_STRING to prevent FloodWait on restart

## Статус

Accepted (2026-07-21). Supersedes ADR `docs/decisions/2026-07-21-pr-46-string-session.md` (Status=Accepted, in-memory `StringSession()` без saved auth). Старый ADR остаётся как immutable record; этот ADR документирует пересмотр решения.

## Контекст

PR#46 заменил file session (`app_data/bot.session`) на in-memory `StringSession()` в `core/telegram.py` и `tests/integration/test_real_edit.py`. ADR PR#46 аргументировал: (1) "bot-token auth мгновенная" — file session не даёт выгоды, (2) SQLite lock conflicts при одновременном запуске tests + container, (3) `StringSession()` in-memory — нет файла, нет conflict.

**Регрессия**: `StringSession()` без saved auth хранит только DC + server_address, НО не auth_key. При каждом `client.start(bot_token=...)` Telethon выполняет `ImportBotAuthorizationRequest` для получения auth_key. Telegram лимитирует auth запросы — после ~5-10 restarts контейнера → `FloodWaitError` с timeout ~2500s (40+ минут downtime).

Тезис PR#46 "bot-token auth мгновенная" опровергнут: auth запрос не мгновенный (network round-trip + MTProto handshake), и повторяется при каждом restart. File session кэшировал auth_key в SQLite — restarts были дешёвы. `StringSession()` без saved auth теряет это преимущество.

## Решение

**`TELEGRAM_SESSION_STRING` env var** — если задан, `StringSession(saved_string)` переиспользует auth_key между restarts. Если пустой/не задан — fallback на `StringSession()` (первый запуск, local dev без кэширования).

```python
session = (
    StringSession(settings.telegram_session_string)
    if settings.telegram_session_string
    else StringSession()
)
_state.client = TelegramClient(
    session,
    settings.telegram_api_id,
    settings.telegram_api_hash,
    receive_updates=False,
)
```

Тот же паттерн в `tests/integration/test_real_edit.py` `_client()`.

- `TELEGRAM_SESSION_STRING` — сериализованная `StringSession` (~350-400 chars base64), содержит DC + auth_key + server_address + port. Один auth → переиспользуется во всех restarts, FloodWait не происходит.
- Fallback `StringSession()` сохранён для local dev / first run (без строки в `.env` — первый auth, потом генерируется строка и кладётся в `.env`).
- `Settings.session_path` и env `SESSION_PATH` сохранены для backwards compat (PR#46, deprecated, не используется `telegram.py`).

## Альтернативы

1. **File session (`settings.session_path` = `app_data/bot.session`)** — исходное решение PR#16. Плюс: переиспользование auth_key между restarts. Минус: SQLite lock conflicts при одновременном запуске tests + container (PR#46 regression reason). Отклонено — lock conflicts блокируют локальный запуск integration tests.

2. **`StringSession()` без saved auth (PR#46 решение)** — in-memory session без auth_key. Плюс: нет файла, нет lock conflict. Минус: каждый restart = новый auth → FloodWait после ~5-10 attempts. Отклонено — регрессия подтверждена FloodWait ~2500s.

3. **`MemorySession()` (PR#46 alternative #2)** — Telethon in-memory session, аналог `StringSession()` но без сериализации. Теряется при restart. Та же проблема что `StringSession()` без saved auth — каждый restart = новый auth. Отклонено.

4. **DB session (custom `Session` subclass)** — Telethon кастомный session backend (PostgreSQL/Redis вместо SQLite). Плюс: persistent + no SQLite lock. Минус: добавляет зависимость и сложность. Избыточно для MVP. Отклонено.

5. **Вернуться к file session PR#16** — полный откат PR#46. Минус: возвращает SQLite lock conflicts. Отклонено — `TELEGRAM_SESSION_STRING` решает FloodWait без возврата к file session.

## Последствия

- `TELEGRAM_SESSION_STRING` env var — основной способ persistent auth для production (Docker контейнеры). Без него restarts приводят к FloodWait.
- Fallback `StringSession()` — для local dev / first run (не FloodWait-critical, restarts редки).
- `Settings.session_path` и env `SESSION_PATH` — deprecated, сохранены для backwards compat (PR#46, PR#16 pending).
- ADR PR#46 ("bot-token auth мгновенная") — superseded. ADR PR#16 (file session) — superseded дважды (PR#46 StringSession, PR#47 StringSession с saved auth). Оба старых ADR — immutable records, не обновляются.
- `scripts/spike_telethon*.py` — standalone spike скрипты (file session), НЕ обновлены (не production код). Если запустить — создаст `bot.session`, но не влияет на app.
- Integration tests `_client()` — тот же паттерн (saved string if set, else fallback). `_reset_telegram_state` fixture добавлен для cleanup между tests (Telethon forbids client reuse across asyncio loops).
- `.env.example` — `TELEGRAM_SESSION_STRING=` с комментарием (способ генерации строки). `SESSION_PATH=app_data/bot.session` сохранён (deprecated).