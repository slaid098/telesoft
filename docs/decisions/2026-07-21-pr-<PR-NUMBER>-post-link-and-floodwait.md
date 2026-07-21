---
pr: <PR-NUMBER>
issue: 61
status: Accepted
created: 2026-07-21
---

# ADR — PR <PR-NUMBER>: replace binary search with user-provided post link + fix integration tests FloodWait

## Статус

Accepted (2026-07-21). Реализует issue #61. ADR
`docs/decisions/2026-07-20-pr-32-get-last-messages.md` (binary search max_id) —
superseded (уже был superseded в PR#52 для raw API, теперь сам алгоритм
binary search заменён на user-provided `max_id`). ADR
`docs/decisions/2026-07-21-pr-48-session-string.md` (TELEGRAM_SESSION_STRING)
— дополняется (module-scoped fixture в integration tests использует тот же
session string).

## Контекст

### Баг 1: Binary search ломается на каналах с дырами в нумерации постов

`_find_max_id` (binary search, `src/telesoft/core/telegram.py:183-199`)
использует binary search для поиска max_id. Алгоритм предполагает
монотонность: "если пост N существует, то все посты с id < N существуют".
Это **неверно для Telegram-каналов** — посты удаляются, создаются дыры.

Воспроизведено на production-канале -1003903711726 ("Test portfolio"):
- Посты 1-113 существуют
- Посты 114-138 удалены (дыра)
- Посты 139-140 существуют (опубликованы сегодня)
- Binary search возвращает 113 (остановился на дыре), не видит 139-140
- Превью показывает старые посты (113, 112, 42...) вместо новых (139, 140)

Probe trace: probes 5000/2500/1250/625/312/156/625 → все missing → hi=155;
probe 78 exists → lo=79; probe 117 missing → hi=116 (binary search "прыгает"
через дыру вверх, не зная, что выше 138 есть валидные посты); converges to
113 (last existing below hole). Linear probe confirms: id=141 missing,
id=140 EXISTS, id=139 EXISTS, id=138-114 missing, id=113 EXISTS.

### Баг 2: Integration tests падают с FloodWait 897 сек

`tests/integration/test_real_edit.py:62-76` — каждый тест создаёт **новый**
`TelegramClient` через `_client()`, вызывает `client.start(bot_token=...)` →
`ImportBotAuthorizationRequest` → FloodWait. При повторных запусках FloodWait
растёт (897 сек). Telethon forbids reusing client across asyncio event loops
→ `_reset_telegram_state` autouse fixture reset'ил singleton между тестами →
каждый тест создавал fresh client → fresh auth → FloodWait.

## Решение

### Часть 1: `post_link` вместо binary search

**4 изменения:**

1. **`src/telesoft/core/telegram.py`** — удалён `_find_max_id` (binary
   search). `get_last_messages(channel_id, limit=100, max_id=0)` принимает
   `max_id` напрямую (обязательный, 0 → `[]` с warning). Без binary search:
   `ids = list(range(max_id, max(0, max_id - limit), -1))`, один fetch через
   `_fetch_messages_by_ids`. Добавлен `parse_post_link(link: str) -> int` —
   извлекает message_id из URL (`/N` regex) или plain number (`int()` fallback),
   невалидный → `ValueError`.

2. **`src/telesoft/config.py`** — удалён `max_probe_id` поле из `Settings`
   (env `MAX_PROBE_ID` больше не нужен).

3. **`src/telesoft/schemas/job.py`** — `ReplaceLinkRequest` + `PreviewRequest`
   добавлен `post_link: str` (обязательный). `src/telesoft/api/routers/jobs.py`
   — `replace_link_endpoint` + `preview_replace_endpoint` парсят `post_link`
   через `parse_post_link` → `max_id` (422 на parse ошибку), передают в
   `get_last_messages(channel_id, limit, max_id)`. `src/telesoft/core/runner.py`
   — `submit` + `_run_job` добавлен `max_id: int = 0` параметр.

4. **Frontend** — `web/src/lib/types.ts` + `ReplaceLinkForm.svelte` —
   добавлено поле "Ссылка на последний пост" (обязательное), placeholder
   `https://t.me/channel/140`, подсказка "Открой последний пост в Telegram →
   правый клик → Copy Link. Можно вставить ссылку или просто номер поста."
   `canSubmit` — добавлено `trimmedPostLink.length > 0`.

### Часть 2: Integration tests FloodWait фикс

**3 изменения в `tests/integration/test_real_edit.py`:**

1. Удалена функция `_client()` (каждый тест создавал новый `TelegramClient`).
2. Удалён `_reset_telegram_state` autouse fixture (function-scoped reset).
3. Добавлен module-scoped fixture `telegram_client` — стартует ОДИН раз на
   все 4 теста, использует `TELEGRAM_SESSION_STRING` (saved auth) →
   `client.start()` НЕ вызывает `ImportBotAuthorizationRequest` → FloodWait
   не возникает. `test_text_url_msg` / `test_entity_url_msg` — function-scoped,
   используют `telegram_client` из module fixture. Teardown: только
   `delete_messages` (без `disconnect` — module fixture disconnect'ит в конце).

## Альтернативы

### Для бага 1 (binary search)

1. **User-provided post_link (выбрано)** — юзер указывает ссылку на последний
   пост, `parse_post_link` извлекает `max_id`. Плюс: просто, надёжно, не
   требует API calls для discovery. Минус: extra UX step (юзер должен
   открыть последний пост → Copy Link).

2. **Кеширование last_known_max_id в БД** (`channels` table поле
   `last_known_max_id`) — после первого поиска сохранить max_id, при
   следующем вызове начать с `last_known_max_id + 1` и линейно вверх до
   первого missing. Плюс: auto-discovery без user input. Минус: требует
   миграцию БД, first run всё ещё использует binary search (broken), не
   решает баг 1 для first run. Pending item из PR#32/34.

3. **Exponential probe сверху** — `MAX_PROBE_ID/2, MAX_PROBE_ID/4, ...` с
   проверкой "above any hole" через batch `channels.GetMessagesRequest(id=[...])`.
   Плюс: auto-discovery без БД changes. Минус: сложнее binary search, всё
   ещё может пропустить post выше hole если hole > probe step. Отклонено —
   ненадёжно.

4. **Webhook на новые посты** — bot подписывается на channel updates
   (`client.on(events.NewMessage(channel=...))`), сохраняет message_id в
   БД. Плюс: 100% точность, ноль probes. Минус: `receive_updates=True`
   (сейчас `False`), повышает traffic, требует persistent listener. Pending
   для будущего PR.

5. **Userbot (service account)** — `iter_messages` работает для user session.
   Плюс: reliable history iteration. Минус: усложняет auth (phone+code flow),
   требует session management. Отклонено — bot session работает для by-ID
   fetch.

6. **Linear probe от MAX_PROBE_ID вниз** — `MAX_PROBE_ID, MAX_PROBE_ID-1, ...`
   до первого существующего. Плюс: просто. Минус: expensive для каналов с
   реальным top_id много меньше MAX_PROBE_ID (N requests). Отклонено —
   неэффективно.

### Для бага 2 (FloodWait в integration tests)

1. **Module-scoped fixture + TELEGRAM_SESSION_STRING (выбрано)** — один
   client на все тесты, saved auth → no `ImportBotAuthorizationRequest` →
   no FloodWait. Плюс: просто, работает с existing `TELEGRAM_SESSION_STRING`
   env var (PR#48). Минус: тесты в одном модуле разделяют state (если один
   тест оставляет client в плохом state — следующий падает).

2. **Function-scoped fixture + TELEGRAM_SESSION_STRING** — каждый тест
   создаёт client, но с saved auth (no `ImportBotAuthorizationRequest`).
   Плюс: изоляция между тестами. Минус: N client starts (N=4), каждый start
   всё ещё делает MTProto handshake (даже без auth) → медленнее, потенциально
   FloodWait на N > 10 тестов.

3. **Session-scoped fixture** — один client на всю test session (все модули).
   Плюс: минимальное количество starts. Минус: если integration tests в
   разных модулях — они разделяют state (race conditions). Отклонено —
   module scope достаточно для 4 тестов в одном модуле.

4. **Skip integration tests в CI** (уже реализовано через `pytestmark` +
   `skipif not TELEGRAM_CREDS`) — тесты не запускаются без creds. Не решает
   FloodWait при локальном запуске с creds.

## Последствия

- **`get_last_messages` сигнатура изменилась**: `(channel_id, limit=100)` →
  `(channel_id, limit=100, max_id=0)`. Backward-incompatible — callers без
  `max_id` получают `[]` (не exception, но empty result). Все callers
  обновлены в этом PR.
- **`_find_max_id` удалён** — internal function, единственный caller был
  `get_last_messages` (переписан). Если другие модули импортировали —
  `ImportError`. Проверено: только `test_telegram_client.py` (обновлён).
- **`Settings.max_probe_id` удалён** — `AttributeError` на доступ. Проверено:
  только `test_config.py` (обновлён) + `get_last_messages` (переписан).
- **`MAX_PROBE_ID` env var** — становится мёртвой (ignored), не breaking.
  Удалён из `.env.example`.
- **`ReplaceLinkRequest` / `PreviewRequest` — `post_link` обязательный** —
  backward-incompatible API change. Existing clients без `post_link` → 422.
  E2E tests (PR#42) могут падать — нужен отдельный PR для E2E update.
- **`parse_post_link` regex `r"/(\d+)/?$"`** — matches trailing `/N` в URL.
  Plain number через `int()` fallback. Невалидный → `ValueError` → 422 в
  router. URL с query `?comment=...` — regex `/?$` anchor в конце matches
  `/N` before query.
- **Module-scoped fixture** — pytest-asyncio `auto` mode поддерживает
  `scope="module"`. Клиент стартует ОДИН раз на все 4 теста в модуле.
  Teardown: только `delete_messages` per message fixture, `disconnect` в
  module fixture teardown.
- **`telegram_client.get_messages` напрямую** в integration tests — вместо
  `telegram_module.get_message` (singleton). High-level API by-ID fetch
  работает для bot-admin (PR#52). `edited[0].text` / `edited[0].entities`
  properly initialized (PR#52 fix).
- **ADR PR#32 (binary search) superseded** — уже был superseded в PR#52 для
  raw API, теперь сам алгоритм binary search заменён. ADR PR#32 не
  обновляется (immutable record).
- **ADR PR#48 (TELEGRAM_SESSION_STRING) дополняется** — module-scoped
  fixture в integration tests использует тот же session string. ADR PR#48
  не обновляется (immutable record), этот ADR документирует применение к
  integration tests.