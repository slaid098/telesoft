---
pr: 36
issue: 35
branch: refactor/web/replace-link-limit
status: ready
created: 2026-07-20
---

# Handoff — PR #36: replace-link form uses limit instead of post URLs

## Что сделано

Реализован issue #35 — frontend форма replace-link переведена с ручного сбора URLs постов на auto-discovery (PR#34 backend уже готов). Юзер даёт канал + pattern + new_link + limit (сколько последних постов сканировать) — backend сам находит посты, regex-фильтрует, редактирует. Svelte 5 runes, client-side regex validation сохранена. 28 тестов (было 28 — channels/jobs/api/login/layout не менялись, replace-link.test.ts: 4 → 6). Biome, svelte-check, Vitest, Knip — green.

### Шаг 1: `web/src/lib/types.ts` — `ReplaceLinkRequest` изменён

- OLD: `export type ReplaceLinkRequest = { post_urls: string[]; pattern: string; new_link: string }`.
- NEW: `export type ReplaceLinkRequest = { pattern: string; new_link: string; limit: number }`.
- Порядок полей: `pattern, new_link, limit` (limit последним — required-поля первыми, mirrors backend `src/telesoft/schemas/job.py` из PR#34).
- Остальные типы (`Channel`, `ChannelCreate`, `ChannelUpdate`, `ChannelListResponse`, `JobStatus`, `JOB_STATUSES`, `JOB_STATUS_LABELS`, `Job`, `JobListResponse`, `Log`, `LogListResponse`, `WsEventType`, `WsEvent`, `WsEventPayload`) — БЕЗ изменений.

### Шаг 2: `web/src/lib/components/ReplaceLinkForm.svelte` — refactor

- **Убрано**: textarea для `post_urls`, `postUrls` state, `parsedUrls` derived, helper text "One URL per line… Parsed: N URL(s)", validation `parsedUrls.length > 0`.
- **Добавлен** `limit` number input:
  - Label: "Limit (last N posts to scan)".
  - `type="number"`, `min="1"`, `max="1000"`, `step="1"`, `bind:value={limit}`.
  - Helper text: "Сколько последних постов канала сканировать (1-1000, default 100)".
  - `let limit = $state(100)` — default 100 (matches backend `Field(default=100, ge=1, le=1000)`).
  - `const limitValid = $derived(Number.isFinite(limit) && limit >= 1 && limit <= 1000)`.
- **Сохранены** поля `pattern` (text, regex, required) и `new_link` (text, required).
- **Сохранена** client-side regex validation через `$effect`: `try { new RegExp(trimmedPattern) } catch (err) { patternError = ... }`. `patternError === null` gate в `canSubmit`.
- **Helper texts** обновлены под спеку: pattern — "Regex для поиска старой ссылки, напр. https://old\.example\.com"; new_link — "Чем заменить, напр. https://new.example.com".
- **`canSubmit`**: `!submitting && trimmedPattern.length > 0 && patternError === null && trimmedNewLink.length > 0 && limitValid`.
- **`handleSubmit`**: если `!canSubmit` → branch по причине (patternError → show, !limitValid → "Limit must be between 1 and 1000", иначе "Fill all required fields"). Submit → `POST /api/channels/{channelId}/replace-link` с body `{pattern: trimmedPattern, new_link: trimmedNewLink, limit}` (НЕ post_urls) → `onSubmit?.(result)` → `goto("/jobs/{job_id}")`.
- **Svelte 5 runes** во всём компоненте: `$props`, `$state`, `$derived`, `$effect`. `bind:value` на `<input type="number">` возвращает number (PR#26 gotcha — `String()` cast не нужен т.к. limit используется как number).

### Шаг 3: `web/src/routes/channels/[id]/+page.svelte` — БЕЗ изменений

- Файл использует `<ReplaceLinkForm channelId={channel.id} />` — props signature формы НЕ изменился (`channelId: number` остался, `onSubmit` optional). Изменений не требуется.
- `+page.ts` (load: `GET /api/channels/{id}` + `GET /api/jobs?channel_id={id}&limit=5`) — БЕЗ изменений.

### Шаг 4: Jobs pages — БЕЗ изменений

- `web/src/routes/jobs/+page.{ts,svelte}` — list + filter + auto-refresh polling — БЕЗ изменений.
- `web/src/routes/jobs/[id]/+page.{ts,svelte}` — detail + progress + cancel + logs + WS realtime — БЕЗ изменений.
- `job.total` теперь = число matching posts (НЕ limit) — PR#34 backend: runner `find_posts_with_pattern` фильтрует, `total = len(matching)`, `job_started` event содержит `total=len(matching)`. Прогресс `edited/total` корректен — UI читает `total` из WS events (не из формы).

### Шаг 5: Тесты

- **`web/src/tests/replace-link.test.ts`** — переписан (6 тестов, было 4):
  - `disables submit when fields are empty` — БЕЗ изменений (button disabled при пустых pattern/newLink, limit=100 default → но pattern/newLink пустые).
  - `disables submit when pattern is empty` — переименован с "when URLs are empty", адаптирован: заполняем new_link, НЕ заполняем pattern → disabled.
  - `shows error on invalid regex pattern` — БЕЗ изменений (`fireEvent.input` с `"("`, `findByText(/Invalid regex/i)`).
  - `disables submit when limit is out of range` — NEW: заполняем pattern + new_link (валидные), `limit=0` → disabled, `limit=1001` → disabled. `limitValid` derived срабатывает.
  - `opens form with default limit 100` — NEW: `render` → `screen.getByLabelText(/Limit/i)` → `expect(limitInput.value).toBe("100")`.
  - `submits with pattern, new_link and limit` — обновлён: заполняем pattern + new_link (limit остаётся default 100), submit → `expect(mockPost).toHaveBeenCalledWith("/api/channels/1/replace-link", { pattern: "https://old\\.example\\.com", new_link: "https://new.example.com", limit: 100 })` (НЕ post_urls) + `expect(mockGoto).toHaveBeenCalledWith("/jobs/5")`.
  - **УДАЛЁН** `parses textarea URLs into an array and submits` (textarea убран, `post_urls` нет в body).
- **`web/src/tests/channels.test.ts`** — не сломан (9 тестов: 6 Channels page + 3 ChannelForm). ChannelForm не затронут, channels page не затронут. Все 9 проходят.

### Проверка

- `cd web && npm run lint` → 0 issues (Biome, 36 files checked).
- `cd web && npm run typecheck` → 0 errors (svelte-check, 357 files). 2 pre-existing advisory warnings на `src/routes/jobs/[id]/+page.svelte` (`state_referenced_locally`, из PR#26, intentional — `let job = $state(data.job)` для "load once, update via events", advisory не error).
- `cd web && npm run test` → 28/28 passed (Vitest: 6 replace-link, 9 channels, 5 jobs, 3 layout, 3 login, 2 api).
- `cd web && npm run knip` → no issues.

## Почему

PR#34 отрефакторил backend `POST /api/channels/{id}/replace-link` на auto-discovery последних N постов канала через `get_last_messages` (PR#32, spike PR#30) — `ReplaceLinkRequest` теперь `{pattern, new_link, limit=100}` (limit 1..1000), без `post_urls`. Backend сам находит посты, regex-фильтрует, редактирует. Это снимает UX-блокер PR#14/PR#22/PR#26 — юзер больше не собирает URLs вручную (для 20 каналов × 100 постов = 2000 ручных URL-сборов — нереально). Frontend форма упрощена: limit input (одно число) вместо textarea URLs (много строк). Svelte 5 runes, client-side regex validation сохранена (fail-fast UX).

## Pending

- Ничего специфичного для этого PR. Общие frontend Pending из PR#26 остаются: edit channel mode (ChannelForm только create), job retry/delete UI, WebSocket shared client, job detail auto-refresh fallback, logs pagination. Этот PR их не трогает.

## Watch out

- **`bind:value` на `<input type="number">` возвращает number** (PR#26 gotcha) — `limit` это `number`, `Number.isFinite(limit)` корректен. `String()` cast НЕ нужен т.к. limit не используется в string-операциях. В тестах `fireEvent.input(limitInput, { target: { value: "0" } })` устанавливает `limit = 0` (number), `limitValid` derived перевычисляется → `false` → button disabled.
- **`canSubmit` учитывает `limitValid`** — без этого юзер мог бы submit с limit=0/1001 и получить 422 от backend. Client-side валидация (1..1000) зеркалит backend `Field(ge=1, le=1000)`. Дублирование намеренное: UX fail-fast + security (не доверяем клиенту).
- **`handleSubmit` error branch по причине** — `if (patternError) {...} else if (!limitValid) {...} else {...}`. Порядок важен: patternError проверяется первым (т.к. regex error более специфифична), limitValid вторым, generic "Fill all required fields" fallback.
- **Svelte 5 runes, НЕ Svelte 4** — `$props()`, `$state()`, `$derived()`, `$effect()`, `bind:value`, `onsubmit={handleSubmit}` (не `on:submit`). svelte-check ловит Svelte 4 syntax как errors.
- **`$effect` для regex validation** (side-effect, НЕ `$derived`) — `$derived` чистый (read-only), `$effect` для side-effects (обновление `patternError` state). PR#26 паттерн, сохранён.
- **2 svelte-check warnings на `jobs/[id]/+page.svelte`** — pre-existing из PR#26 (`state_referenced_locally`, advisory не error). Этот PR их не трогает. Не блокирует merge.
- **Knip green** — `entry` patterns (`src/**/*.svelte`, `src/routes/**/+page.ts`, `src/routes/**/+layout.ts`, `src/lib/api.ts`, `src/lib/ws.ts`, `src/lib/types.ts`) все имеют matches. Удаление `post_urls` из `ReplaceLinkRequest` не создаёт неиспользуемых exports (тип всё ещё используется в `ReplaceLinkForm.svelte`).
- **Biome format auto-fix** — `npm run format` после записи `ReplaceLinkForm.svelte` и `replace-link.test.ts` (1 файл auto-fixed — trailing newline / indent). Run format после каждого edit — паттерн из PR#24.
- **Channels detail page не требует изменений** — props signature `ReplaceLinkForm` (`channelId: number`, `onSubmit?`) не изменился. Файл `+page.svelte` остаётся как есть, `+page.ts` (load) тоже.
- **Jobs pages не требуют изменений** — `job.total` = число matching (PR#34 backend), UI читает `total` из WS events, не из формы. Прогресс `edited/total` корректен.
- **4 коммита** — `refactor(types)` → `refactor(web)` (form) → `test(web)` (tests) → `docs(handoff)` (этот handoff + ADR). Логическая последовательность: каждый коммит self-contained, можно revert по отдельности.
EOF