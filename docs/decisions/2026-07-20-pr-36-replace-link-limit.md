# ADR — PR #36: replace-link form uses limit input instead of post URLs

## Статус

Accepted (2026-07-20) — frontend форма replace-link переведена с ручного сбора URLs постов (textarea) на auto-discovery (limit input). `ReplaceLinkRequest` в `web/src/lib/types.ts` теперь `{pattern, new_link, limit: number}` (без `post_urls`). `ReplaceLinkForm.svelte` использует number input (default 100, min 1, max 1000, step 1) вместо textarea. Submit → `POST /api/channels/{id}/replace-link` с body `{pattern, new_link, limit}`. Svelte 5 runes, client-side regex validation сохранена. 6 тестов (было 4) в `replace-link.test.ts`, 28 всего. Biome, svelte-check (0 errors), Vitest, Knip — green. Снимает UX-блокер PR#14/PR#22/PR#26 (ручной сбор URLs).

## Контекст

PR#26 реализовал frontend MVP с `ReplaceLinkForm.svelte` — textarea для `post_urls` (одна URL на строку, split by newline, trim, filter empty, live "Parsed: N URL(s)"), `pattern` (regex), `new_link`. Submit → `POST /api/channels/{id}/replace-link` с body `{post_urls, pattern, new_link}`. Backend (`PR#22`) парсил URLs через `parse_post_url` (PR#16), fetched каждый post by-ID через `get_messages(chat_id, ids=[...])`, regex-фильтровал, редактировал. Это работало для MVP одного канала с 5-10 постами.

PR#34 отрефакторил backend на auto-discovery: `ReplaceLinkRequest` = `{pattern, new_link, limit=100}` (limit 1..1000). Backend сам находит последние N постов канала через `get_last_messages` (PR#32, spike PR#30 — `channels.GetMessagesRequest` raw API + binary search max_id), regex-фильтрует, редактирует. `post_urls` убран из API. Снимает UX-блокер: 20 каналов × 100 постов = 2000 ручных URL-сборов → 20 запросов.

Frontend (PR#26) остался на старой форме с textarea. Этот PR приводит frontend в соответствие с новым backend API: убирает textarea, добавляет `limit` number input, обновляет `types.ts`, обновляет тесты. Channel detail page (`channels/[id]/+page.svelte`) и jobs pages — БЕЗ изменений (props signature формы не изменился, `job.total` = число matching из WS events).

## Решение

5 изменений по шагам (см. handoff для деталей):

1. **`web/src/lib/types.ts`** — `ReplaceLinkRequest` изменён: OLD `{ post_urls: string[]; pattern: string; new_link: string }` → NEW `{ pattern: string; new_link: string; limit: number }`. Порядок полей mirrors backend `src/telesoft/schemas/job.py` (PR#34). Остальные типы без изменений.

2. **`web/src/lib/components/ReplaceLinkForm.svelte`** — refactor (Svelte 5 runes):
   - **Убрано**: `postUrls` state, `parsedUrls` derived, textarea с helper text "One URL per line… Parsed: N URL(s)", `parsedUrls.length > 0` gate в `canSubmit`.
   - **Добавлен** `limit` number input: `let limit = $state(100)`, `bind:value={limit}`, `type="number"`, `min="1"`, `max="1000"`, `step="1"`, label "Limit (last N posts to scan)", helper text "Сколько последних постов канала сканировать (1-1000, default 100)". `limitValid = $derived(Number.isFinite(limit) && limit >= 1 && limit <= 1000)`.
   - **Сохранены** `pattern` (text, regex, required) и `new_link` (text, required) + client-side regex validation через `$effect` (`try { new RegExp(trimmedPattern) } catch { patternError = ... }`). Helper texts обновлены.
   - **`canSubmit`** = `!submitting && trimmedPattern.length > 0 && patternError === null && trimmedNewLink.length > 0 && limitValid`.
   - **`handleSubmit`** error branch по причине: patternError → show, !limitValid → "Limit must be between 1 and 1000", иначе "Fill all required fields". Submit → `POST /api/channels/{channelId}/replace-link` с body `{pattern, new_link, limit}` → `goto("/jobs/{job_id}")`.

3. **`web/src/routes/channels/[id]/+page.svelte`** — БЕЗ изменений. `<ReplaceLinkForm channelId={channel.id} />` — props signature не изменился (`channelId: number`, `onSubmit?`).

4. **Jobs pages** — БЕЗ изменений. `job.total` = число matching posts (PR#34 backend: `find_posts_with_pattern` → `total = len(matching)`, `job_started` event содержит `total=len(matching)`). UI читает `total` из WS events, не из формы. Прогресс `edited/total` корректен.

5. **Тесты** — `web/src/tests/replace-link.test.ts` переписан (6 тестов, было 4): `disables submit when fields are empty`, `disables submit when pattern is empty` (переименован), `shows error on invalid regex pattern`, `disables submit when limit is out of range` (NEW), `opens form with default limit 100` (NEW), `submits with pattern, new_link and limit` (обновлён — assert body без post_urls, с limit: 100). Удалён `parses textarea URLs into an array and submits` (textarea убран). `channels.test.ts` — 9 тестов не сломаны.

Ключевые отклонения от спецификации issue #35 (зафиксированы в handoff, раздел "Watch out"):
- **`limitValid` дублирует backend `Field(ge=1, le=1000)`** — client-side fail-fast UX + server-side security (не доверяем клиенту). Спека не указывала явно, но паттерн из PR#26 (regex validation client+server).
- **`handleSubmit` error branch по причине** — спека указывала "disabled when invalid", но не указывала error message branch. Реализован branch (patternError → limitValid → generic) для UX (юзер видит конкретную ошибку).
- **Channels detail page без изменений** — спека указывала "проверить что props передаются корректно (если signature не менялся — БЕЗ изменений)". Signature не изменился → без изменений.

## Альтернативы

- **Limit input вместо textarea URLs (выбрано)** — `limit` number input (default 100, min 1, max 1000, step 1). Backend сам находит последние N постов через PR#32 `get_last_messages`. Снимает UX-блокер (2000 ручных URLs → 20 запросов). Соответствует новому backend API (PR#34). Svelte 5 runes, `bind:value` на number input возвращает number. Limit валидация 1..1000 зеркалит backend `Field(ge=1, le=1000)`.

- **Dual mode: URLs + limit (не выбрано)** — `ReplaceLinkRequest { post_urls?: string[]; pattern; new_link; limit?: int }` — либо URLs (для конкретных постов), либо limit (для auto-discovery). Усложняет API (два режима), валидацию (если оба — приоритет?), тесты (двойные сценарии), UI (toggle между режимами). Спека issue #35 и backend PR#34 явно требуют убрать `post_urls` — auto-discovery единственный режим. Backend PR#34 `ReplaceLinkRequest` уже без `post_urls` (только `{pattern, new_link, limit}`).

- **Manual URLs only (не выбрано)** — оставить textarea для `post_urls`, НЕ добавлять limit. Backend PR#34 уже убрал `post_urls` из API — frontend не мог бы submit (422 unknown field). Требовало бы revert PR#34 или отдельный legacy endpoint. Противоречит issue #35 (явно требует limit input). UX-блокер PR#14/PR#22/PR#26 (ручной сбор 2000 URLs) остаётся.

- **Range slider для limit (не выбрано)** — `<input type="range" min="1" max="1000">` вместо number input. Менее точный ввод (юзер тянет слайдер, видит число). Для 1..1000 слайдер неудобен (большой диапазон, маленькие шаги). Number input даёт точный ввод + visible value. Спека указывала number input.

- **Dropdown с presets (не выбрано)** — `<select>` с опциями 10/50/100/500/1000. Ограничивает юзера пресетами, не даёт ввести произвольное число (например, 75). Спека указывала number input с min/max/step.

## Последствия

- 28 тестов (6 в `replace-link.test.ts`, 9 в `channels.test.ts`, 5 в `jobs.test.ts`, 3 в `layout.test.ts`, 3 в `login.test.ts`, 2 в `api.test.ts`) — все зелёные.
- Biome, svelte-check (0 errors, 2 pre-existing advisory warnings на `jobs/[id]/+page.svelte` из PR#26), Vitest, Knip — green.
- 4 коммита: `refactor(types)` → `refactor(web)` (form) → `test(web)` (tests) → `docs(handoff)` (этот ADR + handoff).
- `web/src/lib/types.ts` — `ReplaceLinkRequest` shape mirrors backend `src/telesoft/schemas/job.py` (PR#34). Single source of truth для frontend-backend contract.
- Channel detail page и jobs pages — БЕЗ изменений (props signature stable, `job.total` from WS events).

## Связанные ADR

- ADR PR#34 (backend auto-discovery) — `ReplaceLinkRequest` new shape, runner auto-discovers via `get_last_messages`.
- ADR PR#26 (channels UI) — `ReplaceLinkForm.svelte` Svelte 5 runes, `$effect` regex validation, textarea URLs (этот PR убирает textarea).
- ADR PR#24 (frontend skeleton) — SvelteKit + Svelte 5 + TS + Biome + Vitest + Knip выбор.
- ADR PR#22 (replace-link runner + WS) — `WsEvent` flat structure, `job.total` semantics.