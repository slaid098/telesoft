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
  - web/src/lib/api.ts — fetch wrapper (credentials:include, 401→goto login, ApiError)
  - web/src/lib/ws.ts — WebSocket client (auto-reconnect, heartbeat, cookie auth)
  - web/src/lib/types.ts — TS types mirroring backend Pydantic (Channel/Job/Log/WsEvent)
  - web/src/routes/+layout.svelte — app shell (sidebar, header, mobile nav)
  - web/src/routes/+layout.ts — LayoutLoad auth guard (GET /api/auth/me, 401→redirect)
  - web/src/routes/+page.ts — root redirect → /channels
  - web/src/routes/login/+page.svelte — login form (Svelte 5 runes)
  - web/src/routes/channels/+page.svelte — channels table + delete
  - web/src/routes/channels/+page.ts — PageLoad GET /api/channels
  - web/Dockerfile.web — multi-stage build → adapter-node runtime
dependencies: [backend]
last_updated: 2026-07-20
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
├── .env.example          # VITE_API_BASE=http://localhost:8000
├── .gitignore
└── src/
    ├── app.html          # HTML shell (h-full + dark theme body bg-slate-950)
    ├── app.css           # @tailwind base/components/utilities + html,body height:100% + font-smoothing
    ├── app.d.ts          # App.Locals.user: string | null, App.PageData.user?, App.Error, App.PageStore
    ├── lib/
    │   ├── api.ts        # fetch wrapper: credentials:include, ApiError, 401→goto login, api={get,post,put,patch,del}
    │   ├── ws.ts         # WebSocketClient: auto-reconnect (1s→30s backoff), heartbeat (25s/30s), cookie auth
    │   └── types.ts      # TS types mirroring backend Pydantic: Channel, Job, Log, WsEvent, JobStatus, ReplaceLinkRequest
    ├── routes/
    │   ├── +layout.svelte  # app shell: sidebar (Channels nav + Logout), header (username), mobile bottom nav; Svelte 5 runes
    │   ├── +layout.ts     # LayoutLoad auth guard: GET /api/auth/me, 401→redirect(303,/login?redirectTo=...); prerender=false, ssr=false
    │   ├── +page.svelte   # (удалён в PR#24 — root redirect в +page.ts)
    │   ├── +page.ts       # root redirect(307, /channels)
    │   ├── login/
    │   │   └── +page.svelte  # login form: $state username/password/error/loading, $derived canSubmit, POST /api/auth/login
    │   └── channels/
    │       ├── +page.svelte  # channels table (title/telegram_id/active badge/delete), empty state, $derived.by merge load+localRefresh
    │       └── +page.ts      # PageLoad: GET /api/channels → {channels, total}
    └── tests/
        ├── setup.ts              # import @testing-library/svelte; afterEach(vi.restoreAllMocks)
        ├── LayoutHarness.svelte  # обёртка для +layout.svelte в тестах (передаёт data, рендерит child slot)
        ├── login.test.ts         # 3 теста: form render, submit+redirect, 401 error
        ├── channels.test.ts      # 3 теста: rows render, empty state, delete action
        ├── layout.test.ts        # 3 теста: Channels nav, Logout button, username display
        └── api.test.ts           # 2 теста: query serialization, ApiError on non-ok
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
- **TS types mirroring backend Pydantic** — `Channel`/`Job`/`Log`/`WsEvent`/`JobStatus`/`ReplaceLinkRequest` (PR#20/22). `JobStatus="done"` (не "completed"), `WsEvent` flat structure (не `{type, data}`), `MeResponse={user: string}` (не `{username}`)
- **`$derived.by` для merge load+localRefresh** — паттерн из media-gen для избежания `state_referenced_locally` warning (Svelte 5 advice)
- **Layout + login в одном коммите** — `page.url.pathname === "/login"` требует существования `/login` маршрута (SvelteKit типобезопасное сравнение, иначе ts error)