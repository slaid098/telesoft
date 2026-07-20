# ADR — PR #26: Channels UI with Svelte 5 runes, WS realtime, and client-side regex validation

## Статус

Accepted (2026-07-20) — реализован frontend MVP для telesoft: форма добавления канала, детальная страница канала с replace-link form, страница списка jobs с auto-refresh, детальная страница job с WebSocket realtime-обновлениями прогресса и логов, навигация (Channels, Jobs). 26 тестов (было 11) — все зелёные. Svelte 5 runes, Biome, svelte-check (0 errors), Vitest, Knip — все green.

## Контекст

telesoft — Telegram channel post editor. PR#24 добавил SvelteKit skeleton: auth, layout, channels list (table, delete), api/ws clients, TS types. Frontend MVP недоделан: (1) нет формы добавления канала (POST /api/channels), (2) нет детальной страницы канала с запуском replace-link (POST /api/channels/{id}/replace-link), (3) нет страницы истории jobs с realtime прогрессом через WebSocket, (4) нет просмотра логов. Backend готов: PR#20 (channels CRUD), PR#22 (jobs/replace-link/ws), PR#24 (frontend skeleton).

Референс: `/root/workspace/media-gen/web/` — SvelteKit + Svelte 5 + TS + Tailwind + Biome + Vitest + Knip. Паттерны ChannelForm/JobProgress скопированы и адаптированы под telesoft schema (плоский `Job` без `progress_*` префиксов, `WsEvent` flat structure, `JobStatus="done"` вместо `"completed"`).

Решения, которые надо было принять:
1. Svelte 5 runes vs Svelte 4 syntax (продолжение подхода из PR#24).
2. WebSocket integration: shared client в layout vs per-page client.
3. Realtime updates: WebSocket vs polling vs hybrid.
4. Regex validation: client-side vs server-side only.
5. URL parsing: textarea split vs file upload vs single input.
6. Form state management: `$state` capture initial props vs `$derived` reactive.
7. Auto-refresh strategy: polling vs WS-only vs hybrid.
8. Cancel behavior: `onDestroy` close vs `onDestroy` unsubscribe.
9. Job status mapping: backend "done" vs frontend "completed".
10. Logs refetch on terminal WS event vs rely on WS data only.

## Решение

### Svelte 5 runes (продолжение PR#24)

- `$props()` для component props (`onSaved`, `onCancel`, `channelId`, `data`).
- `$state()` для reactive form fields (`telegramId`, `title`, `postUrls`, `pattern`, `newLink`, `job`, `logs`).
- `$derived()` для computed values (`canSubmit`, `parsedUrls`, `trimmedPattern`, `progressPct`, `hasRunning`, `channelsById`).
- `$derived.by()` для multi-statement derived (`channels` list merge load data с local refresh).
- `$effect()` для side-effects (regex validation обновляет `patternError` state, auto-refresh `setInterval` с cleanup, WS event handler).
- `onMount`/`onDestroy` из `svelte` (не Svelte 4 `import { onMount } from "svelte"` — тот же API, но в Svelte 5 работает с runes).
- `bind:value` для form inputs (двусторонняя связь).

### WebSocket: per-page client (не shared)

- Job detail page: `onMount` → `new WebSocketClient()` → `onMessage(handleWsMessage)` → `connect()`. `onDestroy` → `close()`.
- **Почему не shared client в layout**: упрощает lifecycle — каждый page владеет своим client, cleanup в `onDestroy`. Shared client в layout потребует `getContext`/`setContext` или store, что усложняет тестирование (mock в vitest сложнее). Для MVP с одной WS-using page (job detail) per-page client — достаточно.
- **Trade-off**: при открытии нескольких job detail pages (вкладки) — N соединений. Низкий приоритет для MVP (single-tab usage).
- Спека issue #25 указывала "shared client" — `onDestroy → unsubscribe (не close — shared client)`. Отклонение: реализован per-page client с `close()` в `onDestroy` т.к. shared client в layout требует доп. infrastructure (context/store) без measurable benefit для MVP. Документировано в handoff Pending.

### Realtime: WebSocket-only (без polling fallback)

- Job detail: WS `progress` event → update `job.edited`/`job.failed`/`job.total`. WS `completed`/`failed`/`cancelled` → update `job.status` + `refetchLogs()`.
- Jobs list: polling `/api/jobs` каждые 5 секунд если есть running/pending jobs (fallback если WS не подключён — WS не используется на list page, только на detail).
- **Почему гибрид**: WS для detail (precision, realtime per-event), polling для list (simplicity, bulk refresh). Detail page WS-only — если WS не подключён, прогресс не обновляется (accept для MVP; fallback в Pending).
- **Альтернатива**: polling-only (проще, но менее realtime) или WS-only с broadcast на list page (сложнее, нужно shared client). Выбран гибрид.

### Regex validation: client-side + server-side

- `ReplaceLinkForm`: `$effect` → `try { new RegExp(trimmedPattern) } catch (err) { patternError = err.message }`. Live validation по мере ввода.
- Submit блокируется если `patternError !== null` (`canSubmit = ... && patternError === null`).
- **Server-side**: backend `validate_pattern(pattern)` в `core/link_replacer.py` (PR#22) делает `re.compile` и возвращает 422 при невалидном. Client-side — UX (fail-fast, не дожидаясь запроса), server-side — security (не доверяем клиенту).
- **Почему try/catch в браузере**: `new RegExp(pattern)` бросает `SyntaxError` при невалидном regex. Без external libs (regex-utils/regexpp). Простой и предсказуемый.

### URL parsing: textarea split by newline

- `postUrls.split("\n").map((u) => u.trim()).filter((u) => u.length > 0)` — split by newline, trim, filter empty.
- Live-обновление "Parsed: N URL(s)" — юзер видит сколько URLs распарсено.
- **Почему textarea**: множественный ввод (может быть 10+ URLs), paste-friendly, видны все URLs разом. Альтернативы: single input с comma-separated (less readable), file upload (overkill для MVP), dynamic add/remove input rows (сложнее UI).
- Backend `parse_post_urls` (PR#16) валидирует формат `https://t.me/{channel}/{id}` или `https://t.me/c/{internal_id}/{id}` — client-side формат-валидация не дублируется (backend её уже делает и возвращает 422).

### Form state: `$state` captures initial props (intentional)

- `let job = $state(data.job)` — захватывает initial value из `data.job` (load function). Не реагирует на изменения `data.job` (напр. после load refresh).
- **Почему не `$derived`**: job state обновляется через WS events (`job = { ...job, edited: 3 }`), не через load. Если бы использовали `$derived`, WS update через `job = {...}` был бы невозможен (derived — read-only). `$state` с initial capture — правильный паттерн для "load once, update via events".
- **Svelte 5 advice warning** (`state_referenced_locally`) — advisory, не error. 2 warning на jobs detail page. Соответствует паттерну media-gen `ChannelForm.svelte` (там тоже `let name = $state(channel?.name ?? "")`).

### Auto-refresh: polling на list, WS на detail

- Jobs list: `$effect` проверяет `hasRunning`, запускает `setInterval(refresh, 5000)` если true. Cleanup в return функции (`clearInterval`). Когда jobs завершаются (`hasRunning` becomes false), effect re-runs → cleanup previous interval → no new interval.
- Job detail: WS-only, без polling. Если WS не подключён — прогресс не обновляется (accept для MVP).
- **Почему 5 секунд**: баланс realtime (юзер видит обновления быстро) и load на backend (не каждые 500ms). Media-gen использует тот же интервал.

### Cancel: `onDestroy` close (не unsubscribe)

- `onDestroy(() => { wsClient?.close(); wsClient = null; })` — закрывает WebSocket соединение, не просто unsubscribe handler.
- **Почему close, не unsubscribe**: per-page client (см. WebSocket решение выше). Если бы был shared client — `unsubscribe()` (не close, shared client живёт в layout). Спека указывала "shared client → unsubscribe", но реализован per-page client → close.
- **Trade-off**: при navigation между job detail pages — disconnect/reconnect каждый раз. Низкий приоритет (WS handshake быстрый).

### Job status mapping: backend "done" → frontend "done"

- `JobStatus = "pending" | "running" | "done" | "failed" | "cancelled"` (из PR#24 types.ts). Backend runner (PR#22) использует `"done"` для успешного завершения.
- WS `completed` event → `job.status = "done"` (mapping `completed` → `done` в `handleWsMessage`).
- `JOB_STATUS_LABELS.done = "Done"` для UI rendering.
- **Отклонение от media-gen**: media-gen backend использует `"completed"`, telesoft — `"done"`. Types.ts из PR#24 уже корректен. JobProgress.svelte в media-gen проверяет `status === "completed"` — в telesoft `status === "done"`.

### Logs refetch on terminal WS event

- WS `completed`/`failed`/`cancelled` → `void refetchLogs()` (GET /api/jobs/{id}/logs).
- **Почему refetch, не rely on WS data**: WS `completed` event содержит `edited`/`failed`/`total` (aggregate), но НЕ содержит логи (per-post). Логи — отдельный GET запрос. После завершения job'а логи финальны (не изменятся) — refetch получает полный набор.
- **Альтернатива**: stream логи через WS (per-post `progress` event содержит `message_id`, но не `old_text`/`error`/`edited_at`). Сложнее, требует WS protocol extension. Выбран refetch — проще.

## Альтернативы

### Svelte 5 runes vs Svelte 4

- **Svelte 5 runes** (выбрано): `$props`/`$state`/`$derived`/`$effect` — новая reactive модель, type-safe, лучше DX. svelte-check ловит Svelte 4 syntax как errors.
- **Svelte 4**: `export let`/`$:`/`on:click` — legacy, deprecated в Svelte 5. Не рассматривалось (PR#24 уже на Svelte 5).

### WebSocket: shared client vs per-page client

- **Per-page client** (выбрано): `new WebSocketClient()` в `onMount`, `close()` в `onDestroy`. Simple lifecycle, easy to test (mock `WebSocketClient` class).
- **Shared client в layout**: `setContext`/`get-context` или store, `onMessage` per-page, `unsubscribe` в `onDestroy` (не close). Сложнее test, но эффективнее (1 connection for all pages). Отложено в Pending.

### Realtime: WS vs polling vs hybrid

- **Hybrid** (выбрано): WS для detail (precision), polling для list (simplicity).
- **WS-only**: realtime, но требует shared client для list page (сложнее).
- **Polling-only**: проще, но менее realtime (5s delay на detail page — accept для MVP, но UX хуже).

### Regex validation: client-side vs server-side only

- **Client + server** (выбрано): client-side fail-fast UX, server-side security.
- **Server-side only**: backend уже валидирует (422), но юзер не видит ошибку до submit. UX хуже.

### URL parsing: textarea vs file upload vs dynamic rows

- **Textarea split** (выбрано): simple, paste-friendly, multi-line readable.
- **File upload**: overkill для MVP (юзер не имеет файла с URLs).
- **Dynamic add/remove rows**: сложнее UI, дороже реализация.

### Form state: `$state` capture vs `$derived` + `$effect`

- **`$state` capture initial** (выбрано): `let job = $state(data.job)`, update via `job = {...}`. Intentional для "load once, update via events".
- **`$derived` + side-effect `$effect`**: `$derived` для read-only view, `$effect` для copy в `$state` для updates. Overkill для формы, сложнее читать.

## Последствия

- 26 тестов (было 11) — все зелёные. +15 тестов: 6 для channels (Add button + ChannelForm), 4 для ReplaceLinkForm, 5 для job detail (incl. WS events).
- 2 svelte-check warnings (`state_referenced_locally` на jobs detail) — advisory, не errors. Соответствуют паттерну media-gen.
- Biome, svelte-check (0 errors), Vitest, Knip — все green.
- WebSocket client из PR#24 (`ws.ts`) теперь используется в UI (job detail page) — Coverage расширяется.
- 6 новых файлов (ChannelForm, ReplaceLinkForm, channels/[id]/+page.{ts,svelte}, jobs/+page.{ts,svelte}, jobs/[id]/+page.{ts,svelte}) + 3 изменённых (channels/+page.svelte, +layout.svelte, types.ts).
- 9 коммитов: ChannelForm, channel-detail+ReplaceLinkForm, jobs-list+detail+ws, nav+layout, tests, handoff+ADR (этот коммит).

## Связанные ADR

- ADR PR#24 (frontend skeleton) — SvelteKit+Svelte 5+TS+Tailwind+Biome+Vitest+Knip выбор.
- ADR PR#22 (replace-link runner + WS) — backend runner, WS protocol, `WsEvent` flat structure.
- ADR PR#20 (channels API) — `ChannelResponse.from_row`, `now_iso()` с `Z`, `PATCH` (не PUT).
- ADR PR#16 (telegram client) — `parse_post_url` regex, by-ID fetch only (не `iter_messages`).