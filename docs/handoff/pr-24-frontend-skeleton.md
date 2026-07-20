---
pr: 24
issue: 23
branch: feat/web/sveltekit-skeleton
status: ready
created: 2026-07-20
---

# Handoff — PR #24: SvelteKit skeleton with auth, layout, and api client

## Что сделано

Реализован issue #23 — SvelteKit frontend MVP с Svelte 5 runes, TypeScript, TailwindCSS, Biome, Vitest. Структура: `lib/{api,ws,types}.ts` (fetch wrapper с credentials:include + 401 redirect, WebSocket client с auto-reconnect+heartbeat, TS types mirroring backend Pydantic), `+layout.{svelte,ts}` (app shell с навигацией + auth guard через `GET /api/auth/me`), `login/+page.svelte` (форма логина), `+page.ts` (root redirect на /channels), `channels/+page.{svelte,ts}` (список каналов + delete). 11 тестов (login, channels, layout, api) — все зелёные. Референс: `/root/workspace/media-gen/web/` — паттерны скопированы 1-в-1 (api.ts, ws.ts, layout, login).

### Шаг 1: Базовая конфигурация

- `web/src/app.html` — стандартный SvelteKit shell с `h-full` + dark theme body (`bg-slate-950 text-slate-100`).
- `web/src/app.css` — `@tailwind base/components/utilities;` + `html, body { height: 100% }` + font-smoothing.
- `web/src/app.d.ts` — `App.Locals { user: string | null }`, `App.Error { message: string; code?: string }`, `App.PageData { user?: string | null }`, `App.PageStore` (type-only import `Page` from `@sveltejs/kit`).
- `web/tailwind.config.js` — content paths `./src/**/*.{html,js,svelte,ts}`, `brand` color palette (50/100/500/600/700, синий).
- `web/knip.json` — `entry: [src/**/*.svelte, src/routes/**/+page.ts, src/routes/**/+layout.ts, src/lib/{api,ws,types}.ts]` (extended с PR#2 skeleton, теперь все lib файлы как entry — knip не выдаёт "Configuration hints").

### Шаг 2: API client (`web/src/lib/api.ts`)

- `API_BASE` = `import.meta.env.VITE_API_BASE ?? window.location.origin ?? "http://localhost:8000"` (SSR-safe через `typeof window !== "undefined"`).
- `class ApiError extends Error { status: number; detail: unknown }` — кастомная ошибка с HTTP статусом и payload от сервера.
- Internal `request<T>(path, { method, body, query, headers })`:
  - `credentials: "include"` — session cookie отправляется автоматически.
  - JSON `Accept` + `Content-Type` (если body есть) headers.
  - На 401 в browser → `goto("/login?redirectTo=...")` + throw `ApiError(401)`. НЕ редиректит если уже на `/login`.
  - Парсит JSON response, на non-ok → `ApiError(status, parsed, message)` (message из `detail` или `statusText`).
- Export `api = { get, post, put, patch, del }` — все методы используют `request<T>`.
- `buildUrl(path, query)` — URLSearchParams сериализация, пропускает `undefined`/`null` значения.
- Копия media-gen `web/src/lib/api.ts` 1-в-1 (адаптирован только тип `MeResponse` — `user: string` вместо `{ username: string }`).

### Шаг 3: TS types (`web/src/lib/types.ts`)

- `Channel = { id, telegram_id, title, username: string | null, is_active, added_at }` — mirrors `ChannelResponse` (PR#20).
- `ChannelCreate = { telegram_id, title, username? }`, `ChannelUpdate = { title?, username?, is_active? }` — mirrors Pydantic schemas.
- `ChannelListResponse = { channels: Channel[], total: number }` — mirrors `GET /api/channels` response.
- `JobStatus = "pending" | "running" | "done" | "failed" | "cancelled"` (backend uses "done" not "completed" — PR#22).
- `JOB_STATUSES: JobStatus[]` + `JOB_STATUS_LABELS: Record<JobStatus, string>` — для UI рендера.
- `Job = { id, channel_id, pattern, new_link, status, total, edited, failed, created_at, completed_at: string | null }` — mirrors `JobResponse` (PR#22).
- `JobListResponse = { jobs: Job[], total: number }`.
- `Log = { id, job_id, message_id, old_text: string | null, success, error: string | null, edited_at }` — mirrors `LogResponse` (PR#22).
- `LogListResponse = { logs: Log[], total: number }`.
- `ReplaceLinkRequest = { post_urls: string[], pattern, new_link }` — mirrors `POST /api/channels/{id}/replace-link` body (PR#22).
- `WsEvent = { type: "job_started" | "progress" | "completed" | "failed" | "cancelled", job_id, edited?, failed?, total?, message_id?, error? }` — mirrors `WsEvent` (PR#22), flat structure (не `{type, data}` как в media-gen — telesoft WS шлёт `{type, job_id, ...}` напрямую, не `{type, data: {...}}`).
- `AuthUser = { username: string }`, `MeResponse = { user: string }` — mirrors `GET /api/auth/me` (PR#18 возвращает `{user: username}`).
- `OkResponse = { status: string }` — mirrors `POST /api/auth/login` / `POST /api/auth/logout` responses.

### Шаг 4: WebSocket client (`web/src/lib/ws.ts`)

- `class WebSocketClient` — `connect()`, `onMessage(handler): () => void` (returns unsubscribe), `send(data)`, `close()`, `isConnected` getter.
- Auto-reconnect с exponential backoff: `RECONNECT_BASE_MS=1000`, `RECONNECT_MAX_MS=30000` (`delay = min(1000 * 2^attempts, 30000)`).
- Heartbeat: `HEARTBEAT_INTERVAL_MS=25000` (отправляет `{type: "ping"}`), `HEARTBEAT_TIMEOUT_MS=30000` (закрывает сокет если нет ответа).
- URL: `API_BASE.replace(/^http/, "ws") + "/api/ws"` — `http://` → `ws://`, `https://` → `wss://`.
- `manualClose` flag — `close()` ставит manualClose=true, `onclose` не триггерит reconnect. Иначе — auto-reconnect на любом разрыве.
- Auth через session cookie: browser автоматически шлёт cookie при WebSocket handshake (same-origin). Сервер проверяет через `ws_current_user(websocket)` (PR#22) — читает `websocket.scope["session"]`.
- Копия media-gen `web/src/lib/ws.ts` 1-в-1.

### Шаг 5: Layout + auth guard (`web/src/routes/+layout.{svelte,ts}`)

- `+layout.svelte` (Svelte 5 runes):
  - `$props()` destructures `{ data, children }`.
  - `$derived` для `isLogin` (`page.url.pathname === "/login"`) и `username` (`data?.user ?? null`).
  - App shell: sidebar (desktop, `sm:flex`) с навигацией (Channels), username + Logout button; main с header (mobile показывает "telesoft"), content (`{@render children()}`), mobile bottom nav.
  - `handleLogout()` — `POST /api/auth/logout` (catch игнорирует — redirect на /login regardless), `goto("/login")`.
  - Если `isLogin` → рендерит только children (без app shell) — чистая страница логина.
  - Tailwind: dark theme (`bg-slate-950`, `bg-slate-900`), `brand-600` для активной навигации.
- `+layout.ts` (LayoutLoad):
  - `export const prerender = false; export const ssr = false;` — whole app CSR.
  - `PUBLIC_PATHS = new Set(["/login"])` — skip auth for these.
  - `load({ url })`:
    - Если `pathname` in PUBLIC_PATHS → `return {}` (no user data).
    - Если NOT browser (SSR) → `return { user: null }` (avoid fetch during SSR).
    - Иначе `GET /api/auth/me` → `return { user: data.user }`.
    - На 401 (catch) → `redirect(303, "/login?redirectTo=" + encodeURIComponent(pathname + search))`.
  - Копия media-gen `+layout.ts` 1-в-1 (адаптирован тип `MeResponse.user: string`).

### Шаг 6: Login page (`web/src/routes/login/+page.svelte`)

- Svelte 5 runes: `$state` для `username`, `password`, `error`, `loading`; `$derived` для `redirectTo` (from query) и `canSubmit` (`username.trim().length > 0 && password.length > 0 && !loading`).
- `handleSubmit(event)` — preventDefault, валидация, `POST /api/auth/login` с `{username, password}`, на success → `goto(redirectTo, { replaceState: true })`.
- Error handling: 401 → "Invalid credentials", другой ApiError → `err.message`, network error → "Network error".
- Tailwind: centered card (`max-w-sm`), dark theme, `brand-600` submit button.
- `disabled={!canSubmit}` на submit button — предотвращает submit пустой формы.
- Не нужен `+page.ts` (pure CSR, нет load). Layout `+layout.ts` уже ставит `ssr=false` для всего приложения.

### Шаг 7: Root redirect (`web/src/routes/+page.ts`)

- `export const prerender = false; export const ssr = false;`
- `load()` → `redirect(307, "/channels")` — постоянный редирект с root на channels page.
- 307 (Temporary Redirect) — сохраняет method (GET→GET). Копия media-gen.

### Шаг 8: Channels page (`web/src/routes/channels/+page.{svelte,ts}`)

- `+page.ts` (PageLoad):
  - `export const prerender = false; export const ssr = false;`
  - `load()` → `GET /api/channels` → `return { channels: data.channels, total: data.total }`.
  - На ошибку → `error(status, "Failed to load channels")` (status из ApiError или 500).
- `+page.svelte` (Svelte 5 runes):
  - `$props()` destructures `{ data: { channels, total } }`.
  - `$state` для `error`, `busy`, `localRefresh`.
  - `$derived.by` для `channels` (`localRefresh ?? data.channels`) — merge load data с local refresh state (паттерн из media-gen для избежания `state_referenced_locally` warning).
  - `reload()` — `GET /api/channels`, обновляет `localRefresh`.
  - `deleteChannel(channel)` — `confirm()`, `DELETE /api/channels/{id}`, `reload()`.
  - Table: Title, Telegram ID, Username, Active (badge), Actions (Delete button).
  - Empty state: "No channels" в `{:else}` блоке `{#each}`.
  - "Add channel" button — `disabled` (stub, форма в отдельном issue).
  - Tailwind: dark theme table, `bg-emerald-900/60` для active badge, `bg-slate-800` для inactive.

### Шаг 9: Тесты (11 тестов, 4 файла)

- `web/src/tests/setup.ts` — `import "@testing-library/svelte"; afterEach(vi.restoreAllMocks)`.
- `web/src/tests/LayoutHarness.svelte` — обёртка для `+layout.svelte` (передаёт `data` prop, рендерит child slot).
- `web/src/tests/login.test.ts` (3 теста):
  1. `renders the form with username and password fields` — getByLabelText Username/Password, getByRole button "Sign in".
  2. `submits credentials and redirects on success` — mock `api.post` → resolve, fireEvent.input + submit, assert `api.post("/api/auth/login", {username, password})` + `goto("/channels", {replaceState: true})`.
  3. `shows an error on 401 response` — mock `api.post` → reject `ApiError(401)`, assert "Invalid credentials" displayed.
- `web/src/tests/channels.test.ts` (3 теста):
  1. `renders rows with title, telegram_id, and active badge` — 2 канала (active + inactive), assert title + badges.
  2. `renders empty state when there are no channels` — `channels: []`, assert "No channels".
  3. `calls DELETE /api/channels/{id} when Delete is clicked` — `confirm() → true`, `api.del` mock, click Delete, assert `api.del("/api/channels/7")`.
- `web/src/tests/layout.test.ts` (3 теста):
  1. `renders the Channels nav item` — getAllByText("Channels") ≥1.
  2. `renders the logout button` — getByRole button "Logout".
  3. `shows the signed-in username` — getAllByText(/admin/u) >0.
- `web/src/tests/api.test.ts` (2 теста):
  1. `serializes query params into the URL` — `api.get("/api/channels", {active_only: true, missing: undefined, count: 5})` → URL содержит `?active_only=true&count=5` (undefined пропущен).
  2. `throws ApiError on a non-ok response` — mock fetch → 404, assert rejects with `ApiError` + `{status: 404, message: "Not found"}`.
- Удалён `web/src/tests/smoke.test.ts` (PR#2) — реальные тесты заменяют smoke.

## Почему

Frontend MVP: юзер логинится через форму (session cookie через `credentials:include`), видит список каналов (title/telegram_id/active badge), может удалить канал. Auth guard в layout обеспечивает redirect на `/login` при 401 на любом маршруте (не только на прямом переходе). WebSocket client готов для будущей страницы jobs (показ прогресса замены ссылок в реальном времени) — автопереподключение + heartbeat. TS types mirroring backend Pydantic (`Channel`/`Job`/`Log`/`WsEvent`) — type safety между frontend и backend. Svelte 5 runes (`$props`/`$state`/`$derived`) — новая reactive модель, не Svelte 4 syntax (`export let`/`$:`/`on:click`). Референс media-gen 1-в-1 — проверенные паттерны, меньше шансов на ошибки.

## Pending

- **Channels create/edit form** — модальная форма для добавления/редактирования каналов (telegram_id + title + username). Сейчас только "Add channel" stub (disabled). Отдельный issue.
- **Replace-link page** — запуск замены ссылок (выбор постов, pattern, new_link) + WebSocket прогресс. Отдельный issue.
- **Jobs list page** — история запусков с фильтрами. Отдельный issue.
- **Logs view** — детали job (per-post logs). Отдельный issue.
- **WebSocket integration** — `ws.ts` клиент написан, но не используется в UI (пока нет jobs page). Подключить в replace-link page.

## Watch out

- **Svelte 5 runes, НЕ Svelte 4** — `$props()`, `$state()`, `$derived()`/`$derived.by()`, `{@render children()}`, `onclick={}` (не `on:click`), `bind:value`. svelte-check поймает Svelte 4 syntax как errors.
- **`credentials: "include"` в api.ts** — обязательно для session cookie. Без него fetch не отправляет cookie → 401 на каждом запросе. Cookie подписан `SECRET_KEY` (PR#18, Starlette SessionMiddleware).
- **`goto("/login?redirectTo=...")` на 401 в api.ts** — редирект только в browser (не SSR), и только если уже не на `/login` (избегаем loop). Layout `+layout.ts` отдельно делает `redirect(303)` на 401 от `GET /api/auth/me`.
- **WebSocket auth через session cookie** — browser автоматически шлёт cookie при WS handshake (same-origin). Сервер (`ws_current_user` в PR#22) читает `websocket.scope["session"]`. НЕ нужно передавать token в URL или headers.
- **`MeResponse = { user: string }`** (telesoft) vs `{ username: string }` (media-gen) — backend `GET /api/auth/me` возвращает `{"user": "admin"}` (PR#18), не `{"username": "admin"}`. `AuthUser` тип оставлен для совместимости, но layout использует `data?.user ?? null` (string).
- **`WsEvent` flat structure** (telesoft) vs `{type, data}` (media-gen) — telesoft WS шлёт `{"type": "progress", "job_id": 1, "edited": 2, ...}` напрямую (не вложенный `data`). `ws.ts` `WsMessage` тип — generic `{type, data}` (как в media-gen), но `types.ts` `WsEvent` — flat (mirrors backend `WsEvent` Pydantic model). UI будет кастить `msg.data` к `WsEvent`.
- **`$derived.by` для channels list** — merge load data (`data.channels`) с local refresh state (`localRefresh`). Паттерн из media-gen для избежания `state_referenced_locally` warning (Svelte 5 advice, не error).
- **`busy` state в channels page** — `$state(false)`, используется в `disabled={busy}` на Delete button. Не устанавливается в `true` в `deleteChannel` (упрощение — confirm() блокирует, api.del быстрый). Если нужны долгие операции — установить busy=true в try/finally.
- **`Response` body одноразовый в vitest** — `vi.fn().mockResolvedValue(response)` возвращает тот же Response на каждый вызов → "Body is unusable" на втором. Использовать `mockImplementation(() => Promise.resolve(jsonResponse(...)))` для fresh Response каждый вызов.
- **Biome trailing newline** — все файлы должны заканчиваться newline. `npm run format` (biome format --write) автоматически добавляет. Без него lint падает на "Formatter would have printed the following content".
- **`knip.json` entry patterns** — `src/routes/**/+page.ts` и `src/routes/**/+layout.ts` — после создания login/+page.svelte, channels/+page.{svelte,ts}, +layout.{svelte,ts}, +page.ts все patterns имеют matches. knip green.
- **`app.d.ts` `App.Locals.user: string | null`** — `string | null` (не `{username: string} | null`) — mirrors backend `current_user() -> str | None` (PR#18). `App.PageData.user?: string | null` — optional, layout может не вернуть user (для PUBLIC_PATHS).
- **SvelteKit pathname типобезопасность** — `page.url.pathname === "/login"` вызывает ts error если `/login` маршрут не существует (`'"/" | `/${string}/`' and '"/login"' have no overlap`). Решение: создать `/login` маршрут (даже пустой) чтобы типы включили `/login`. Поэтому layout + login в одном коммите.
- **Coverage** — Vitest не имеет coverage gate (в отличие от backend pytest `--cov-fail-under=80`). 11 тестов покрывают все новые файлы кроме `ws.ts` (нет UI-использования пока). Можно добавить `ws.test.ts` в follow-up issue.
- **`@testing-library/svelte` import в setup.ts** — добавлен `import "@testing-library/svelte"` (media-gen pattern). Без него `getByLabelText`/`getByRole` могут не работать корректно с Svelte 5.

## Coverage

- `lib/api.ts` — покрыт через `api.test.ts` (query serialization, ApiError) + через pages (login, channels, layout используют api mock).
- `lib/ws.ts` — НЕ покрыт тестами (нет UI-использования, WebSocket в jsdom требует mock). Добавить в follow-up.
- `lib/types.ts` — type-only, не требует runtime тестов.
- `routes/+layout.svelte` — покрыт через `layout.test.ts` (LayoutHarness + 3 теста).
- `routes/+layout.ts` — НЕ покрыт (load function, требует SvelteKit load context). Можно добавить через `@sveltejs/kit` testing в follow-up.
- `routes/login/+page.svelte` — покрыт через `login.test.ts` (3 теста).
- `routes/+page.ts` — НЕ покрыт (root redirect, требует SvelteKit load context).
- `routes/channels/+page.{svelte,ts}` — `+page.svelte` покрыт через `channels.test.ts` (3 теста), `+page.ts` НЕ покрыт (load function).