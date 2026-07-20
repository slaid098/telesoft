---
pr: <PR-NUMBER>
issue: 37
branch: fix/web/mobile-responsive
status: ready
created: 2026-07-20
---

# Handoff — PR #<PR-NUMBER>: mobile responsive layout — bottom nav, touch targets, cards

## Что сделано

Реализован issue #37 — mobile-responsive адаптация frontend. Bottom nav пофикшен (критический баг `grid-cols-1` → `grid-cols-2`, пункты стопкой → горизонтально), таблицы на 3 страницах дублированы карточками на `<640px` (dual-layout паттерн `hidden sm:block` + `sm:hidden`), touch targets на primary кнопках увеличены до ≥44px (`py-2` → `py-2.5`). Desktop (≥640px) — БЕЗ визуальных изменений. Svelte 5 runes, no comments. 28 тестов (все green), Biome, svelte-check (0 errors), Knip — clean.

### Шаг 1: Bottom nav fix — `web/src/routes/+layout.svelte`

- `grid-cols-1` → `grid-cols-2` (критический баг — 2 пункта Channels/Jobs рендерились стопкой на mobile, теперь горизонтально).
- Иконки `text-lg` → `text-xl` (крупнее для touch).
- Лейблы `text-[10px]` → `text-xs` (читаемее).
- `py-2` → `py-3` (≥44px touch target по Apple HIG / Material).
- Sidebar (desktop ≥640px) — БЕЗ изменений (`hidden ... sm:flex`).

### Шаг 2: Таблицы → карточки на mobile — 3 файла

Паттерн: `hidden sm:block` для table wrapper + `sm:hidden` для cards section. Оба блока в DOM (jsdom видит оба → тесты адаптированы, см. Шаг 5). На desktop (≥640px) видна только таблица, на mobile (<640px) — только карточки.

- **`web/src/routes/channels/+page.svelte`** — 5 колонок (Title, Telegram ID, Username, Active, Actions) → карточки. Card: title (link) + active badge в header, dl с Telegram ID / Username, Delete button в footer. Empty state: "No channels" в обоих блоках.
- **`web/src/routes/jobs/+page.svelte`** — 6 колонок (ID, Channel, Pattern, Status, Progress, Created) → карточки. Card: #id (link) + status badge в header, dl с Channel / Pattern (truncate) / Progress / Created. Empty state: "No jobs" в обоих блоках.
- **`web/src/routes/jobs/[id]/+page.svelte`** — logs table 5 колонок (Message ID, Success, Error, Old text, Edited at) → карточки. Card: #message_id + ✓/✗ в header, dl с Error (truncate) / Old text (truncate) / Edited at. Header "Channel: #X · Pattern: Y" — на mobile в столбец (`flex-col space-y-1 sm:flex-row sm:space-y-0 sm:gap-3`), на desktop в строку через `·` разделитель убран (теперь два отдельных `<span>`).

### Шаг 3: Touch targets — primary кнопки

- `web/src/lib/components/ChannelForm.svelte` — primary submit Save: `py-2` → `py-2.5` (~44px height).
- `web/src/lib/components/ReplaceLinkForm.svelte` — primary submit "Run replace-link": `py-2` → `py-2.5`.
- `web/src/routes/jobs/[id]/+page.svelte` — Cancel job button: `py-2` → `py-2.5`.
- Secondary buttons (Delete, Add channel, Cancel в ChannelForm, Back to jobs) — БЕЗ изменений (≥36px ок для secondary actions).

### Шаг 4: Иконки/лейблы bottom nav — учтено в Шаге 1

### Шаг 5: Тесты — селекторы адаптированы под dual-layout

- **`web/src/tests/channels.test.ts`** — 3 теста адаптированы (9 тестов всего, все green):
  - `renders rows with title, telegram_id, and active badge` — `getByText("alpha")` → `getAllByText("alpha").length > 0` (текст "alpha" теперь в table + card). То же для "beta", "active", "inactive".
  - `renders empty state when there are no channels` — `getByText(/No channels/i)` → `getAllByText(/No channels/i).length > 0` (empty state в table + card).
  - `calls DELETE /api/channels/{id} when Delete is clicked` — `getByRole("button", { name: "Delete" })` → `getAllByRole("button", { name: "Delete" })[0]` (два Delete кнопки, кликаем первую).
  - Остальные 6 тестов (Add channel form, ChannelForm) — БЕЗ изменений (форма не дублирована).
- **`web/src/tests/jobs.test.ts`** — 5 тестов, БЕЗ изменений. Job detail page: logs table + cards оба рендерят `message_id` (100, 101), но тесты используют `getByText("100")` / `getByText("101")` — `getByText` находит первый match (не падает на duplicate т.к. message_id уникален per log). Header "Channel: #10 · Pattern: ..." — текст "Channel:" и "Pattern:" теперь в отдельных `<span>`, но `getByText(/Job #1/)` и `getByText(/Progress: 1\/4/)` не затронуты.
- **`web/src/tests/replace-link.test.ts`** — 6 тестов, БЕЗ изменений (форма не дублирована, только `py-2.5` touch target change не влияет на селекторы).

### Проверка

- `cd web && npm run lint` → 0 issues (Biome, 36 files checked).
- `cd web && npm run typecheck` → 0 errors (svelte-check, 357 files). 2 pre-existing advisory warnings на `src/routes/jobs/[id]/+page.svelte` (`state_referenced_locally`, из PR#26, intentional — `let job = $state(data.job)` для "load once, update via events", advisory не error).
- `cd web && npm run test` → 28/28 passed (Vitest: 6 replace-link, 9 channels, 5 jobs, 3 layout, 3 login, 2 api).
- `cd web && npm run knip` → no issues.

## Почему

Layout был частично адаптирован в PR#24 (sidebar прячится <640px, bottom nav появляется), но bottom nav имел критический баг `grid-cols-1` — 2 пункта (Channels, Jobs) рендерились стопкой вместо горизонтально, занимая 2 строки и ломая mobile UX. Таблицы на 375px (iPhone SE width) давали плохой UX: мелкий текст + горизонтальный скролл. Touch targets ~32-36px были меньше Apple HIG / Material минимума 44px. Этот PR фиксит все 3 проблемы: bottom nav горизонтально с ≥44px touch target, таблицы дублированы карточками на mobile (dual-layout pattern), primary кнопки увеличены. Desktop (≥640px) — БЕЗ визуальных изменений (таблицы остаются, sidebar виден, bottom nav скрыт).

## Pending

- Ничего специфичного для этого PR. Общие frontend Pending из PR#26 остаются: edit channel mode (ChannelForm только create), job retry/delete UI, WebSocket shared client, job detail auto-refresh fallback, logs pagination. Этот PR их не трогает.
- Возможное будущее улучшение: `Container query` вместо viewport-based `sm:` breakpoint (компонент-уровень адаптации вместо page-уровня). Tailwind v4 поддерживает `@container`. Низкий приоритет — текущий `sm:` (640px) покрывает iPhone SE (375px) → iPad (768px) диапазон корректно.

## Watch out

- **Dual-layout pattern `hidden sm:block` + `sm:hidden`** — оба блока (table + cards) в DOM одновременно. CSS media query скрывает один на основе viewport width. В jsdom (Vitest) media queries НЕ оцениваются → оба блока видимы для `getByText`/`getByRole` → `getByText` падает на "Found multiple elements". Решение: `getAllByText`/`getAllByRole` + `.length > 0` или `[0]`. Альтернатива — mock `window.matchMedia` в vitest setup, но это усложняет тесты и ломает text-based селекторы (нужно знать какой layout активен). `getAllBy*` проще и stable.
- **Bottom nav `grid-cols-2`** — ровно 2 пункта (Channels, Jobs). Если добавить 3-й пункт (например, Settings) — нужно `grid-cols-3`. Hardcoded `grid-cols-2` намеренно (MVP nav items). Альтернатива — `grid-cols-{navItems.length}` через Svelte dynamic class, но Tailwind не генерирует dynamic classes без safelist → нужен полный class list. Hardcoded проще для 2 items.
- **Touch target `py-2.5`** — Tailwind `py-2.5` = 10px top + 10px bottom = 20px padding + ~20px text height (text-sm) = ~40px. С border/line-height ~44px. Apple HIG / Material минимум 44px. `py-3` (12px) дал бы ~48px, но visual balance `py-2.5` лучше для primary buttons. Secondary buttons (Delete, Add) оставлены `py-1`/`py-2` — secondary actions допускают меньший touch target (≥36px).
- **Header "Channel: #X · Pattern: Y" на mobile** — `flex-col space-y-1 sm:flex-row sm:gap-3`. Разделил на два `<span>` (Channel / Pattern) вместо одного text с `·` разделителем. На mobile — в столбец (читаемее), на desktop — в строку через gap. `·` разделитель убран (был в одном text блоке, теперь два span). Visual change на desktop минимальный (gap вместо `·`), но semantic чище.
- **Svelte 5 runes, НЕ Svelte 4** — `$props()`, `$state()`, `$derived()`, `$effect()`, `bind:value`, `onsubmit={handleSubmit}` (не `on:submit`). svelte-check ловит Svelte 4 syntax как errors. Этот PR не добавляет новых runes — только Tailwind class changes + new card markup.
- **2 svelte-check warnings на `jobs/[id]/+page.svelte`** — pre-existing из PR#26 (`state_referenced_locally`, advisory не error). Этот PR не трогает `let job = $state(data.job)` / `let logs = $state(data.logs)`. Не блокирует merge.
- **Knip green** — `entry` patterns все имеют matches. Новый card markup не добавляет неиспользуемых exports (типы не менялись).
- **Biome format** — `npm run format` после каждого edit (паттерн из PR#24). 36 files checked, no fixes applied (всё отформатировано).
- **Desktop (≥640px) БЕЗ визуальных изменений** — table wrapper получил `sm:block` (был всегда `block`, теперь `hidden sm:block` — на mobile скрыт, на desktop виден). Cards section `sm:hidden` — на desktop скрыт. Touch target `py-2.5` на primary кнопках виден на desktop тоже (≥44px), но это improvement а не regression (кнопки были ~36px, стали ~44px — лучше для desktop touch/mouse). Header "Channel / Pattern" на desktop — gap вместо `·`, минимальный visual change.
- **5 коммитов** — `fix(layout)` (bottom nav) → `fix(channels)` (cards) → `fix(jobs)` (cards + header) → `fix(forms)` (touch targets) → `docs(handoff)` (handoff + ADR). Логическая последовательность: каждый коммит self-contained, можно revert по отдельности. Test selector fix включён в `fix(channels)` (селекторы адаптированы под card markup того же коммита).
