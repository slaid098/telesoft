# ADR — PR #<PR-NUMBER>: WebSocket support, mobile bugs, auto-discovery logging

## Статус

Accepted (2026-07-20) — 6 фиксов багов, найденных при тестировании на test.slaid098.dev (мобильный viewport). WebSocket support: `uvicorn>=0.30` → `uvicorn[standard]>=0.30` (добавляет `websockets` + `uvloop` + `httptools`). Auto-discovery logging: loguru `logger.info`/`logger.warning`/`logger.debug` в `get_last_messages` и `_find_max_id` (раньше молча `return []`). Mobile: `hidden sm:block` на 2 table wrappers (channels list, recent jobs), "Open" button на channel cards, zero-match feedback на job detail. ruff, mypy, Biome, svelte-check (0 errors), Vitest (28), pytest (115, coverage 94.27%) — все green. No comments. Svelte 5 runes.

## Контекст

При тестировании на test.slaid098.dev (мобильный viewport) найдены 6 багов разной критичности:

1. **WebSocket сломан** (критический) — `pyproject.toml:28` имеет `uvicorn>=0.30` без `[standard]` extra. Нет `websockets` библиотеки. `/api/ws` endpoint (PR#22) не работает — real-time progress job detail page полностью сломан. uvicorn при запуске логирует `WARNING: No supported WebSocket library detected. Please use "pip install 'uvicorn[standard]'"`, но WS handshake падает. Регрессия PR#22 — спека указывала `uvicorn[standard]`, но при инициализации репо (PR#2) упустили `[standard]`.

2. **Auto-discovery возвращает 0 постов молча** (высокий) — `core/telegram.py` `get_last_messages` (PR#32) отрабатывает ~15 секунд (binary search 13 probes × 1s delay + range fetch), возвращает `[]`. Без логирования невозможно понять причину: `max_id=0` (канал пуст)? `access_hash=0` (нет прав)? `FloodWait`? Все случаи выглядят одинаково — "0 постов, причина неизвестна". Логирование позволяет дебажить prod.

3. **Дублирование каналов на мобиле** (UI regression PR#38) — `channels/+page.svelte:68` имеет `sm:block` БЕЗ `hidden` на table wrapper. Table видна ВСЕГДА (на mobile + desktop), cards section (`sm:hidden`) видна только на mobile → каждый канал рендерится дважды на mobile viewport. Простая опечатка в Tailwind class.

4. **Нет кнопки "Open" на карточке канала** (UX) — `channels/+page.svelte` cards section имеет только Delete button. Title карточки — ссылка, но не очевидно что туда кликать. Desktop table имеет только Title-link (тоже не идеально, но там row визуально кликабельнее). Добавление явной кнопки "Open" делает action set симметричным (view + delete).

5. **0/0 без объяснения** (UX) — `jobs/[id]/+page.svelte` показывает "done 0/0" без контекста. После авто-обнаружения + regex-фильтра (PR#34 `find_posts_with_pattern`) job может завершиться с `total=0` (0 matching posts). Юзер не понимает: нет постов в канале? паттерн не сматчился? авто-обнаружение сломалось?

6. **Recent jobs table не mobile** (UI regression PR#38) — `channels/[id]/+page.svelte:70` — table без `hidden sm:block` обёртки (channel detail page не была включена в PR#38 mobile responsive fix). На mobile — горизонтальный скролл, плохой UX.

## Решение

6 фиксов по спеке issue #39:

1. **WebSocket support** (`pyproject.toml`) — `"uvicorn>=0.30"` → `"uvicorn[standard]>=0.30"`. `[standard]` extra включает `websockets` (WS protocol implementation), `uvloop` (async event loop, faster than default asyncio), `httptools` (HTTP parser). `uv.lock` обновлён (`uv sync --extra dev` подтянул 6 новых пакетов). uvicorn теперь поддерживает WS handshake — `/api/ws` endpoint начинает работать.

2. **Auto-discovery logging** (`src/telesoft/core/telegram.py`) — loguru логи на 3 уровнях:
   - `logger.info("get_last_messages: channel_id={}, limit={}")` в начале функции — виден в prod (INFO default).
   - `logger.info("binary search: max_id={}")` после `_find_max_id` — виден в prod.
   - `logger.warning("get_last_messages: no messages found (max_id=0)")` если `max_id == 0` — виден в prod, alert level.
   - `logger.info("fetched {} messages")` после range fetch — виден в prod.
   - `logger.debug("binary search probe mid={}")` на каждой probe в `_find_max_id` — НЕ виден в prod по умолчанию, только при `LOG_LEVEL=DEBUG`.
   Использует уже импортированный `loguru.logger` (PR#16). Существующие тесты не падают — они mock'ируют `_find_max_id`/`_get_channel_input`/`mock_telethon_client` и не assert'ят на логах.

3. **Table hidden on mobile** (`web/src/routes/channels/+page.svelte:68`) — `sm:block` → `hidden sm:block`. Table скрыта <640px, видна ≥640px. Cards section (`sm:hidden`) видна <640px, скрыта ≥640px. Стандартный Tailwind dual-layout pattern PR#38. Desktop unaffected.

4. **"Open" button on mobile cards** (`web/src/routes/channels/+page.svelte`) — рядом с Delete добавлен `<a href="/channels/${ch.id}">Open</a>` (brand-600 bg). Delete + Open обернуты в `<div class="mt-3 flex justify-end gap-2">` (было `flex justify-end` без `gap-2`). Явная кнопка перехода вместо неочевидного Title-link.

5. **Zero-match feedback** (`web/src/routes/jobs/[id]/+page.svelte`) — после прогресс-бара, перед cancel section: `{#if job.status === "done" && job.total === 0}` → amber-950 box с текстом "No posts matched the pattern. Check if the channel has posts or if your pattern is correct." Условие `job.status === "done"` (только успешно завершённые, НЕ `failed`/`cancelled` — у них свой UX) и `job.total === 0` (strict equality, `total` всегда ≥0 от Pydantic `Field(ge=0)`).

6. **Recent jobs table mobile** (`web/src/routes/channels/[id]/+page.svelte:70`) — table wrapper: `overflow-x-auto rounded-lg border border-slate-800 bg-slate-900` → `hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block`. Добавлен cards section (`sm:hidden`) после table, до `{:else}`. Card: #id (link) + status badge в header, "Progress: edited/total" + created_at. Паттерн 1-в-1 из channels list cards (PR#38).

## Альтернативы

### WebSocket support
- **`uvicorn[standard]` (выбрано)** — добавляет `websockets` + `uvloop` + `httptools`. Официальный recommended uvicorn install. 1 строка в `pyproject.toml`. CI/Docker/Linux — wheel доступен, нативные extensions компилируются. Самый простой и standard fix.
- **`wsproto` вместо `websockets`** — альтернативный WS protocol implementation (`uvicorn[wsproto]` extra). Менее популярный, меньше community support, но pure-Python (нет native compilation). Выбрано `websockets` — дефолт uvicorn, больше тестов в community.
- **SvelteKit hooks proxy** — реализовать WS через SvelteKit `hooks.server.ts` (Node.js `ws` library) вместо FastAPI uvicorn. Перенос WS logic из backend (PR#22) в frontend. Усложняет архитектуру (auth в SvelteKit vs FastAPI session), дублирование logic. Отклонено — backend WS уже работает в PR#22, нужен только uvicorn extra.
- **Оставить как есть** — игнорировать warning, надеяться что кто-то догадается `pip install websockets`. Отклонено — real-time progress полностью сломан, критический UX bug.

### Auto-discovery logging
- **loguru logging (выбрано)** — 3 INFO + 1 WARNING + 1 DEBUG лог в `get_last_messages`/`_find_max_id`. Использует уже импортированный `loguru.logger`. Виден в prod (INFO default), DEBUG для deep dive. Не требует новых зависимостей, не падает тесты. Стандартный Python logging pattern.
- **Structured logging (structlog)** — JSON-формatted logs с контекстом (channel_id, max_id, duration). Лучше для log aggregation (ELK, Datadog), но требует новую dependency (`structlog`). Отклонено для MVP — loguru достаточно, structured logging можно добавить в follow-up если понадобится.
- **Metrics (prometheus client)** — экспортировать `telesoft_discovery_total_messages` counter, `telesoft_discovery_duration_seconds` histogram. Лучше для monitoring/alerting, но требует `prometheus-client` dependency + `/metrics` endpoint + scraping setup. Отклонено — overkill для MVP, логи достаточно для дебага.
- **Оставить как есть** — молча `return []` при max_id=0. Отклонено — невозможно дебажить prod, 0 постов без причины = "магия".

### Mobile dual-layout (Фикс 3, 6)
- **`hidden sm:block` + `sm:hidden` (выбрано)** — Tailwind responsive pattern из PR#38. Оба блока в DOM, CSS media query скрывает один. Стандартный Tailwind pattern, работает без JS. Выбрано — консистентно с PR#38.
- **CSS Grid reflow** — single `<div>` с `display: grid`, reflow в зависимости от viewport через `grid-template-columns`. Ломает `<table>` semantic (нельзя использовать `<thead>`/`<tbody>`). Отклонено — потеря semantic HTML.
- **Отдельный mobile компонент** — `<ChannelsTableMobile />` vs `<ChannelsTableDesktop />`, условный рендеринг через `{#if isMobile}`. Дублирование logic, нужен viewport detection (resize listener). Отклонено — дублирование, dual-layout проще.
- **Container queries (`@container`)** — Tailwind v4 `@container` для container-based responsive (вместо viewport). Более precise (component-based), но Tailwind v4 `@container` ещё не stable. Отклонено — подождать stable Tailwind v4.

### "Open" button on cards (Фикс 4)
- **Явная кнопка "Open" (выбрано)** — `<a href="/channels/${ch.id}">Open</a>` рядом с Delete. Очевидное action, симметричное с Delete. Brand-600 bg для primary action. Выбрано — UX clarity.
- **Title-link only (как было)** — Title карточки уже ссылка, не добавлять отдельную кнопку. Меньше clutter, но не очевидно для юзера что Title кликабелен. Отклонено — UX testing показал путаницу.
- **Card click (whole card clickable)** — `onclick={() => goto("/channels/${ch.id}")}` на card wrapper. Весь card кликабелен, но конфликтует с Delete button (click на Delete = delete, не navigate). Отклонено — event conflict.
- **Иконка вместо текста** — `<a>→</a>` или `<a>👁</a>` вместо "Open". Меньше места, но иконка менее obvious чем текст. Отклонено — text яснее.

### Zero-match feedback (Фикс 5)
- **Inline message на job detail (выбрано)** — `{#if job.status === "done" && job.total === 0}` amber box с explanation. Visible только когда 0 matching, не загромождает normal jobs. Выбрано — minimal, contextual.
- **Toast notification** — всплывающее notification после job completion. Transient (исчезает через N секунд), но юзер может пропустить. Отклонено — persistent message лучше для debugging.
- **Error status в БД** — добавить `error: str | null` column в `edit_jobs`, persist "no matching posts" как error. Backend change + migration. Отклонено — `total=0` уже хранится, нет нужды в отдельной error column (PR#22 documented "edit_jobs НЕ имеет error column" by design).
- **Оставить 0/0** — юзер сам догадается. Отклонено — UX testing показал путаницу.

## Ключевые отклонения от спеки

Спека issue #39 указывала точные строки и class changes — реализация 1-в-1 по спеке. Незначительные отклонения:

- **`uvicorn[standard]` тянет `uvloop` + `httptools`** — спека упоминала только `websockets`, но `[standard]` extra включает 3 библиотеки (websockets, uvloop, httptools). Все полезны (uvloop = faster event loop, httptools = faster HTTP parser), не отклонение а дополнение.
- **`uv.lock` обновлён** — спека не упоминала lock file, но `uv sync --frozen` в CI требует актуальный lock. Lock включён в коммит 1 (fix(api): add uvicorn[standard]).
- **`logger.debug` в `_find_max_id` на каждой probe** — спека указывала "optional, debug level". Реализовано как `logger.debug` (НЕ info) — не шумит в prod по умолчанию, виден только при `LOG_LEVEL=DEBUG`. 13 probes × 1 debug log = 13 строк на job в DEBUG mode — приемлемо.
- **`job.total === 0` strict equality** — спека не уточняла, использован `===` (не `==`). TS best practice, `total` всегда number (не null), `=== 0` безопаснее (нет type coercion).
- **"Open" button brand-600** — спека указывала `bg-brand-600`, реализовано как указано. Consistent с primary action colors (Save, Run replace-link).

## Pending / Follow-up

- **Кеширование max_id в БД** (PR#32 pending) — `last_known_max_id` field в `channels` table ускорит `get_last_messages` с 15 запросов до 1. Не в scope.
- **Test coverage для `channels/[id]/+page.svelte`** — Vitest не имеет тестов для channel detail page. Добавить в follow-up.
- **Structured logging** — если понадобится log aggregation, мигрировать на `structlog` (JSON logs).
- **WebSocket E2E smoke test** — `scripts/smoke_test.py` (PR#28) не проверяет WS. Добавить WS step — follow-up.
- **PR#26 pending items** сохраняются: Edit channel mode, Job retry/delete UI, WebSocket shared client, Job detail auto-refresh fallback (polling), Logs pagination.