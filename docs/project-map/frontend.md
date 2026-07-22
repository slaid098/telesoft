---
module: web
purpose: SvelteKit 2 + Svelte 5 runes + TypeScript frontend (auth, channels CRUD, WebSocket client)
key_files:
  - web/package.json — scripts + deps (svelte, sveltekit, biome, vitest, knip, tailwind)
  - web/svelte.config.js — adapter-node + vitePreprocess
  - web/vite.config.ts — sveltekit plugin + proxy /api → localhost:8000
  - web/vitest.config.ts — jsdom + @testing-library/svelte + coverage v8
  - web/biome.json — linter/formatter config (noExplicitAny=error, 2-space, double quotes)
  - web/knip.json — dead code detection entry points (lib + routes + tests)
  - web/src/lib/api.ts — fetch wrapper (credentials:include, 401→goto login, ApiError) + PR#58: previewReplace/listPatterns/createPattern/deletePattern + typed replaceLink wrapper
  - web/src/lib/ws.ts — WebSocket client (auto-reconnect, heartbeat, cookie auth)
  - web/src/lib/types.ts — TS types mirroring backend Pydantic (Channel/Job/Log/WsEvent/WsEventType/WsEventPayload/ReplaceLinkRequest; PR#58: ReplaceMode, PreviewRequest/Item/Response, PatternResponse/ListResponse/CreateRequest, ReplaceLinkRequest+mode+keep_tail; PR#62: ReplaceLinkRequest+post_link, PreviewRequest+post_link; PR#64: keep_tail→full_replace в ReplaceLinkRequest + PreviewRequest)
  - web/src/lib/components/ChannelForm.svelte — add channel form (Svelte 5 runes, $state/$derived canSubmit; PR#38 touch target py-2.5)
  - web/src/lib/components/ReplaceLinkForm.svelte — replace-link form (PR#58 редизайн: 3 таба Simple/Library/Advanced via role="tablist", PR#64: radio "Полная"/"Частичная" замена вместо keep_tail checkbox, Preview+Run buttons, runSignal prop; PR#36 limit 1..1000; PR#38 touch target py-2.5; PR#62: +post_link field "Ссылка на последний пост" обязательное, placeholder `https://t.me/channel/140`, canSubmit +trimmedPostLink.length>0)
  - web/src/lib/components/PreviewModal.svelte — PR#58: modal role="dialog", before→after pairs, compiled_pattern, onRun/onEdit callbacks
  - web/src/lib/components/PatternLibrary.svelte — PR#58: modal CRUD for link_patterns (listPatterns/createPattern/deletePattern, is_builtin badge, onPatternsChanged callback)
  - web/src/routes/+layout.svelte — app shell (sticky header PR#82, top nav bar Главная/Каналы/Задачи всегда видим на всех устройствах PR#82; bottom tab bar удалён PR#82)
  - web/src/routes/+layout.ts — LayoutLoad auth guard (GET /api/auth/me, 401→redirect)
  - web/src/routes/+page.ts — root redirect → /channels
  - web/src/routes/login/+page.svelte — login form (Svelte 5 runes)
  - web/src/routes/channels/+page.svelte — channels list: dual-layout table (≥640px) + cards (<640px) PR#38, delete, Add channel button (inline ChannelForm)
  - web/src/routes/channels/+page.ts — PageLoad GET /api/channels
  - web/src/routes/channels/[id]/+page.svelte — channel detail (header, ReplaceLinkForm, run history; PR#58: PreviewModal integration, runSignal nonce trigger)
  - web/src/routes/channels/[id]/+page.ts — PageLoad GET /api/channels/{id} + recent jobs, 404→redirect
  - web/src/routes/jobs/+page.svelte — jobs list: dual-layout table (≥640px) + cards (<640px) PR#38, status filter, auto-refresh 5s, PR#84 pagination controls (номера страниц 1..N, Prev/Next, pageSize=20, `$derived` totalPages, polling уважает текущую страницу)
  - web/src/routes/jobs/+page.ts — PageLoad GET /api/jobs + channels lookup (PR#84: limit=20 offset=0 вместо limit=50)
  - web/src/routes/jobs/[id]/+page.svelte — job detail: dual-layout logs table+cards PR#38, progress bar, cancel (touch target py-2.5 PR#38), WebSocket realtime
  - web/src/routes/jobs/[id]/+page.ts — PageLoad GET /api/jobs/{id} + logs, 404→redirect
  - web/Dockerfile.web — multi-stage build → adapter-node runtime
  - web/playwright.config.ts — Playwright E2E config (PR#42): mobile project 375x812, baseURL docker-dind:8080, webServer off, workers 1
dependencies: [backend]
last_updated: 2026-07-22 (PR#84)
---

# frontend — web/

## Structure

```
web/
├── package.json          # telesoft-web: dev/build/preview/lint/format/check/typecheck/test/test:watch/knip
├── package-lock.json     # 428 пакетов
├── svelte.config.js      # adapter-node + vitePreprocess
├── vite.config.ts        # sveltekit plugin + proxy /api → localhost:8000 (ws:true)
├── vitest.config.ts      # jsdom + @testing-library/svelte/vite + coverage v8
├── tsconfig.json         # TS config (extends svelte-kit, strict: true)
├── biome.json            # recommended, noExplicitAny=error, 2-space, double quotes, semicolons, lineWidth 100
├── knip.json             # entry: src/**/*.svelte, src/routes/**/+{page,layout}.ts, src/lib/{api,ws,types}.ts
├── postcss.config.js     # tailwindcss + autoprefixer
├── tailwind.config.js    # content paths + brand color palette (50/100/500/600/700, синий)
├── Dockerfile.web        # multi-stage build → runtime (adapter-node, PORT=3000)
├── playwright.config.ts # E2E config (PR#42): testDir ./tests/e2e, timeout 30s, retries 1, workers 1 (sequential), baseURL http://docker-dind:8080 (nginx, контейнеры running, webServer отключён), project "mobile" (viewport 375x812, deviceScaleFactor 2, isMobile true, hasTouch true — iPhone SE-like)
├── .env.example          # VITE_API_BASE=http://localhost:8000
├── .gitignore            # PR#42: +test-results/, +playwright-report/, +playwright/.cache/
└── src/
    ├── app.html          # HTML shell (h-full + dark theme body bg-slate-950)
    ├── app.css           # @tailwind base/components/utilities + html,body height:100% + font-smoothing
    ├── app.d.ts          # App.Locals.user: string | null, App.PageData.user?, App.Error, App.PageStore
    ├── lib/
    │   ├── api.ts        # fetch wrapper: credentials:include, ApiError, 401→goto login, api={get,post,put,patch,del}; PR#58: previewReplace/listPatterns/createPattern/deletePattern + typed replaceLink wrapper
    │   ├── ws.ts         # WebSocketClient: auto-reconnect (1s→30s backoff), heartbeat (25s/30s), cookie auth
    │   ├── types.ts      # TS types mirroring backend Pydantic: Channel, Job, Log, WsEvent, WsEventPayload, JobStatus, ReplaceLinkRequest={pattern, new_link, post_link, limit, mode, full_replace} (PR#58: +ReplaceMode, PreviewRequest/Item/Response, PatternResponse/ListResponse/CreateRequest; PR#62: +post_link в ReplaceLinkRequest + PreviewRequest; PR#64: keep_tail→full_replace)
    │   └── components/
    │       ├── ChannelForm.svelte      # add channel form: $state telegramId/title/username, $derived canSubmit, POST /api/channels → onSaved(channel); PR#38 primary submit py-2.5 (≥44px touch target)
    │       ├── ReplaceLinkForm.svelte   # PR#58 редизайн: 3 таба (Simple/Library/Advanced) via role="tablist". Simple: input с placeholder `https://t.me/bot?start=flow-*`. Library: <select> из listPatterns() (lazy load через $effect) + кнопка "Управление паттернами". Advanced: raw regex input (без frontend-валидации). Общее: "Заменить на", PR#64: radio "Полная замена" (full_replace=true, default) / "Частичная (оставить окончание)" (full_replace=false) через fieldset+legend вместо keep_tail checkbox, Limit 1..1000, "Предпросмотр"+"Запустить". PR#62: +поле "Ссылка на последний пост" (обязательное, placeholder `https://t.me/channel/140`, подсказка "Открой последний пост в Telegram → правый клик → Copy Link. Можно вставить ссылку или просто номер поста.", canSubmit +trimmedPostLink.length>0). effectivePattern=$derived. onPreview callback, runSignal prop (nonce) для триггера submit из PreviewModal. PR#36 limit, PR#38 touch target py-2.5
    │       ├── PreviewModal.svelte      # PR#58: modal role="dialog". Props: previews, totalMatches, compiledPattern, onRun, onEdit. Список пар before→after (post #id + text), compiled_pattern мелким. Кнопки "Изменить pattern" (onEdit) | "Запустить job" (onRun)
    │       └── PatternLibrary.svelte    # PR#58: modal CRUD. Загрузка listPatterns() на mount, форма добавления (name, pattern, description) через createPattern(), удаление (!is_builtin только) через deletePattern() с window.confirm. onPatternsChanged callback → родитель перезагружает
    ├── routes/
    │   ├── +layout.svelte  # app shell PR#82: header sticky top-0 z-50 (всегда виден при скролле), top nav bar (wordmark «telesoft» кликабельный → /, horizontal nav Главная/Каналы/Задачи всегда видим на всех устройствах — `hidden sm:flex` убрано PR#82, tap targets py-2.5 PR#82, gap-2 вместо space-x-1 PR#82, «Вы вошли как» + «Выйти» справа), isActive(item) хелпер со строгим сравнением для "/" (иначе startsWith("/") всегда true); login guard {#if isLogin} сохранён; bottom tab bar (grid grid-cols-2 sm:hidden, aria-label="Мобильная навигация") удалён PR#82; Svelte 5 runes
    │   ├── +layout.ts     # LayoutLoad auth guard: GET /api/auth/me, 401→redirect(303,/login?redirectTo=...); prerender=false, ssr=false
    │   ├── +page.svelte   # (удалён в PR#24 — root redirect в +page.ts)
    │   ├── +page.ts       # root redirect(307, /channels)
    │   ├── login/
    │   │   └── +page.svelte  # login form: $state username/password/error/loading, $derived canSubmit, POST /api/auth/login
    │   ├── channels/
    │   │   ├── +page.svelte      # channels list: dual-layout PR#38 — table (hidden sm:block, title/telegram_id/active badge/delete) + cards (sm:hidden, title link + active badge + dl telegram_id/username + delete); empty state, Add channel button (toggle inline ChannelForm), row link → /channels/{id}; $derived.by merge load+localRefresh
    │   │   ├── +page.ts         # PageLoad: GET /api/channels → {channels, total}
    │   │   └── [id]/
    │   │       ├── +page.svelte  # channel detail: header (title/telegram_id/is_active badge/username), ReplaceLinkForm (PR#58: onPreview callback + runSignal prop), "Run history" table (last 5 jobs), link to /jobs; statusClass(status) helper; PR#58: PreviewModal рендерится при preview !== null, onRun → preview=null; runNonce+=1
    │   │       └── +page.ts      # PageLoad: GET /api/channels/{id} + GET /api/jobs?channel_id={id}&limit=5 → {channel, recentJobs}; 404→redirect(303,/channels)
    │   └── jobs/
    │       ├── +page.svelte      # jobs list: dual-layout PR#38 — table (hidden sm:block, id/channel title/pattern/status badge/progress edited/total/created_at) + cards (sm:hidden, #id link + status badge + dl channel/pattern truncate/progress/created); status filter dropdown, auto-refresh 5s if hasRunning ($effect+setInterval+cleanup), channelsById Map lookup; PR#84: pagination controls — `let page = $state(1)`, `const pageSize = 20`, `total = $derived.by(() => localTotal ?? data.total)` (sync с refresh), `totalPages = $derived(Math.ceil(total / pageSize))`, `goToPage(next)` → `refresh()` → `api.get('/api/jobs', { limit: pageSize, offset: (page-1)*pageSize, status? })`, `<nav aria-label="Пагинация задач">` с «‹ Пред.» | 1 2 3 ... N | «След. ›» (текущая `bg-brand-600`+`aria-current="page"`, Prev/Next disabled на границах), рендерится только при `totalPages > 1`, polling уважает текущую страницу (offset пересчитывается на каждом refresh)
    │       ├── +page.ts          # PageLoad: GET /api/jobs?limit=20&offset=0 PR#84 (было limit=50) + GET /api/channels (lookup) → {jobs, total, channels}
    │       └── [id]/
    │           ├── +page.svelte  # job detail: header (id/status badge/channel/pattern/new_link, Channel/Pattern flex-col sm:flex-row PR#38), progress bar (edited/total+percent), Cancel button (POST /api/jobs/{id}/cancel if running/pending, py-2.5 ≥44px touch target PR#38), dual-layout logs PR#38 — table (hidden sm:block, message_id/success ✓/✗/error/old_text/edited_at) + cards (sm:hidden, #message_id + ✓/✗ + dl error truncate/old_text truncate/edited_at); WebSocket realtime: onMount→new WebSocketClient()→onMessage(handleWsMessage)→connect(), onDestroy→close(); handleWsMessage filters by job_id, progress→update edited/failed/total, completed/failed/cancelled→update status+refetchLogs
    │           └── +page.ts      # PageLoad: GET /api/jobs/{id} + GET /api/jobs/{id}/logs → {job, logs}; 404→redirect(303,/jobs)
    └── tests/
        ├── setup.ts              # import @testing-library/svelte; afterEach(vi.restoreAllMocks)
        ├── LayoutHarness.svelte  # обёртка для +layout.svelte в тестах (передаёт data, рендерит child slot)
        ├── login.test.ts         # 3 теста: form render, submit+redirect, 401 error
        ├── channels.test.ts      # 9 тестов: 3 rows/empty/delete + 3 Add button (open/submit+refresh/cancel) + 3 ChannelForm (disabled/enabled/onSaved)
        ├── replace-link.test.ts  # PR#58: 8 тестов (rewrite под 3-mode UI): disable submit when empty/new-link empty, enable submit when simple fields filled, limit validation, default limit 100, submit с mode/full_replace PR#64, full_replace=false when partial radio selected PR#64, defaults to full_replace=true PR#64, Advanced mode switch. Mock replaceLink (НЕ api.post напрямую). PR#36: было 6 тестов (disabled/invalid-regex/limit/default/submit)
        ├── jobs.test.ts          # 5 тестов: render header/status/progress/logs, cancel POST, WS progress updates, WS completed refetches logs, WS ignores other job_ids
        ├── layout.test.ts        # 3 теста: Channels nav, Logout button, username display
        ├── api.test.ts           # 2 теста: query serialization, ApiError on non-ok
        └── e2e/                  # PR#42 — Playwright E2E tests (см. tests.md)
            ├── helpers.ts        # login(page), getSessionCookie(page), BASE_URL, TEST_CHANNEL_ID=2, TEST_USERNAME/TEST_PASSWORD
            └── mobile.spec.ts    # 7 тестов: login, channels no duplicates, open button, replace-link form, job progress, zero-match, websocket
```

## Patterns

- **SvelteKit 2 + Svelte 5 runes** — `$props()`, `$state()`, `$derived()`/`$derived.by()`, `{@render children()}`, `onclick={handler}` (НЕ Svelte 4 `export let`/`$:`/`on:click`)
- **adapter-node** для SSR в Docker (PORT=3000), но `ssr=false` для всего app — pure CSR MVP
- **Vite proxy** `/api` → backend (localhost:8000) для dev
- **Biome** вместо ESLint+Prettier (единый linter/formatter, recommended + noExplicitAny=error)
- **Knip** для dead code detection — entry patterns покрывают все lib + routes + tests
- **Vitest + @testing-library/svelte** для unit-тестов (jsdom), mocking через `vi.hoisted` + `vi.mock`
- **TailwindCSS** через PostCSS, dark theme (`bg-slate-950`/`bg-slate-900`/`brand-600`)
- **credentials: "include"** в api.ts — session cookie отправляется автоматически (signed cookie через Starlette SessionMiddleware, PR#18)
- **Auth guard в layout load** — `GET /api/auth/me` на каждом маршруте (кроме PUBLIC_PATHS), 401 → `redirect(303, /login?redirectTo=...)`. Дополнительно api.ts `request()` на 401 → `goto(/login?redirectTo=...)` для fetch после load
- **WebSocket cookie auth** — browser автоматически шлёт session cookie при WS handshake (same-origin), сервер читает `websocket.scope["session"]` (PR#22 `ws_current_user`)
- **API wrapper** — `api = { get, post, put, patch, del }` с `ApiError` class (status + detail), `buildUrl` для query params (пропускает undefined/null)
- **TS types mirroring backend Pydantic** — `Channel`/`Job`/`Log`/`WsEvent`/`JobStatus`/`ReplaceLinkRequest` (PR#20/22/36). `ReplaceLinkRequest={pattern, new_link, post_link, limit, mode, full_replace}` (PR#64 — `keep_tail`→`full_replace`, mirrors backend `src/telesoft/schemas/job.py` PR#64; PR#62 — `post_link` добавлен, mirrors backend `src/telesoft/schemas/job.py` PR#62; PR#34 — `post_urls` убран, mirrors backend PR#34). `JobStatus="done"` (не "completed"), `WsEvent` flat structure (не `{type, data}`), `MeResponse={user: string}` (не `{username}`)
- **`$derived.by` для merge load+localRefresh** — паттерн из media-gen для избежания `state_referenced_locally` warning (Svelte 5 advice)
- **Layout + login в одном коммите** — `page.url.pathname === "/login"` требует существования `/login` маршрута (SvelteKit типобезопасное сравнение, иначе ts error)
- **Svelte 5 runes в forms** (PR#26) — `$state` для form fields, `$derived` для `canSubmit`/`parsedUrls`/`trimmedPattern`/`progressPct`, `$effect` для side-effects (regex validation обновляет `patternError`, auto-refresh `setInterval` с cleanup). `bind:value` для двусторонней связи. НЕ Svelte 4 `export let`/`$:`/`on:click`.
- **WebSocket realtime в job detail** (PR#26) — `onMount` → `new WebSocketClient()` → `onMessage(handleWsMessage)` → `connect()`, `onDestroy` → `close()`. Per-page client (не shared в layout) — упрощает lifecycle и тестирование. `handleWsMessage` фильтрует по `job_id`, `progress` event → update `job.edited`/`job.failed`/`job.total`, terminal events (`completed`/`failed`/`cancelled`) → update `job.status` + `refetchLogs()`. `WsEventPayload` тип для `msg.data` (wire format `{type, data: {...}}`).
- **Regex validation client-side** (PR#26, сохранён в PR#36) — `ReplaceLinkForm`: `$effect` → `try { new RegExp(trimmedPattern) } catch (err) { patternError = err.message }`. Без external libs (regex-utils/regexpp). Submit блокируется если `patternError !== null`. Server-side `validate_pattern` (PR#22) — security, client-side — UX (fail-fast).
- **Limit validation 1..1000** (PR#36) — `ReplaceLinkForm`: `let limit = $state(100)` (default mirrors backend `Field(default=100, ge=1, le=1000)`), `const limitValid = $derived(Number.isFinite(limit) && limit >= 1 && limit <= 1000)`. `<input type="number" min="1" max="1000" step="1" bind:value={limit}>` — `bind:value` на number input возвращает number (PR#26 gotcha — `String()` cast НЕ нужен т.к. limit используется как number). `canSubmit` учитывает `limitValid`. PR#62: `canSubmit` также учитывает `trimmedPostLink.length > 0` (post_link обязательный). `handleSubmit` error branch: `patternError` → `!limitValid` ("Limit must be between 1 and 1000") → `!trimmedPostLink` ("Fill all required fields") → generic. Client-side валидация зеркалит backend `Field(ge=1, le=1000)` — UX fail-fast + security (не доверяем клиенту). Submit → `POST /api/channels/{id}/replace-link` с body `{pattern, new_link, post_link, limit}` (НЕ post_urls) → `goto("/jobs/{job_id}")`.
- **textarea URLs убран** (PR#36) — `postUrls` state, `parsedUrls` derived (`split("\n").map(trim).filter(non-empty)`), helper text "Parsed: N URL(s)" удалены. Backend PR#34 auto-discovery через `get_last_messages` (PR#32) заменил ручной сбор URLs — UX-блокер PR#14/PR#22/PR#26 снят (20 каналов × 100 постов = 2000 ручных URL-сборов → 20 запросов с limit).
- **Auto-refresh polling** (PR#26, jobs list) — `$effect` проверяет `hasRunning`, запускает `setInterval(refresh, 5000)` если true, cleanup в return функции (`clearInterval`). Когда jobs завершаются → effect re-runs → cleanup previous interval. Job detail — WS-only (без polling fallback для MVP).
- **Nav active state** (PR#26, обновлено PR#74) — `isActive(item)` хелпер: для `/` (Главная) строгое `pathname === "/"` (иначе `startsWith("/")` всегда true), для остальных `pathname.startsWith(item.href)`. `navItems` array: Главная + Каналы + Задачи (PR#74 добавил «Главная»). Используется и в desktop top nav, и в mobile bottom nav.
- **`$state` captures initial props** (PR#26) — `let job = $state(data.job)` захватывает initial value из load, не реагирует на изменения `data.job` (intentional для "load once, update via events"). Svelte 5 advice warning `state_referenced_locally` — advisory, не error. Соответствует паттерну media-gen.
- **`goto("/jobs/{job_id}")` после replace-link submit** (PR#26) — redirect на job detail page для realtime прогресса через WS. Альтернатива — inline progress на channel detail (дублирует логику job detail page).
- **`statusClass(status)` helper** (PR#26) — Tailwind классы для status badge: running=brand-600, done=emerald-700, failed=red-700, cancelled=amber-600. Используется в channel detail run history и jobs list/detail.
- **Responsive dual-layout table↔card** (PR#38) — паттерн `hidden sm:block` для table wrapper + `sm:hidden` для cards section. Оба блока в DOM, CSS media query (`sm:` = 640px) скрывает один на основе viewport width. Desktop (≥640px) — таблица, mobile (<640px) — карточки. Применён на 3 страницах: channels list, jobs list, job detail logs. Стандартный Tailwind pattern для table↔card dual layout. Минус: оба блока в DOM → в jsdom оба видимы → тесты используют `getAllByText`/`getAllByRole` (см. tests.md). Альтернативы (CSS Grid reflow, отдельный mobile компонент, container queries) отклонены — см. ADR PR#38.
- **Bottom nav `grid-cols-3`** (PR#38 → PR#74 → **удалён PR#82**) — mobile bottom nav в `+layout.svelte` был `grid grid-cols-3` (PR#74: было `grid-cols-2` для 2 пунктов, стало 3 пункта Главная/Каналы/Задачи). Иконки `text-xl`, лейблы `text-xs`, `py-3` (≥44px touch target). **PR#82 удалил bottom tab bar полностью** — заменён единым sticky top nav на всех устройствах (см. паттерн "Sticky header + unified top nav" ниже). Sidebar удалён в PR#74 — заменён верхним навбаром в `<header>` (wordmark + horizontal nav на desktop sm+).
- **Touch targets ≥44px на primary кнопках** (PR#38) — primary submit кнопки `py-2` → `py-2.5` (~44px height): ChannelForm Save, ReplaceLinkForm "Run replace-link", job detail "Cancel job". Apple HIG / Material минимум 44px. Secondary кнопки (Delete, Add channel, Cancel в ChannelForm, Back to jobs) — БЕЗ изменений (≥36px ок для secondary actions). `py-2.5` = 10px+10px padding + ~20px text = ~40px, с border/line-height ~44px.
- **Job detail header `flex-col sm:flex-row`** (PR#38) — "Channel: #X · Pattern: Y" разбит на два `<span>` (был один text блок с `·` разделителем). `flex-col space-y-1 sm:flex-row sm:space-y-0 sm:gap-3` — mobile в столбец, desktop в строку через gap. `·` разделитель убран.
- **Playwright E2E** (PR#42) — `web/playwright.config.ts` в корне `web/` (НЕ в `src/`), `testDir: ./tests/e2e`. Mobile project (375x812, iPhone SE-like). `baseURL: http://docker-dind:8080` (nginx, контейнеры running, webServer отключён). `workers: 1`, `fullyParallel: false` (sequential — общий running backend). `@playwright/test` в devDependencies. Scripts `test:e2e`/`test:e2e:mobile`. `.gitignore`: `test-results/`, `playwright-report/`, `playwright/.cache/`. Подробности — см. [tests.md](tests.md) E2E секция.
- **Three replace modes + Preview UI** (PR#58) — `ReplaceLinkForm` редизайн: 3 таба (Simple/Library/Advanced) через `role="tablist"`. **Dumb frontend** — НЕ делает конвертацию `*`→regex, экранирование, валидацию regex, логику full_replace (всё в backend PR#56/PR#64). Frontend только отображает и дёргает endpoints. `effectivePattern = $derived` для library mode (берёт `selectedPattern.pattern`) vs simple/advanced (берёт `trimmedPattern`). `onPreview` callback передаёт `PreviewResponse` родителю. `runSignal: { nonce: number }` prop + `$effect` в форме — триггер `submitJob()` из PreviewModal (Svelte 5 не expose методы, декларативный паттерн). Lazy load patterns через `$effect` с guard `patterns === null` (только при первом переключении на Library tab). `onPatternsChanged` callback сбрасывает `patterns = null` → перезагрузка. Biome import order: component import ДО type import в Svelte `<script>`. **PR#64**: radio "Полная замена" / "Частичная (оставить окончание)" через `<fieldset>`+`<legend>` (вместо `keep_tail` checkbox). `let fullReplace = $state(true)` (default = Полная замена). Radio `name="rl-replace-mode"`, `checked={fullReplace === true/false}`, `onclick={() => (fullReplace = true/false)}`. При `full_replace=false` — подсказка про `*` wildcard для указания где обрезать. Body в handlePreview/submitJob: `full_replace: fullReplace` (вместо `keep_tail: keepTail`)
- **PreviewModal onRun ordering** (PR#58) — `preview = null` BEFORE `runNonce += 1` (сначала закрываем модалку, потом триггерим submit). Если наоборот — `$effect` в форме может не сработать (race с unmount).
- **Backend-only regex validation** (PR#58) — старый UI делал `new RegExp()` в `$effect` (live error). Новый UI убрал — backend возвращает 422, frontend показывает в error-блоке после submit/preview. Соответствует "dumb frontend" спеке. Минус: пользователь видит ошибку позже (после submit, не live).
- **Sticky header + unified top nav** (PR#82) — `<header>` получил `sticky top-0 z-50` (приклеен к верху viewport'а, двигается при скролле, всегда виден). `sticky` (не `fixed`) — header остаётся в normal flow, отдельный `padding-top` для контента не нужен. Top nav (`<nav>`) всегда видим на всех устройствах: `hidden sm:flex` убрано → `flex items-center gap-2` (раньше nav скрывался на мобиле, был только bottom tab bar). Tap targets `py-2` → `py-2.5` (WCAG 2.5.5, ≥44px). `space-x-1` → `gap-2` (flex+gap единообразно с остальной шапкой). Bottom tab bar (`grid grid-cols-2 sm:hidden`, `aria-label="Мобильная навигация"`) удалён полностью — одна разметка навигации для всех устройств вместо двух (desktop top nav + mobile bottom tab bar). `isActive(item)` хелпер теперь используется только в top nav. Мотивация: на длинных списках (100 задач) bottom tab bar уезжал вниз со скроллом → переключение требовало скролла в самый низ. Sticky header решает — навигация доступна мгновенно из любого места. Контент `<main>` (`overflow-y-auto` + `flex-1` в flex-column) корректно скроллится под sticky header.
- **Jobs list pagination** (PR#84, `routes/jobs/+page.svelte`) — `let page = $state(1)`, `const pageSize = 20`. `total = $derived.by(() => localTotal ?? data.total)` — sync с `refresh()` (после refresh `localTotal = resp.total` → `total` re-derives → `totalPages` re-derives → controls перерисовываются). `totalPages = $derived(Math.ceil(total / pageSize))`. `goToPage(next)` guard: `if (next < 1 || next > totalPages || next === page) return` → `page = next` → `refresh()`. `refresh()` пересчитывает `offset = (page - 1) * pageSize` на каждом вызове → polling (5s при running) уважает текущую страницу. Controls внизу: `<nav aria-label="Пагинация задач">` с «‹ Пред.» | 1 2 3 ... N | «След. ›». Текущая страница — `bg-brand-600` + `aria-current="page"`, остальные `bg-slate-800`. Prev/Next disabled на границах (`disabled={page <= 1}` / `disabled={page >= totalPages}`) + `disabled:cursor-not-allowed`. Pagination рендерится только при `totalPages > 1` (избегает визуального шума для маленьких списков). `+page.ts` initial load: `{ limit: 20, offset: 0 }` (соответствует pageSize=20). Status-filter client-side на текущей странице, server-side при смене страницы (TODO: синхронизировать statusFilter change с refresh — для 2 фильтров и pageSize=20 приемлемо)