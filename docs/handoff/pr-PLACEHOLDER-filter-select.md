---
pr: PLACEHOLDER
issue: 99
branch: fix/channels/filter-select
status: ready
created: 2026-07-23
---

# Handoff — PR PLACEHOLDER: replace channels filter toggle with select dropdown

## Что сделано

Реализован issue #99 — переделка фильтра «Все каналы» / «Только
активные» на странице каналов (`web/src/routes/channels/+page.svelte`)
из toggle-кнопки в выпадающее меню `<select>` (по образцу
`jobs/+page.svelte:118-131` из PR#92) + скрытие select при открытии
формы «Добавить канал».

### Шаг 1: Состояние `channelFilter`

- `let showInactive = $state(false)` (строка 16) заменён на
  `let channelFilter = $state<"active" | "all">("active")`.
- Boolean `showInactive` уходит — фильтр теперь имеет строковое
  значение, соответствующее опциям select.

### Шаг 2: `<select>` вместо toggle-кнопки

- Toggle-кнопка (бывшие строки 74-84) заменена на `<select>`:
  ```svelte
  <div class="flex items-center gap-2">
    <label for="channel-filter" class="text-xs text-slate-400">Фильтр</label>
    <select id="channel-filter" bind:value={channelFilter}
      onchange={onFilterChange} class="...">
      <option value="active">Только активные</option>
      <option value="all">Все каналы</option>
    </select>
  </div>
  ```
- `bind:value={channelFilter}` + `onchange={onFilterChange}` —
  паттерн 1-в-1 как на /jobs (PR#92). Svelte 5 обновляет state ДО
  вызова `onchange`, поэтому `reload()` видит новое значение.

### Шаг 3: `onFilterChange()` вместо `toggleShowInactive()`

- `toggleShowInactive()` (бывшие строки 64-67) заменён на
  `onFilterChange()`:
  ```svelte
  async function onFilterChange() {
    await reload();
  }
  ```
- Конвертация `"active"|"all"` → `show_inactive: boolean` происходит
  в `reload()`, не в handler — единая точка для всех callers.

### Шаг 4: `reload()` — конвертация фильтра

- `listChannels(showInactive)` → `listChannels(channelFilter === "all")`.
- `"all"` → `true` (показывать неактивные), `"active"` → `false`
  (только активные). `+page.ts` (initial load) остаётся
  `listChannels(false)` — соответствует `channelFilter = "active"`.

### Шаг 5: Скрытие select при открытии формы

- Select обёрнут в `{#if !showForm}...{/if}` — при открытии формы
  «Добавить канал» select исчезает, остаётся только кнопка
  «Закрыть». Убирает визуальный шум и неоднозначность (toggle
  «Все каналы» над формой читался как навигация/отмена).

### Шаг 6: Тесты `web/src/tests/channels.test.ts`

- Добавлен `describe("Channels page — filter select")` с 5 тестами:
  1. `renders filter select with two options` — select рендерится,
     2 опции «Только активные» / «Все каналы».
  2. `calls listChannels with show_inactive=true when filter changes
     to 'all'` — `fireEvent.change` на select со value `"all"` →
     `mockGet` (mock для `listChannels`) вызван с `true`.
  3. `calls listChannels with show_inactive=false when filter changes
     back to 'active'` — последовательный `change` `"all"` →
     `"active"` → последний вызов `mockGet` = `false`.
  4. `hides filter select when Add channel form is open` — после
     клика «Добавить канал» `queryByLabelText(/Фильтр/i)` = null.
  5. `shows filter select again when Add channel form is closed` —
     после Cancel select снова виден.
- Существующих тестов на toggle-кнопку `showInactive` НЕ было
  (grep по `showInactive`/`toggleShowInactive`/`Все каналы` в
  `channels.test.ts` — 0 совпадений). Удалять нечего.
- `getByLabelText(/Фильтр/i)` находит `<select>` через
  `<label for="channel-filter">` (testing-library связывает по
  `for`/`id`) — паттерн из PR#92.

## Почему

Toggle-кнопка над формой добавления канала имела две проблемы:

1. **Неоднозначность**: текст «Все каналы» на кнопке над формой
   «Добавить канал» читался как навигация/отмена формы, а не как
   фильтр списка.
2. **Визуальный шум**: при открытии формы toggle оставался видимым
   и конкурировал за внимание с кнопкой «Закрыть».

Select однозначно читается как фильтр (особенно с `<label>Фильтр</label>`
и тем же паттерном, что на /jobs). Скрытие при форме убирает шум.

## Pending

- Нет. Backend `listChannels(showInactive?)` без изменений (передаёт
  boolean в `GET /api/channels?show_inactive=...`).
- `web/src/routes/channels/+page.ts` без изменений
  (`listChannels(false)` = initial = `"active"`).
- ADR не нужен (UI fix, архитектурных решений нет).

## Watch out

- **Svelte 5 `bind:value` + `onchange` ordering**: `bind:value`
  обновляет `channelFilter` ДО вызова `onchange` → в
  `onFilterChange()` `channelFilter` уже имеет новое значение, и
  `reload()` корректно передаёт `channelFilter === "all"` в
  `listChannels`. Та же семантика, что в PR#92 (jobs status filter).
- **`{#if !showForm}` обёртка**: select исчезает при открытии формы,
  но `channelFilter` state сохраняет значение — при закрытии формы
  select восстанавливается с прежним выбором. НЕ сбрасывается на
  `"active"`.
- **`getByLabelText(/Фильтр/i)` в тестах**: находит select через
  `<label for="channel-filter">`. Если на странице появится ещё один
  элемент с текстом «Фильтр» — уточнить regex или использовать
  `getByRole("combobox")` (но jsdom + Svelte могут не выставлять
  role корректно для custom-styled select).
- **`mockGet` = mock для `listChannels`**: в existing test setup
  (`vi.mock("../lib/api", ...)`) `listChannels: mockGet` — тот же
  mock перехватывает и `api.get`, и `listChannels`. Тесты filter
  используют `mockGet` для проверок вызова `listChannels(...)`.
- **Pre-existing warnings**: `svelte-check` выдаёт 4
  `state_referenced_locally` warnings в `ChannelForm.svelte` (2) и
  `jobs/[id]/+page.svelte` (2) — НЕ связаны с этим PR, существуют до
  него. 0 errors.