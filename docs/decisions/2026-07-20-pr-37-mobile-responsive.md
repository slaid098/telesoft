# ADR — PR #<PR-NUMBER>: mobile responsive layout — bottom nav, touch targets, cards

## Статус

Accepted (2026-07-20) — mobile-responsive адаптация frontend. Bottom nav `grid-cols-1` → `grid-cols-2` (критический баг фиксед), иконки `text-xl`, лейблы `text-xs`, `py-3` (≥44px touch target). Таблицы на 3 страницах (channels list, jobs list, job detail logs) дублированы карточками на `<640px` через dual-layout pattern `hidden sm:block` + `sm:hidden`. Primary кнопки (Save, Run replace-link, Cancel job) `py-2` → `py-2.5` (~44px). Desktop (≥640px) — БЕЗ визуальных изменений. Svelte 5 runes, no comments. 28 тестов green (3 селектора адаптированы под dual-layout), Biome, svelte-check (0 errors), Knip — clean.

## Контекст

PR#24 реализовал frontend skeleton с mobile nav (sidebar прячится <640px, bottom nav появляется). Но bottom nav имел критический баг: `grid grid-cols-1` — 2 пункта (Channels, Jobs) рендерились стопкой вместо горизонтально, занимая 2 строки и ломая mobile UX. Таблицы на 375px (iPhone SE width) давали плохой UX: мелкий текст + горизонтальный скролл (`overflow-x-auto` помогал, но юзер должен был скроллить горизонтально чтобы увидеть все колонки). Touch targets на primary кнопках были ~32-36px (`py-2` = 8px top + 8px bottom + ~20px text = ~36px), меньше Apple HIG / Material минимума 44px. Иконки в bottom nav были `text-lg` (18px), лейблы `text-[10px]` — мелко для touch.

Этот PR фиксит все 3 проблемы: bottom nav горизонтально с ≥44px touch target, таблицы дублированы карточками на mobile (dual-layout pattern), primary кнопки увеличены. Desktop (≥640px) — БЕЗ визуальных изменений.

## Решение

Tailwind responsive dual-layout pattern: `hidden sm:block` для table wrapper + `sm:hidden` для cards section. Оба блока в DOM, CSS media query скрывает один на основе viewport width (`sm:` = 640px). На desktop (≥640px) видна таблица, на mobile (<640px) — карточки. Стандартный Tailwind pattern для table↔card dual layout.

5 изменений по шагам (см. handoff для деталей):

1. **Bottom nav fix** (`web/src/routes/+layout.svelte`) — `grid-cols-1` → `grid-cols-2`, иконки `text-lg` → `text-xl`, лейблы `text-[10px]` → `text-xs`, `py-2` → `py-3`. Sidebar (desktop) — БЕЗ изменений.

2. **Таблицы → карточки на mobile** (3 файла):
   - `channels/+page.svelte` — 5 колонок → карточки (title link, active badge, telegram_id, username, delete).
   - `jobs/+page.svelte` — 6 колонок → карточки (#id link, status badge, channel, pattern truncate, progress, created).
   - `jobs/[id]/+page.svelte` — logs table 5 колонок → карточки (message_id, ✓/✗, error truncate, old_text truncate, edited_at). Header "Channel / Pattern" — `flex-col space-y-1 sm:flex-row sm:gap-3` (mobile в столбец, desktop в строку).

3. **Touch targets** — primary submit кнопки `py-2` → `py-2.5` (~44px): ChannelForm Save, ReplaceLinkForm "Run replace-link", job detail "Cancel job". Secondary кнопки — БЕЗ изменений.

4. **Иконки/лейблы bottom nav** — учтено в шаге 1.

5. **Тесты** — 3 селектора в `channels.test.ts` адаптированы под dual-layout (`getByText` → `getAllByText` + `.length > 0`, `getByRole` → `getAllByRole` + `[0]`). 28 тестов green. `jobs.test.ts` и `replace-link.test.ts` — БЕЗ изменений.

Ключевые отклонения от спецификации issue #37 (зафиксированы в handoff, раздел "Watch out"):
- **`getAllByText` вместо `getByText` в channels.test.ts** — спека указывала "адаптировать селекторы под новый markup". Dual-layout рендерит текст дважды (table + cards) → `getByText` падает на "Found multiple elements". `getAllByText` + `.length > 0` — stable, не зависит от того какой layout активен. Альтернатива — mock `window.matchMedia` в vitest setup, но усложняет тесты.
- **Header "Channel / Pattern" — `·` разделитель убран** — спека указывала `flex-col sm:flex-row` или `space-y-1 sm:space-y-0`. Реализовано `flex-col space-y-1 sm:flex-row sm:gap-3` с двумя `<span>` вместо одного text блока с `·`. На desktop минимальный visual change (gap вместо `·`), но semantic чище.
- **`grid-cols-2` hardcoded** — спека указывала `grid-cols-2`. Hardcoded для 2 nav items (Channels, Jobs). Если добавить 3-й пункт — нужно `grid-cols-3`. Альтернатива — dynamic class, но Tailwind не генерирует dynamic classes без safelist.

## Альтернативы

- **Tailwind responsive `hidden sm:block` / `sm:hidden` dual-layout (выбрано)** — table wrapper `hidden sm:block` (скрыт на mobile, виден на desktop), cards section `sm:hidden` (виден на mobile, скрыт на desktop). Оба блока в DOM, CSS media query скрывает один. Стандартный Tailwind pattern. Desktop (≥640px) — БЕЗ визуальных изменений (таблица остаётся). Mobile (<640px) — карточки. Минусы: оба блока в DOM (дублирование markup), в jsdom оба видимы → тесты на `getAllBy*`. Плюсы: простой, Tailwind-native, no JS, no separate mobile component.

- **CSS Grid reflow (не выбрано)** — таблица с CSS Grid `display: grid` + media query меняет `grid-template-columns` на mobile (1 колонка = карточки). Один markup, CSS меняет layout. Минусы: таблица semantic (`<table>`, `<tr>`, `<td>`) ломается при grid reflow (нужно `display: block` на `<tr>` + `display: grid` на ячейки). Сложно стилизовать (border, padding, header). Не работает с `overflow-x-auto`. Плюсы: один markup, no duplication.

- **Отдельный mobile компонент (не выбрано)** — `<ChannelsTable>` для desktop + `<ChannelsCards>` для mobile, условный рендер через `{#if isMobile}`. Минусы: нужен JS для определения viewport (или SvelteKit `userAgent`), дублирование логики (delete, reload) в двух компонентах, сложнее тестировать. Плюсы: чистый markup per layout, no CSS hiding.

- **Оставить таблицы с horizontal scroll (не выбрано)** — `overflow-x-auto` уже есть, юзер скроллит горизонтально. Минусы: плохой UX на mobile (мелкий текст, нужно скроллить чтобы увидеть все колонки, легко промахнуться по кнопке). Спека issue #37 явно требует карточки. Плюсы: no markup duplication, меньше кода.

- **Container queries вместо viewport `sm:` (не выбрано)** — Tailwind v4 `@container` для компонент-уровня адаптации (вместо page-уровня viewport). Минусы: Tailwind v4 ещё не stable в этом проекте (Biome config, svelte-check). Плюсы: компонент адаптируется к своему контейнеру, не к viewport (если компонент в узкой колонке — карточки, даже на desktop). Низкий приоритет — текущий `sm:` (640px) покрывает iPhone SE (375px) → iPad (768px) диапазон корректно.

## Последствия

- 28 тестов (6 replace-link, 9 channels, 5 jobs, 3 layout, 3 login, 2 api) — все зелёные. 3 селектора в `channels.test.ts` адаптированы (`getByText` → `getAllByText`).
- Biome, svelte-check (0 errors, 2 pre-existing advisory warnings из PR#26), Vitest, Knip — green.
- 5 коммитов: `fix(layout)` → `fix(channels)` → `fix(jobs)` → `fix(forms)` → `docs(handoff)`.
- Desktop (≥640px) — БЕЗ визуальных изменений (таблицы, sidebar, touch target `py-2.5` improvement на primary кнопках).
- Mobile (<640px) — bottom nav горизонтально (grid-cols-2), таблицы → карточки, touch targets ≥44px.
- Dual-layout pattern `hidden sm:block` + `sm:hidden` — стандарт для table↔card dual layout в этом проекте. Будущие таблицы (если появятся) должны следовать тому же pattern.

## Связанные ADR

- ADR PR#24 (frontend skeleton) — SvelteKit + Svelte 5 + TS + Biome + Vitest + Knip выбор, mobile nav (sidebar + bottom nav) изначальная реализация (с багом `grid-cols-1`).
- ADR PR#26 (channels UI) — ChannelForm, ReplaceLinkForm, jobs list, job detail pages (таблицы которые этот PR дублирует карточками).
- ADR PR#36 (replace-link limit) — ReplaceLinkForm refactor (форма не затронута, только touch target `py-2.5`).
