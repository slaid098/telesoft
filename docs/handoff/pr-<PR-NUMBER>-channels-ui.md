---
pr: <PR_NUMBER>
issue: 25
branch: feat/web/channels-ui
status: ready
created: 2026-07-20
---

# Handoff — PR #<PR_NUMBER>: Channel form, detail page, and replace-link UI

## Что сделано

Реализован issue #25 — полноценный frontend MVP для telesoft: форма добавления канала, детальная страница канала с запуском replace-link, страница списка jobs с авто-рефрешшем, детальная страница job с realtime-обновлениями через WebSocket, навигация (Channels, Jobs). 26 тестов (было 11) — все зелёные. Svelte 5 runes (`$props`/`$state`/`$derived`/`$effect`/`onMount`/`onDestroy`), TailwindCSS, Biome, svelte-check, Vitest, Knip — все green.

### Шаг 1: ChannelForm (`web/src/lib/components/ChannelForm.svelte`)

- Svelte 5 runes: `$state` для `telegramId`/`title`/`username`/`error`/`saving`, `$derived` для `trimmedTitle`/`trimmedUsername`/`telegramIdStr`/`telegramIdNum`/`hasTelegramId`/`canSubmit`.
- Props: `onSaved?: (channel: Channel) => void`, `onCancel?: () => void`.
- Поля: `telegram_id` (number, required, валидация через `Number.isFinite` + non-zero), `title` (text, required), `username` (text, optional — отправляется только если непустой).
- Submit → `POST /api/channels` → `onSaved(channel)`. Error display: ApiError → `err.message`, network error → "Network error".
- `disabled={!canSubmit}` на Save button — предотвращает submit пустой/невалидной формы.
- Tailwind: form card, labels, inputs, buttons — паттерн из media-gen `ChannelForm.svelte`.

### Шаг 2: Channels list page (`web/src/routes/channels/+page.svelte`)

- Добавлен "Add channel" button (раньше был disabled stub из PR#24) — toggles inline `ChannelForm` (`showForm = $state(false)`).
- После `onSaved` → `reload()` (GET /api/channels → `localRefresh` update).
- Каждая строка таблицы → `<a href="/channels/{id}">` на детальную страницу.
- Сохранены существующие тесты (delete, empty state, badge render) + добавлены 3 новых (open form, submit+refresh, cancel).

### Шаг 3: Channel detail page (`web/src/routes/channels/[id]/+page.{ts,svelte}`)

- `+page.ts` (PageLoad): `GET /api/channels/{id}` + `GET /api/jobs?channel_id={id}&limit=5` → `return { channel, recentJobs }`. 404 → `redirect(303, "/channels")`. Other errors → `error(status, ...)`.
- `+page.svelte`: header (title, telegram_id, is_active badge, username если есть), `ReplaceLinkForm`, "Run history" section (table id/status/progress/created для последних 5 jobs этого канала), link на `/jobs` (полный список).
- `statusClass(status)` helper — Tailwind классы для status badge (running=brand-600, done=emerald-700, failed=red-700, cancelled=amber-600).

### Шаг 4: ReplaceLinkForm (`web/src/lib/components/ReplaceLinkForm.svelte`)

- Svelte 5 runes: `$state` для `postUrls`/`pattern`/`newLink`/`error`/`submitting`/`patternError`, `$derived` для `parsedUrls`/`trimmedPattern`/`trimmedNewLink`/`canSubmit`.
- `$effect` для regex validation: `try { new RegExp(trimmedPattern) } catch (err) { patternError = err.message }`. Простой try/catch в браузере (без external libs).
- URL parsing: `postUrls.split("\n").map(trim).filter(empty)` — textarea split by newline, trim, filter empty. Live-обновление "Parsed: N URL(s)".
- Поля: `post_urls` (textarea, required, минимум 1 URL), `pattern` (text, regex, required), `new_link` (text, required).
- Validation: `canSubmit = !submitting && parsedUrls.length > 0 && trimmedPattern.length > 0 && patternError === null && trimmedNewLink.length > 0`.
- Submit → `POST /api/channels/{channelId}/replace-link` → `goto("/jobs/{job_id}")` (redirect на страницу job для realtime прогресса).
- Helper text под каждым полем — формат URLs (public/private), regex пример, replacement пример.

### Шаг 5: Jobs list page (`web/src/routes/jobs/+page.{ts,svelte}`)

- `+page.ts` (PageLoad): `GET /api/jobs?limit=50` + `GET /api/channels` (для lookup channel title по channel_id) → `return { jobs, total, channels }`.
- `+page.svelte`: table (id, channel title, pattern (truncated), status badge, progress edited/total, created_at), filter по status (dropdown: all + 5 статусов), link на `/jobs/{id}`.
- Auto-refresh каждые 5 секунд если есть running/pending jobs: `$effect` проверяет `hasRunning`, запускает `setInterval(refresh, 5000)`, cleanup в return функции.
- `channelsById` Map для O(1) lookup channel title по channel_id.
- `localRefresh` pattern (как в channels page) — merge load data с local refresh state.

### Шаг 6: Job detail page (`web/src/routes/jobs/[id]/+page.{ts,svelte}`) — WebSocket realtime

- `+page.ts` (PageLoad): `GET /api/jobs/{id}` + `GET /api/jobs/{id}/logs` → `return { job, logs }`. 404 → `redirect(303, "/jobs")`.
- `+page.svelte`: header (job id, status badge, channel, pattern, new_link), progress bar (edited/total + percent), Cancel button (POST /api/jobs/{id}/cancel — только если status=running/pending), logs table (message_id, success ✓/✗, error, old_text truncated, edited_at).
- **WebSocket**: `onMount` → `new WebSocketClient()` → `wsClient.onMessage(handleWsMessage)` → `wsClient.connect()`. `onDestroy` → `wsClient.close()` (НЕ shared client — per-spec, но client создаётся per-mount, close в destroy — корректно для detail page).
- `handleWsMessage(msg)`: фильтр по `job_id === job.id` (игнорирует события других jobs). `progress` event → update `job.edited`/`job.failed`/`job.total`. `completed`/`failed`/`cancelled` → update `job.status` (completed → "done") + `refetchLogs()` (GET /api/jobs/{id}/logs — свежие логи после завершения).
- `$state` для `job`/`logs`/`cancelError`/`cancelling`. `progressPct`/`isStoppable` через `$derived`.

### Шаг 7: Nav + layout (`web/src/routes/+layout.svelte`)

- Добавлен "Jobs" nav item (`{ href: "/jobs", label: "Jobs", icon: "⚙️" }`) в `navItems` array — Channels + Jobs.
- Active state через `page.url.pathname.startsWith(item.href)` — уже работало из PR#24, просто новый item.
- Mobile bottom nav автоматически подхватывает (тот же `navItems` array).

### Шаг 8: Types update (`web/src/lib/types.ts`)

- Добавлен `WsEventType` union type (`"job_started" | "progress" | "completed" | "failed" | "cancelled"`).
- `WsEvent` теперь использует `WsEventType` вместо inline union.
- Добавлен `WsEventPayload` тип для `msg.data` — `{ job_id?, edited?, failed?, total?, message_id?, error?, status? }` (все optional т.к. backend шлёт разные поля для разных event types).

### Шаг 9: Тесты (26 тестов, 6 файлов — было 11 тестов, 4 файла)

- `web/src/tests/channels.test.ts` (9 тестов, было 3): добавлены `mockPost` в mock, 3 теста для Add button behavior на channels page (open form, submit+refresh, cancel), 3 теста для ChannelForm component (disabled when empty, enabled when filled, calls onSaved after POST).
- `web/src/tests/replace-link.test.ts` (4 теста, новый): disabled when empty, disabled when URLs empty, invalid regex error, parses textarea URLs and submits with correct body + redirects.
- `web/src/tests/jobs.test.ts` (5 тестов, новый): renders header/status/progress/logs, cancel button calls POST, WS progress event updates progress, WS completed event refetches logs, WS events for other job_ids ignored.
- WebSocket mock: `vi.mock("../lib/ws", ...)` с class mock — `onMessage(handler)` регистрирует handler в Set, `emitWsEvent(type, data)` helper дёргает все handlers. `beforeEach` очищает `onMessageHandlers` Set.

## Почему

Полноценный frontend MVP: юзер логинится (PR#24), видит список каналов, добавляет новый канал через форму, открывает детальную страницу канала, запускает replace-link (textarea URLs + regex pattern + new_link), видит прогресс в реальном времени через WebSocket, может отменить job, видит логи (per-post success/error). История jobs доступна на отдельной странице с фильтром по статусу и auto-refresh. WebSocket realtime — ключевая фича: прогресс обновляется без polling, логи рефетчатся по завершении. Svelte 5 runes (`$props`/`$state`/`$derived`/`$effect`/`onMount`/`onDestroy`) — новая reactive модель, не Svelte 4 syntax. Regex validation в браузере (`try { new RegExp(pattern) } catch`) — без external libs, fail-fast на стороне клиента. URL parsing (split by newline, trim, filter empty) — простой и предсказуемый.

## Pending

- **Edit channel** — ChannelForm сейчас только create (нет edit mode). Backend `PATCH /api/channels/{id}` готов (PR#20). Добавить `channel?: Channel` prop в ChannelForm + `isEdit` derived — отдельный issue.
- **Job retry/delete** — backend endpoints готовы, но UI кнопок на jobs list/detail нет. Добавить в follow-up.
- **WebSocket shared client** — сейчас каждый job detail page создаёт свой `WebSocketClient` и закрывает в `onDestroy`. Для multiple job pages это N соединений. Оптимизация — shared client в layout, `onMessage` per-page. Низкий приоритет (MVP работает).
- **Job detail auto-refresh fallback** — если WS не подключён, нет polling fallback. Добавить `setInterval(refresh, 5000)` если `!wsClient.isConnected` — follow-up.
- **Logs pagination** — `GET /api/jobs/{id}/logs` возвращает первые 100 логов. Для больших jobs нужна pagination. UI сейчас показывает все логи разом.
- **Svelte 5 `state_referenced_locally` warnings** (2 шт на jobs detail page) — advisory, не errors. `let job = $state(data.job)` захватывает initial value, что намеренно (job state updates через WS). Фикс через `$derived` + side-effect `$effect` для copy — overkill для формы. Соответствует паттерну media-gen.

## Watch out

- **Svelte 5 runes, НЕ Svelte 4** — `$props()`, `$state()`, `$derived()`/`$derived.by()`, `{@render children()}`, `onclick={}` (не `on:click`), `bind:value`. svelte-check ловит Svelte 4 syntax как errors.
- **`bind:value` on `<input type="number">`** возвращает number (не string) — `telegramId.trim()` падает с `TypeError: trim is not a function`. Фикс: `String(telegramId ?? "").trim()` или `telegramIdStr = $derived(String(telegramId ?? ""))`.
- **`$effect` для regex validation** — `try { new RegExp(pattern) } catch (err) { patternError = err.message }` в `$effect`, не в `$derived` (т.к. side-effect — обновление `patternError` state). `$derived` чистый, `$effect` для side-effects.
- **Biome import ordering** — alphabetical by source path. `$lib/api` < `$lib/components/...` < `$lib/types` < `$lib/ws` < `svelte`. Type-only imports (`import type {...}`) interspersed with value imports по source order. Run `npm run format` после каждого edit — auto-fixes formatting.
- **WebSocket mock в vitest** — `vi.mock("../lib/ws", ...)` с class mock. `onMessage(handler)` должен регистрировать handler в Set (не возвращать static vi.fn()), чтобы `emitWsEvent` helper мог дёргать handlers. `beforeEach` очищает Set между тестами.
- **`$state` captures initial value of `$props()`** — `let job = $state(data.job)` захватывает `data.job` на mount, не реагирует на изменения `data.job` (load refresh). Это намеренно для job detail (job updates через WS, не через load). Svelte 5 advice warning (`state_referenced_locally`) — advisory, не error.
- **`goto("/jobs/{job_id}")` после replace-link submit** — redirect на job detail page для realtime прогресса. Альтернатива — показать progress inline на channel detail, но это дублирует логику job detail page.
- **Auto-refresh cleanup** — `$effect` в jobs list возвращает cleanup function (`clearInterval`). Svelte 5 автоматически вызывает cleanup при re-run effect или unmount. Без cleanup — leak interval между navigation.
- **WsEventPayload тип** — `msg.data` кастится к `WsEventPayload` (не `WsEvent`) т.к. wire format `{type, data: {...}}` — `data` содержит поля event'а (`job_id`/`edited`/`failed`/...), а `type` — на верхнем уровне. `WsEvent` (flat) — для удобства, `WsEventPayload` — реальная структура `data`.
- **Knip entry patterns** — `src/routes/**/+page.ts` и `src/routes/**/+layout.ts` — все patterns имеют matches после добавления channels/[id] и jobs/[id] маршрутов. Knip green.
- **Vitest coverage** — Vitest не имеет coverage gate. 26 тестов покрывают все новые файлы (ChannelForm, ReplaceLinkForm, channels page, channels detail page, jobs list page через layout test, job detail page). `+page.ts` load functions НЕ покрыты (требуют SvelteKit load context).

## Coverage

- `lib/components/ChannelForm.svelte` — покрыт через `channels.test.ts` (3 теста: disabled, enabled, onSaved).
- `lib/components/ReplaceLinkForm.svelte` — покрыт через `replace-link.test.ts` (4 теста: disabled, URLs empty, invalid regex, submit+redirect).
- `routes/channels/+page.svelte` — покрыт через `channels.test.ts` (9 тестов: 3 существующих + 3 Add button + 3 ChannelForm).
- `routes/channels/[id]/+page.svelte` — НЕ покрыт напрямую (требует channelsById mock + load context). Косвенно через ReplaceLinkForm tests.
- `routes/channels/[id]/+page.ts` — НЕ покрыт (load function).
- `routes/jobs/+page.svelte` — НЕ покрыт напрямую (требует channels mock + load context). Косвенно через layout test (Jobs nav item).
- `routes/jobs/+page.ts` — НЕ покрыт (load function).
- `routes/jobs/[id]/+page.svelte` — покрыт через `jobs.test.ts` (5 тестов: render, cancel, WS progress, WS completed refetch, WS ignore other job_ids).
- `routes/jobs/[id]/+page.ts` — НЕ покрыт (load function).
- `routes/+layout.svelte` — покрыт через `layout.test.ts` (3 теста, теперь включает Jobs nav item).
- `lib/types.ts` — type-only, не требует runtime тестов.
- `lib/ws.ts` — НЕ покрыт напрямую (mock'ается в jobs.test.ts через `vi.mock`).