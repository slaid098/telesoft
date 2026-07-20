# ADR — PR PLACEHOLDER: SvelteKit skeleton with auth, layout, and api client

## Статус

Accepted (2026-07-20) — реализован SvelteKit frontend MVP с Svelte 5 runes, TypeScript, TailwindCSS, Biome, Vitest. Структура: `lib/{api,ws,types}.ts` (fetch wrapper с credentials:include + 401 redirect, WebSocket client с auto-reconnect+heartbeat, TS types mirroring backend Pydantic), `+layout.{svelte,ts}` (app shell + auth guard), `login/+page.svelte` (форма логина), `+page.ts` (root redirect), `channels/+page.{svelte,ts}` (список каналов + delete). 11 тестов — все зелёные.

## Контекст

telesoft — Telegram channel post editor. Backend MVP готов (auth PR#18, channels CRUD PR#20, replace-link runner+WS PR#22). Frontend пустой — только placeholder из PR#2 (`web/src/routes/+page.svelte` "Under construction"). Нужен frontend MVP: юзер логинится, видит список каналов, может удалить канал. Auth guard обеспечивает redirect на `/login` при отсутствии сессии. WebSocket client готов для будущей jobs page (показ прогресса замены ссылок).

Референс: `/root/workspace/media-gen/web/` — SvelteKit + Svelte 5 + TS + Tailwind + Biome + Vitest + Knip. Паттерны скопированы 1-в-1 (api.ts, ws.ts, layout, login, root redirect, tests).

Решения, которые надо было принять:
1. Frontend framework: SvelteKit+Svelte 5 vs React vs Vue vs plain Vite.
2. Styling: TailwindCSS vs CSS Modules vs styled-components.
3. Linter/formatter: Biome vs ESLint+Prettier.
4. Test runner: Vitest vs Jest vs Playwright.
5. Type safety: TypeScript vs plain JS.
6. Dead-code detection: Knip vs手动 review.
7. Svelte 5 runes vs Svelte 4 syntax.
8. API client: fetch wrapper vs axios vs TanStack Query.
9. WebSocket client: custom vs socket.io vs native.
10. Auth guard: layout load vs per-page vs middleware.

## Решение

### SvelteKit + Svelte 5 + TypeScript

- SvelteKit 2 (adapter-node для SSR/SSG/CSR, `ssr=false` для всего app — pure CSR MVP).
- Svelte 5 runes: `$props()`, `$state()`, `$derived()`/`$derived.by()`, `{@render children()}`, `onclick={}` (не Svelte 4 `export let`/`$:`/`on:click`).
- TypeScript strict (`tsconfig.json` extends `.svelte-kit/tsconfig.json` с `strict: true`).
- `app.d.ts` — `App.Locals.user: string | null`, `App.PageData.user?: string | null`.

### TailwindCSS

- `tailwind.config.js` — content paths `./src/**/*.{html,js,svelte,ts}`, `brand` color palette (синий: 50/100/500/600/700).
- `app.css` — `@tailwind base/components/utilities;` + `html, body { height: 100% }` + font-smoothing.
- `postcss.config.js` — `tailwindcss` + `autoprefixer`.
- Dark theme: `bg-slate-950` (body), `bg-slate-900` (sidebar/header/cards), `text-slate-100` (text), `brand-600` (active nav/submit).

### Biome (lint + format)

- `biome.json` — recommended, `noExplicitAny: error`, 2-space indent, double quotes, semicolons always, trailingCommas all, lineWidth 100.
- `overrides` для `*.svelte` — `style.useConst: off` (Svelte reactivity использует `let`).
- `scripts.lint` = `biome check`, `scripts.format` = `biome format --write`.
- Единый инструмент (lint + format) вместо ESLint+Prettier — меньше конфигов, быстрее.

### Vitest + @testing-library/svelte

- `vitest.config.ts` — jsdom, `@testing-library/svelte/vite` plugin, setup `src/tests/setup.ts` (`import "@testing-library/svelte"; afterEach(vi.restoreAllMocks)`).
- `include: ["src/**/*.{test,spec}.{js,ts}"]`.
- 11 тестов: login (3), channels (3), layout (3), api (2). Все зелёные.
- Mocking через `vi.hoisted` + `vi.mock("../lib/api", ...)`, `$app/navigation` goto, `$app/state` page.

### Knip (dead-code detection)

- `knip.json` — `entry: [src/**/*.svelte, src/routes/**/+page.ts, src/routes/**/+layout.ts, src/lib/{api,ws,types}.ts]`, `project: [src/**/*.{svelte,ts,js}]`.
- `scripts.knip` = `knip`. Green (no issues).

### Svelte 5 runes (НЕ Svelte 4)

- `$props()` вместо `export let`.
- `$state()` вместо `let` + `$:`.
- `$derived()` / `$derived.by()` вместо `$:`.
- `{@render children()}` вместо `<slot />`.
- `onclick={handler}` вместо `on:click={handler}`.
- `bind:value={var}` — работает в Svelte 5 (совместимость с Svelte 4).
- svelte-check (`npm run check`) ловит Svelte 4 syntax как errors.

### API client — fetch wrapper (`lib/api.ts`)

- `API_BASE` = `import.meta.env.VITE_API_BASE ?? window.location.origin ?? "http://localhost:8000"` (SSR-safe).
- `class ApiError extends Error { status: number; detail: unknown }` — кастомная ошибка.
- `request<T>(path, { method, body, query, headers })` — `credentials: "include"` (session cookie), JSON parse, на 401 в browser → `goto("/login?redirectTo=...")` + throw ApiError.
- `api = { get, post, put, patch, del }` — все методы используют `request<T>`.
- `buildUrl(path, query)` — URLSearchParams, пропускает undefined/null.
- НЕ axios / TanStack Query — fetch достаточно для MVP, меньше зависимостей. TanStack Query можно добавить если понадобится caching/retries.

### WebSocket client — custom (`lib/ws.ts`)

- `class WebSocketClient` — `connect()`, `onMessage(handler): () => void`, `send(data)`, `close()`, `isConnected`.
- Auto-reconnect с exponential backoff (1000ms base, 30000ms max).
- Heartbeat (25s interval, 30s timeout) — отправляет `{type: "ping"}`, закрывает сокет если нет ответа.
- URL: `API_BASE.replace(/^http/, "ws") + "/api/ws"`.
- Auth через session cookie (browser автоматически шлёт cookie при WS handshake).
- НЕ socket.io — native WebSocket достаточно для MVP. socket.io добавляет transport layer (long-polling fallback), но telesoft backend использует FastAPI WebSocket (native).

### Auth guard — layout load (`+layout.ts`)

- `LayoutLoad` — `GET /api/auth/me` на каждом маршруте (кроме PUBLIC_PATHS).
- 401 → `redirect(303, "/login?redirectTo=...")`.
- `prerender=false; ssr=false` — CSR, не пытаемся fetch при SSR.
- Дополнительно: `api.ts` `request()` на 401 → `goto("/login?redirectTo=...")` (для fetch после load, например в event handlers).
- НЕ per-page guard (boilerplate) и НЕ middleware (SvelteKit middleware ограничен, не имеет доступа к fetch).

### Standard file structure

- `lib/api.ts`, `lib/ws.ts`, `lib/types.ts` — переиспользуемые clients и types.
- `routes/+layout.{svelte,ts}` — app shell + auth guard (применяется ко всем маршрутам).
- `routes/+page.ts` — root redirect на `/channels`.
- `routes/login/+page.svelte` — форма логина (без `+page.ts`, pure CSR).
- `routes/channels/+page.{svelte,ts}` — список каналов + delete.
- `tests/` — `setup.ts`, `LayoutHarness.svelte`, `{login,channels,layout,api}.test.ts`.

## Альтернативы

### React (вместо SvelteKit+Svelte)

- Pro: огромная экосистема, больше разработчиков, больше библиотек.
- Con: larger bundle size, JSX runtime overhead, сложнее reactive model (hooks rules, stale closures), Vite plugin менее интегрирован чем SvelteKit.
- Решение: SvelteKit — меньше bundle, проще reactive model (runes), SvelteKit тесно интегрирован с Svelte (routing, SSR, build). Референс media-gen использует SvelteKit — переиспользование паттернов.

### Vue (вместо Svelte)

- Pro: progressive framework, composition API похож на runes, большая экосистема.
- Con: larger bundle чем Svelte, Vue Router менее интегрирован чем SvelteKit routing, меньше совместимости с media-gen референсом.
- Решение: Svelte — меньше bundle, runes проще composition API, SvelteKit routing из коробки.

### Plain Vite + vanilla TS (без framework)

- Pro: минимальный bundle, полный контроль, без framework abstractions.
- Con: нет routing, нет reactive model, нет SSR/SSG, много boilerplate для UI components.
- Решение: SvelteKit — routing, SSR (даже если `ssr=false`), reactive model, build optimisation из коробки. Для MVP с auth+layout+pages framework окупается.

### CSS Modules / styled-components (вместо Tailwind)

- Pro: scoped styles, no utility classes, CSS-in-JS для dynamic styles.
- Con: больше CSS файлов, сложнее consistent design system, runtime overhead для styled-components.
- Решение: Tailwind — utility classes, consistent design system (colors/spacing/typography), dark theme через `dark:` или явные classes, меньше CSS файлов. Референс media-gen использует Tailwind.

### ESLint + Prettier (вместо Biome)

- Pro: зрелая экосистема, больше плагинов, больше настроек.
- Con: два инструмента (lint + format), медленнее, больше конфигов.
- Решение: Biome — единый инструмент (lint + format), быстрее (Rust), меньше конфигов, recommended preset + `noExplicitAny: error` достаточно. Референс media-gen использует Biome.

### Jest (вместо Vitest)

- Pro: зрелая экосистема, больше разработчиков знакомы.
- Con: медленнее, less integrated with Vite, больше конфигов.
- Решение: Vitest — native Vite integration, faster, совместим с Jest API, `@testing-library/svelte/vite` plugin. Референс media-gen использует Vitest.

## Ключевые отклонения от спецификации

Зафиксированы в handoff, раздел "Watch out":
1. **`MeResponse = { user: string }`** (telesoft) vs `{ username: string }` (media-gen) — backend `GET /api/auth/me` возвращает `{"user": "admin"}` (PR#18). Layout использует `data?.user ?? null` (string), не `data?.user?.username`.
2. **`WsEvent` flat structure** (telesoft) vs `{type, data}` (media-gen) — telesoft WS шлёт `{"type": "progress", "job_id": 1, "edited": 2, ...}` напрямую. `ws.ts` `WsMessage` тип — generic `{type, data}` (совместимость с media-gen), `types.ts` `WsEvent` — flat (mirrors backend Pydantic).
3. **`JobStatus = "done"`** (telesoft) vs `"completed"` (media-gen) — backend runner (PR#22) использует `"done"` для успешного завершения.
4. **`ChannelListResponse = { channels, total }`** (telesoft) vs `Channel[]` directly (media-gen) — backend `GET /api/channels` возвращает `{channels: [...], total: N}` (PR#20). Channels page `+page.ts` destructures `data.channels`.
5. **`App.Locals.user: string | null`** (telesoft) vs `{username: string} | null` (media-gen) — mirrors backend `current_user() -> str | None` (PR#18).
6. **`busy` state в channels page** — `$state(false)`, используется в `disabled={busy}` но не устанавливается в `true` в `deleteChannel` (упрощение — confirm() блокирует, api.del быстрый). Не отклонение от спеки, но watch out для будущих долгих операций.
7. **Layout + login + root-redirect в одном коммите** — layout `+layout.svelte` использует `page.url.pathname === "/login"` — SvelteKit типобезопасное сравнение требует существования `/login` маршрута. Поэтому layout + login + root-redirect закоммичены вместе (не отдельными коммитами как в спеке). Иначе typecheck падает на первом коммите.
8. **Smoke-тест удалён** — `web/src/tests/smoke.test.ts` (PR#2) удалён, реальные тесты (11) заменяют. PR#2 smoke был placeholder для `vitest` exit code, теперь не нужен.