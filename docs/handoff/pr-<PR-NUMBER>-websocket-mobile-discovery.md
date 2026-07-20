---
pr: <PR-NUMBER>
issue: 39
branch: fix/api-web/websocket-mobile-discovery
status: ready
created: 2026-07-20
---

# Handoff — PR #<PR-NUMBER>: WebSocket support, mobile bugs, auto-discovery logging

## Что сделано

Реализован issue #39 — 6 фиксов багов, найденных при тестировании на test.slaid098.dev (мобильный viewport): WebSocket сломан (нет `websockets` lib), auto-discovery возвращает 0 постов без логов, дублирование каналов на мобиле (table не скрыта), нет явной кнопки перехода на карточке канала, 0/0 без объяснения на job detail, recent jobs table не mobile-friendly. Backend: 1 файл (`pyproject.toml` uvicorn[standard], `core/telegram.py` loguru logging). Frontend: 3 файла (`channels/+page.svelte`, `channels/[id]/+page.svelte`, `jobs/[id]/+page.svelte`). No comments. Svelte 5 runes. ruff, mypy, Biome, svelte-check (0 errors, 2 pre-existing advisory warnings), Vitest (28 тестов), pytest (115 тестов, coverage 94.27%) — все green.

### Фикс 1: WebSocket support — `pyproject.toml`

- Строка 28: `"uvicorn>=0.30"` → `"uvicorn[standard]>=0.30"`.
- `[standard]` extra включает `websockets` + `uvloop` + `httptools` библиотеки. WebSocket `/api/ws` (PR#22) начинает работать — без `[standard]` uvicorn логирует `WARNING: No supported WebSocket library detected` и WS handshake падает.
- `uv.lock` обновлён (`uv sync` подтянул `websockets`, `uvloop`, `httptools`, `websockets-client`).

### Фикс 2: Auto-discovery logging — `src/telesoft/core/telegram.py`

- `get_last_messages` (строка 168): `logger.info("get_last_messages: channel_id={}, limit={}", ...)` в начале, `logger.info("binary search: max_id={}", max_id)` после `_find_max_id`, `logger.warning("get_last_messages: no messages found (max_id=0)")` если max_id==0 (раньше молча `return []`), `logger.info("fetched {} messages", len(messages))` после range fetch.
- `_find_max_id` (строка 144): `logger.debug("binary search probe mid={}", mid)` на каждой probe (debug level — не шумит в INFO, виден при `LOG_LEVEL=DEBUG`).
- Логирование использует уже импортированный `loguru.logger` (PR#16). НЕ требует новых зависимостей. Существующие тесты не падают — они не assert'ят на логах, mock'и `mock_telethon_client` и `monkeypatch.setattr` на `_find_max_id`/`_get_channel_input` изолируют от реальной логики.

### Фикс 3: Table hidden on mobile — `web/src/routes/channels/+page.svelte:68`

- `class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block"` → `class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block"`.
- Баг PR#38: `sm:block` БЕЗ `hidden` — table видна ВСЕГДА (на mobile + desktop), cards (`sm:hidden`) видны только на mobile → каждый канал рендерится дважды на mobile. Фикс: `hidden sm:block` (скрыт <640px, виден ≥640px). Стандартный Tailwind dual-layout паттерн PR#38.

### Фикс 4: "Open" button on mobile cards — `web/src/routes/channels/+page.svelte`

- В cards section рядом с Delete добавлен `<a href="/channels/${ch.id}">Open</a>` (brand-600 bg, xs size).
- Delete + Open обернуты в `<div class="mt-3 flex justify-end gap-2">` (было `flex justify-end` без `gap-2`).
- Раньше Title карточки был ссылкой, но не очевидно что туда кликать — теперь явная кнопка "Open" как в desktop table (где Title — link). UX consistency между table и cards.

### Фикс 5: Zero-match feedback — `web/src/routes/jobs/[id]/+page.svelte`

- После прогресс-бара (после "Edited: X · Failed: Y"), перед cancel section: `{#if job.status === "done" && job.total === 0}` → amber-950 box с текстом "No posts matched the pattern. Check if the channel has posts or if your pattern is correct."
- Раньше job detail показывал "done 0/0" без объяснения — юзер не понимал: нет постов в канале? паттерн не сматчился? авто-обнаружение сломалось? Теперь явное сообщение объясняет причину (после авто-обнаружения + regex-фильтра PR#34 `find_posts_with_pattern` вернул 0 matching).
- Условие `job.total === 0` (НЕ `<= 0`) — `total` всегда ≥0 (PR#22/34, `int Field(ge=0)` в schema). `job.status === "done"` — только для завершённых успешно (НЕ `failed`/`cancelled` — у них свой UX).

### Фикс 6: Recent jobs table mobile — `web/src/routes/channels/[id]/+page.svelte:70`

- Table wrapper: `class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900"` → `class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block"` (тот же паттерн что Фикс 3).
- Добавлен cards section (`sm:hidden`) после table, до `{:else}` (когда recentJobs непустой). Card: #id (link) + status badge в header, "Progress: edited/total" + created_at. Паттерн 1-в-1 из channels list cards (PR#38).
- Раньше на mobile — горизонтальный скролл таблицы, плохой UX. Теперь карточки на <640px, таблица на ≥640px.

## Почему

При тестировании на test.slaid098.dev (мобильный viewport) найдены 6 багов разной критичности:

1. **WebSocket сломан** (критический) — real-time progress job detail page полностью нерабочий. `pyproject.toml` указывал `uvicorn>=0.30` без `[standard]` extra, который содержит `websockets` library. uvicorn при запуске логирует warning, но WS handshake падает. Это регрессия PR#22 (runner + WS endpoint) — спека указывала `uvicorn[standard]`, но при инициализации репо (PR#2) упустили `[standard]`.
2. **Auto-discovery молча возвращает 0** (высокий) — `get_last_messages` (PR#32) отрабатывает ~15 секунд (binary search 13 probes × 1s delay + range fetch), возвращает `[]`. Без логирования невозможно понять: max_id=0 (канал пуст)? access_hash=0 (нет прав)? FloodWait? Все случаи выглядят одинаково — "0 постов, причина неизвестна". Логирование позволяет дебажить prod.
3. **Дублирование каналов на мобиле** (UI, средний) — regression PR#38: `sm:block` без `hidden` на table wrapper. Desktop unaffected (видна только table, cards `sm:hidden`), но mobile видит оба блока → каждый канал дважды. Простая опечатка в Tailwind class.
4. **Нет явной кнопки "Open"** (UX, низкий) — на mobile cards Title — ссылка, но не очевидно. Desktop table имеет только Title-link (тоже не идеально, но там row кликабельнее визуально). Добавление явной кнопки "Open" рядом с Delete делает action set симметричным (view + delete).
5. **0/0 без объяснения** (UX, средний) — после авто-обнаружения + regex-фильтра (PR#34) job может завершиться с `total=0` (0 matching posts). Job detail показывал "done 0/0" без контекста → юзер думает "что-то сломалось". Явное сообщение объясняет: нет matching, проверь pattern или наличие постов.
6. **Recent jobs table не mobile** (UI, средний) — regression PR#38 (channels/[id] page не была включена в PR#38 mobile responsive fix). Table без `hidden sm:block` обёртки → горизонтальный скролл на mobile. Фикс: применить тот же dual-layout паттерн.

## Pending

- **PR#26 pending items** сохраняются: Edit channel mode (ChannelForm только create), Job retry/delete UI, WebSocket shared client (per-page сейчас), Job detail auto-refresh fallback (polling если WS не подключён), Logs pagination.
- **Кеширование max_id в БД** (PR#32 pending) — `last_known_max_id` field в `channels` table ускорит `get_last_messages` с 15 запросов до 1. Не в scope этого PR.
- **Test coverage для `channels/[id]/+page.svelte`** — Vitest не имеет тестов для channel detail page (нет `channels-detail.test.ts`). PR#38 тоже не добавлял. Добавить в follow-up.
- **E2E smoke test** — `scripts/smoke_test.py` (PR#28) не проверяет WebSocket. Добавить WS smoke step (connect, receive event, close) — follow-up.

## Watch out

- **`uv.lock` обновлён** — `uv sync --extra dev` после `pyproject.toml` change подтягивает `websockets`, `uvloop`, `httptools`. Если lock file не коммитнут — CI `uv sync --frozen` упадёт. Lock включён в коммит 1 (fix(api): add uvicorn[standard]).
- **`uvicorn[standard]` тянет `uvloop`** — на macOS/Windows это native extension, требует compilation (или wheel). На Linux (CI, Docker) — wheel доступен. Если dev на Windows без build tools — может потребоваться `pip install uvicorn[standard]` отдельно. Не блокирующее для prod (Linux Docker).
- **`hidden sm:block` vs `sm:block`** — легко перепутать. `hidden` без `sm:block` = скрыт всегда. `sm:block` без `hidden` = виден всегда (display:block на ≥640px, но и на <640px тоже block, т.к. нет `hidden`). Правильно: `hidden sm:block` = скрыт <640px, block ≥640px. PR#38 упустил `hidden` на channels table — этот PR фиксит.
- **`job.total === 0` strict equality** — НЕ `<= 0` и НЕ `== 0` (loose). `total: int` всегда ≥0 (Pydantic `Field(ge=0)`), но TS `=== 0` безопаснее `== 0` (нет type coercion). Если backend когда-нибудь вернёт `null` для total — `null === 0` false, сообщение не покажется (правильно, т.к. null = неизвестно, не 0 matching).
- **Логи `get_last_messages` на INFO level** — видны в prod по умолчанию (`LOG_LEVEL=INFO` default в Settings). 1 info в начале + 1 info после binary search + 1 info после range fetch = 3 INFO на каждый replace-link job. НЕ шумно (job сам логирует progress в БД + event bus). `binary search probe mid={}` на DEBUG — не виден в prod по умолчанию, только при `LOG_LEVEL=DEBUG` (debug channel).
- **`statusClass` функция определена локально** в `channels/[id]/+page.svelte` (дубликат из `jobs/[id]/+page.svelte`). Не в scope этого PR выносить в `$lib/utils`. Follow-up — extract в shared helper.
- **Pre-existing advisory warnings** — `state_referenced_locally` на `jobs/[id]/+page.svelte` строки 10-11 (`let job = $state(data.job)`, `let logs = $state(data.logs)`). PR#26 documented as intentional ("load once, update via events" паттерн). НЕ фиксятся в этом PR.