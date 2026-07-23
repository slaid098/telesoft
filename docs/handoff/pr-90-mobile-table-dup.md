---
pr: 90
issue: 89
branch: fix/jobs/mobile-table-duplication
status: ready
created: 2026-07-23
---

# Handoff — PR #90: fix(jobs): mobile table duplication

## Что сделано

Реализован issue #89 — bugfix регрессии PR#38 (mobile responsive layout): на 2 из 4 table wrappers в jobs-страницах пропущён Tailwind-класс `hidden` → на мобиле (<640px) таблица и карточки видны одновременно → дублирование данных. PR#40 фиксил channels-страницы, jobs-страницы пропустил.

### Фикс 1: `web/src/routes/jobs/+page.svelte:121`

- `class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block"` → `class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block"`.
- Tailwind dual-layout паттерн: `hidden sm:block` = скрыт на <640px, block на ≥640px. Cards section (`sm:hidden`) видна только на <640px. Без `hidden` таблица видна всегда → дублирование с cards на mobile.

### Фикс 2: `web/src/routes/jobs/[id]/+page.svelte:201`

- Та же правка в блоке логов (logs table). `{:else}` ветка когда `logs.length > 0` — раньше table + cards рендерились одновременно на mobile.

### Regression test: `web/src/tests/jobs.test.ts`

- 2 новых теста в `describe("Jobs list page — dual-layout (regression for #89)")` и `describe("Job detail page — dual-layout (regression for #89)")`.
- Проверка через DOM: table wrapper имеет `classList.contains("hidden")` и `classList.contains("sm:block")` = true; cards section (`div.space-y-3.sm:hidden`) существует и имеет `sm:hidden`.
- jsdom НЕ применяет Tailwind CSS (нет layout), но классы в DOM присутствуют — проверка `classList` надёжно ловит регрессию (пропущенный `hidden`).
- Переиспользованы существующие `makeJob`/`makeLog`/`makeChannel` helpers и mock'и из `jobs.test.ts`. Новых mock'ов не добавлено.
- Было 43 теста → стало 45 (6 тестовых файлов, все green).

### Проверки

- `npm run lint` (Biome) — green (1 файл отформатирован: двойные кавычки в `querySelectorAll`).
- `npm run typecheck` (svelte-check) — 0 errors, 2 pre-existing warnings (`state_referenced_locally` на `jobs/[id]/+page.svelte:10-11`, PR#26 documented, не трогал).
- `npm run test` (Vitest) — 45/45 passed.
- `rg "sm:block"` по `web/src/routes/**/*.svelte` — все 4 table wrappers теперь `hidden ... sm:block`, все 4 cards sections `sm:hidden`. Layout span (`+layout.svelte:60`) уже имел `hidden sm:block`.

## Почему

PR#38 (mobile responsive layout) внедрил dual-layout паттерн: table wrapper = `hidden ... sm:block` (скрыт на <640px), cards section = `sm:hidden` (скрыта на ≥640px). На 2 из 4 таблиц пропустили `hidden` — таблица видна на всех экранах (Tailwind `sm:block` = block на ≥640px, но и на <640px тоже block, т.к. нет `hidden`), а cards (`sm:hidden`) видны на <640px → оба блока одновременно на mobile. PR#40 фиксил channels list/detail pages, но jobs list/detail pages остались с тем же багом. Пользователь сообщил дублирование данных на mobile (issue #89).

## Pending

- **E2E smoke test на mobile viewport** — Playwright E2E (PR#42) проверяет мобильный flow, но явно не ассертит `hidden`/`sm:block` классы. Можно добавить visual regression или class assertion. Follow-up.
- **Shared `statusClass` helper** — функция дублируется в 4 файлах (`jobs/+page.svelte`, `jobs/[id]/+page.svelte`, `channels/[id]/+page.svelte` и в `jobs/+page.svelte` list). PR#40 отмечал как follow-up — не в scope.
- **Pre-existing `state_referenced_locally` warnings** — `jobs/[id]/+page.svelte:10-11` (`let job = $state(data.job)`, `let logs = $state(data.logs)`), PR#26 documented as intentional ("load once, update via events"). Не фиксятся.

## Watch out

- **`hidden sm:block` vs `sm:block`** — легко перепутать (это уже 3-й PR фиксящий эту регрессию: PR#40 channels, этот PR jobs). `hidden` без `sm:block` = скрыт всегда. `sm:block` без `hidden` = виден всегда (display:block на ≥640px, но и на <640px тоже block, т.к. нет `hidden`). Правильно: `hidden sm:block` = скрыт <640px, block ≥640px.
- **jsdom не применяет Tailwind** — regression test проверяет наличие классов в DOM (`classList.contains`), а НЕ computed style. Это надёжно для ловли пропущенного `hidden`, но НЕ проверяет реальную видимость. Для полной проверки нужен Playwright E2E с real browser viewport.
- **CSS escape в `querySelectorAll`** — `sm:hidden` содержит двоеточие, в CSS selector нужно экранировать: `"div.space-y-3.sm\\:hidden"`. Biome требует двойные кавычки (не одинарные) для string literals.
- **`closest("div")` для table wrapper** — table непосредственный дочерний элемент div-обёртки, `tables[0].closest("div")` возвращает ближайший ancestor div (он же wrapper). Альтернатива `tables[0].parentElement` — то же самое, но `closest` безопаснее если wrapper получит nested structure.