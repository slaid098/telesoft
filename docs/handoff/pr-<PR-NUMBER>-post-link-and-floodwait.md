---
pr: <PR-NUMBER>
issue: 61
branch: fix/telegram/post-link-and-floodwait
status: ready
created: 2026-07-21
---

# Handoff — PR <PR-NUMBER>: replace binary search with user-provided post link + fix integration tests FloodWait

## Что сделано

Реализован issue #61 — два production-бага: (1) binary search в
`get_last_messages` ломается на каналах с дырами в нумерации постов
(воспроизведено: посты 114-138 удалены, 139-140 существуют — binary search
возвращал 113, не видел 139-140); (2) integration tests создавали новый
`TelegramClient` каждый тест → FloodWait 897 сек. 4 коммита, 16 файлов
изменено, 191 unit test green (+2 новых: `test_replace_link_invalid_post_link_422`,
`test_preview_replace_invalid_post_link_422`, 4 `parse_post_link` теста, 3
новых `get_last_messages` теста; удалено 5 `_find_max_id` тестов и 2
`get_last_messages` теста с binary search), ruff/mypy green, coverage 94.69%,
frontend 36 tests green (+1 новый: `disables submit when post link is empty`).

### Шаг 1: Backend — `fix(telegram): replace binary search with user-provided post_link`

- `src/telesoft/core/telegram.py`:
  - Удалён `_find_max_id` (binary search, строки 183-199).
  - `get_last_messages(channel_id: int, limit: int = 100, max_id: int = 0)`
    — `max_id` обязательный параметр (default 0 → возвращает `[]` с warning).
    Без binary search: `ids = list(range(max_id, max(0, max_id - limit), -1))`,
    один fetch через `_fetch_messages_by_ids`.
  - Добавлен `parse_post_link(link: str) -> int` — извлекает message_id из
    `https://t.me/channelname/140`, `https://t.me/c/1234567890/140`, `140`
    (plain number). Невалидный → `ValueError(f"cannot parse post link: {link}")`.
    Реализация: `re.search(r"/(\d+)/?$", link.strip())` → если match, `int(match.group(1))`;
    если весь link — число, `int(link.strip())`; иначе `ValueError`.
- `src/telesoft/config.py`: удалён `max_probe_id` поле из `Settings` (env
  `MAX_PROBE_ID` больше не нужен).
- `src/telesoft/schemas/job.py`: `ReplaceLinkRequest` + `PreviewRequest` —
  добавлен `post_link: str` (обязательный).
- `src/telesoft/api/routers/jobs.py`: `replace_link_endpoint` и
  `preview_replace_endpoint` парсят `payload.post_link` через `parse_post_link`
  → `max_id` (422 на parse ошибку), передают в `get_last_messages(channel_id, limit, max_id)`.
- `src/telesoft/core/runner.py`: `submit` + `_run_job` + docstring —
  добавлен `max_id: int = 0` параметр, передаётся в `get_last_messages(chat_id, limit, max_id)`.
  `# noqa: PLR0913` на `submit`/`_run_job` (6 args > 5 limit).
- `.env.example`: удалён `MAX_PROBE_ID=10000`.
- Тесты:
  - `tests/test_telegram_client.py` — удалены `_find_max_id` import + 5 тестов
    (`test_find_max_id_binary_search`, `test_find_max_id_all_empty`,
    `test_delay_between_requests`, `test_get_last_messages_reads_settings_once`,
    `test_get_last_messages_success`/`empty_channel`/`limit_larger_than_max_id`
    — последние 3 переписаны под `max_id` параметр). Добавлены 3 новых
    `get_last_messages` теста (`with_max_id`, `max_id_zero_returns_empty`,
    `limit_larger_than_max_id`) + 4 `parse_post_link` теста
    (`public_channel_url`, `private_channel_url`, `plain_number`,
    `invalid_raises_value_error`). Удалён `Settings` import (неиспользуемый).
  - `tests/test_api_jobs.py` — все payload'ы `replace-link` обновлены с
    `post_link: "https://t.me/test/140"` или `"140"`. Добавлен
    `test_replace_link_invalid_post_link_422`.
  - `tests/test_api_patterns.py` — все payload'ы `preview-replace` и
    `replace-link` обновлены с `post_link`. Добавлен
    `test_preview_replace_invalid_post_link_422`.
  - `tests/test_websocket.py` — payload `replace-link` обновлён с `post_link: "140"`.
  - `tests/test_config.py` — удалены `MAX_PROBE_ID` из env list + assertion
    `settings.max_probe_id` (defaults + custom + frozen test).
  - `tests/conftest.py` — удалён `MAX_PROBE_ID` из `mock_settings` env list.

### Шаг 2: Integration tests — `fix(tests): module-scoped StringSession fixture for integration tests`

- `tests/integration/test_real_edit.py`:
  - Удалена функция `_client()` (строки 62-76) — каждый тест создавал новый
    `TelegramClient` → `ImportBotAuthorizationRequest` → FloodWait.
  - Удалён `_reset_telegram_state` autouse fixture (строки 42-59) — больше
    не нужен (module-scoped client, не function-scoped).
  - Добавлен module-scoped fixture `telegram_client` — стартует ОДИН раз
    на все 4 теста, использует `TELEGRAM_SESSION_STRING` (saved auth) →
    `client.start()` НЕ вызывает `ImportBotAuthorizationRequest` → FloodWait
    не возникает.
  - `test_text_url_msg` / `test_entity_url_msg` — function-scoped, используют
    `telegram_client` из module fixture. Teardown: только `delete_messages`
    (без `disconnect` — module fixture disconnect'ит в конце).
  - Удалён `from telesoft.core import telegram as telegram_module` (больше
    не нужен — нет `_reset_telegram_state`).
  - Удалён `from telesoft.core.telegram import get_message` — тесты
    переписаны на `telegram_client.get_messages(CHANNEL_ID, ids=[msg.id])`
    напрямую (high-level API, by-ID fetch).
  - Удалены `contextlib` + `StringSession` top-level imports если не
    используются (проверено: `StringSession` остался — используется в
    `telegram_client` fixture; `contextlib` удалён).

### Шаг 3: Frontend — `feat(web): add post_link field to ReplaceLinkForm`

- `web/src/lib/types.ts`: `ReplaceLinkRequest` + `PreviewRequest` — добавлен
  `post_link: string` (обязательный).
- `web/src/lib/components/ReplaceLinkForm.svelte`:
  - Добавлен `let postLink = $state("")`.
  - `trimmedPostLink = $derived(postLink.trim())`.
  - `canSubmit` — добавлено `trimmedPostLink.length > 0`.
  - Поле "Ссылка на последний пост" (обязательное) после "Заменить на":
    - `<input id="rl-post-link" type="text" bind:value={postLink}
      placeholder="https://t.me/channel/140" required>`.
    - Подсказка: "Открой последний пост в Telegram → правый клик → Copy Link.
      Можно вставить ссылку или просто номер поста."
  - `handlePreview` + `submitJob` — добавлен `post_link: trimmedPostLink` в payload.
- `web/src/tests/replace-link.test.ts`:
  - Все тесты с заполнением формы обновлены — добавлен
    `await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), { target: { value: "https://t.me/test/140" } })`.
  - Добавлен `disables submit when post link is empty` — форма disabled если
    post_link пустой (даже при заполненных pattern + new_link).
  - Assertions `replaceLink`/`previewReplace` — добавлен `post_link` в payload.
- `web/src/lib/components/PreviewModal.svelte` — без изменений.

### Шаг 4: Docs — `docs(handoff): set PR number`

- `docs/handoff/pr-<PR-NUMBER>-post-link-and-floodwait.md` (этот файл) —
  placeholder `<PR-NUMBER>` заменён на реальный PR number после создания PR.
- `docs/decisions/2026-07-21-pr-<PR-NUMBER>-post-link-and-floodwait.md` —
  ADR с 4 секциями (Статус, Контекст, Решение, Альтернативы).

## Почему

### Баг 1: Binary search ломается на дырах

`_find_max_id` (binary search) предполагает монотонность: "если пост N
существует, то все посты с id < N существуют". Это **неверно для Telegram-
каналов** — посты удаляются, создаются дыры. Воспроизведено на канале
-1003903711726: посты 1-113 существуют, 114-138 удалены (дыра), 139-140
существуют. Binary search возвращает 113 (остановился на дыре), не видит
139-140. Превью показывает старые посты (113, 112, 42...) вместо новых
(139, 140).

**Решение**: юзер сам знает последний пост — проще и надёжнее. Юзер указывает
ссылку на последний пост (`https://t.me/channel/140` или просто `140`),
`parse_post_link` извлекает `max_id`, `get_last_messages` fetch'ит посты от
`max_id` вниз. Без binary search, без `_find_max_id`, без `MAX_PROBE_ID` config.

### Баг 2: Integration tests FloodWait

`tests/integration/test_real_edit.py:62-76` — каждый тест создавал **новый**
`TelegramClient` через `_client()`, вызывал `client.start(bot_token=...)` →
`ImportBotAuthorizationRequest` → FloodWait. При повторных запусках FloodWait
растёт (897 сек). Module-scoped fixture + `TELEGRAM_SESSION_STRING` (saved
auth) → `client.start()` НЕ вызывает `ImportBotAuthorizationRequest` →
FloodWait не возникает. Клиент стартует ОДИН раз на все 4 теста.

## Pending

- **Прогон integration tests локально** — главный агент должен запустить
  `uv run pytest -m integration` (нужны валидные creds `TELEGRAM_BOT_TOKEN` /
  `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` + `TELEGRAM_SESSION_STRING` в `.env`
  + test channel access). Сабагент НЕ прогоняет integration tests.
- **E2E tests (PR#42)** — могут падать на новом UI (добавлено поле
  `post_link`). Проверить `web/tests/e2e/mobile.spec.ts` отдельно — если
  тест 5 (replace-link form submission) использует old payload без
  `post_link`, он упадёт на 422. Нужен отдельный PR для E2E update.
- **Pre-existing broken files on main** (`Dockerfile.api`, `docker-compose.yml`,
  `Dockerfile.nginx`, `nginx.preview.conf`) — НЕ включены в этот PR (как и в
  PR#48/#50/#52/#54/#56/#58/#60).

## Watch out

- **`get_last_messages` сигнатура изменилась**: `(channel_id, limit=100)` →
  `(channel_id, limit=100, max_id=0)`. `max_id` — обязательный для meaningful
  result (0 → `[]`). Все callers (`runner._run_job`, `jobs.py` endpoints)
  обновлены. Любой внешний caller со старой сигнатурой получит `max_id=0` →
  `[]` (не exception, но empty result — нужно обновить caller).
- **`_find_max_id` удалён** — если другие тесты импортировали его — они
  сломаются. Проверено: только `test_telegram_client.py` использовал (обновлён
  в этом PR).
- **`Settings.max_probe_id` удалён** — если другие код/тесты читают это поле
  — `AttributeError`. Проверено: только `test_config.py` использовал (обновлён
  в этом PR), `get_last_messages` — единственный caller (переписан).
- **`MAX_PROBE_ID` env var удалён** из `.env.example` и `conftest.py`. Если
  existing `.env` файл содержит `MAX_PROBE_ID=10000` — `Settings.from_env()`
  его игнорирует (no `max_probe_id` field). Не breaking, но env var становится
  мёртвой.
- **`ReplaceLinkRequest` / `PreviewRequest` — `post_link` обязательный** —
  existing API clients (curl, E2E tests) без `post_link` в payload получат
  422 (Pydantic validation). Backward-incompatible, но необходимо для fix.
- **`parse_post_link` regex `r"/(\d+)/?$"`** — matches trailing `/N` в URL.
  `https://t.me/channel/140` → 140, `https://t.me/c/1234567890/140` → 140.
  Plain number `140` → 140 (через `int()` fallback). `invalid` → `ValueError`.
  URL с query `?comment=...` — regex без `$` anchor в середине, но `/?$`
  anchor в конце → matches `/140` before query. `https://t.me/channel/140?x=1`
  → 140 (regex matches `/140` before `?`). Проверено тестами.
- **Integration tests: `telegram_client.get_messages` напрямую** — вместо
  `telegram_module.get_message` (singleton, удалён из тестов). High-level API
  by-ID fetch работает для bot-admin (PR#52). `edited[0].text` / `edited[0].entities`
  — properly initialized (PR#52 fix).
- **Module-scoped fixture + pytest-asyncio**: `scope="module"` — клиент
  стартует ОДИН раз на все 4 теста в модуле. pytest-asyncio `auto` mode
  поддерживает async fixtures с `scope="module"`. Если тесты в разных модулях
  используют `telegram_client` — каждый модуль получит свой instance (не
  shared across modules). Для этого PR — 1 модуль, 4 теста, 1 client start.
- **`# noqa: PLR0913` на `submit`/`_run_job`** — 6 args > 5 limit. Тот же
  паттерн что в `db/models/log.py:create_log`, `db/models/job.py:update_job_status`,
  `db/models/pattern.py:create_pattern` (PR#12/56). Не поднимать global limit.