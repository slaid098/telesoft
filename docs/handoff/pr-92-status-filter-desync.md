---
pr: 92
issue: 91
branch: fix/jobs/status-filter-desync
status: ready
created: 2026-07-23
---

# Handoff — PR 92: status filter desync causes empty list

## Что сделано

Реализован issue #91 — фикс рассинхронизации client-side и server-side
фильтра статусов на странице задач (`web/src/routes/jobs/+page.svelte`).

### Шаг 1: Убран client-side `filteredJobs`

- Удалён `$derived` `filteredJobs = statusFilter === "all" ? jobs :
  jobs.filter(...)` (бывшие строки 23-25).
- В рендере таблицы (desktop) и карточек (mobile) `filteredJobs`
  заменён на `jobs` — рендерится напрямую то, что приходит из API
  (`localRefresh ?? data.jobs`).
- Фильтрация теперь только server-side через `?status=...` query param.

### Шаг 2: `onchange` handler на `<select>`

- Добавлена функция `onStatusFilterChange()`: `page = 1` (сброс на
  первую страницу) + `await refresh()` (server-side filter через API).
- На `<select id="job-status-filter">` добавлен `onchange={onStatusFilterChange}`.
- `bind:value={statusFilter}` остался — Svelte 5 корректно обновляет
  state ДО вызова `onchange`, поэтому `refresh()` видит новое значение
  `statusFilter`.

### Шаг 3: `refresh()` — без изменений

- `refresh()` уже корректно передавал `status` query param (PR#84):
  `if (statusFilter !== "all") query.status = statusFilter;`.
- При `statusFilter === "all"` — `status` НЕ передаётся в API (получаем
  все задачи).
- `localTotal` обновляется из `resp.total` → `total`/`totalPages`
  пересчитываются автоматически (backend `count_jobs` с `status` filter
  уже готов из PR#84).

### Шаг 4: Тесты `web/src/tests/jobs.test.ts`

- Добавлен `describe("Jobs list page — server-side status filter")` с
  3 тестами:
  1. `does not send status query param when filter is 'all'` —
     `fireEvent.change` на select со value `"all"` → последний вызов
     `mockGet` не содержит `status` в query.
  2. `resets to page 1 and sends status query param when filter changes` —
     сначала `goToPage(2)` (offset=20), затем `change` на `"running"` →
     последний вызов `mockGet` = `{ limit: 20, offset: 0, status:
     "running" }` (page сброшен на 1).
  3. `renders jobs from API response directly (no client-side filter)` —
     после `change` на `"running"` рендерятся jobs из mock API ответа
     (`#100`, `#101`), не client-side отфильтрованный subset.
- Существующие тесты на pagination и dual-layout не изменялись
  (client-side `filteredJobs` тестов не было — только pagination и
  layout regression для #89).
- `getAllByText` вместо `getByText` для `#100`/`#101` — job id
  рендерится и в table (desktop), и в cards (mobile), jsdom не
  применяет `sm:` breakpoints → оба layout видны → множественное
  совпадение.

## Почему

Симптом от пользователя: при переключении фильтра статусов задач
(Ожидает/Выполняется/Готово/Ошибка) список «иногда пусто». После reload
страницы — нормально. При последовательном щелкании статусов — опять
пусто. Поведение нестабильно, зависит от порядка.

Корень проблемы (описано в issue #91, обнаружено в PR#84 TODO):
- `filteredJobs` = client-side фильтр применялся к текущей странице
  (20 jobs на странице).
- `bind:value={statusFilter}` на `<select>` НЕ имел `onchange` handler
  и НЕ имел `$effect` на `statusFilter` → при смене фильтра `refresh()`
  не вызывался, `page` не сбрасывался.
- `refresh()` передавал `status` в API только при пагинации
  (`goToPage`), не при смене фильтра.
- `total`/`totalPages` не пересчитывались под фильтр при смене статуса.

Сценарий бага: юзер на странице 3 (offset=40). Меняет фильтр на
«Выполняется». `filteredJobs` фильтрует 20 задач на странице 3 → если
среди них нет running, показывает «Нет задач» (хотя running есть на
странице 1). При клике «След.» → `goToPage(4)` → `refresh()` →
`status=running` уходит в API → server-side фильтр → рассогласование с
предыдущим client-side результатом.

Фикс: единый источник истины — server-side filter через API. Смена
фильтра → `page = 1` + `refresh()` → API возвращает отфильтрованный
slice + пересчитанный `total` → пагинация и список консистентны.

## Pending

- Нет. Backend `count_jobs` с `status` filter готов с PR#84 —
  frontend-фикс завершает задачу.
- ADR не нужен (bugfix, архитектурных решений нет).

## Watch out

- **Svelte 5 `bind:value` + `onchange` ordering**: `bind:value`
  обновляет state ДО вызова `onchange` handler — поэтому в
  `onStatusFilterChange()` `statusFilter` уже имеет новое значение, и
  `refresh()` корректно передаёт его в API. НЕ использовать `$effect` на
  `statusFilter` вместо `onchange` — `$effect` сработает и при
  programmatically-установленном значении (если такое появится), что
  может вызвать лишний `refresh()`. `onchange` срабатывает только на
  user interaction.
- **`refresh()` НЕ сбрасывает `page` сам** — это ответственность caller.
  `onStatusFilterChange` сбрасывает `page = 1` перед `refresh()`;
  `goToPage` устанавливает `page = next` перед `refresh()`. Polling
  (`$effect` + `setInterval`) НЕ сбрасывает `page` — обновляет текущую
  страницу. Если в будущем появится другой caller `refresh()` —
  убедиться что `page` установлен корректно ДО вызова.
- **`getByLabelText(/Статус/i)`** в тестах находит `<select>` через
  `<label for="job-status-filter">` (testing-library связывает по
  `for`/`id`). НЕ `getByRole("combobox")` — несколько combobox'ов могут
  быть на странице.
- **`getAllByText` для job id в tests**: job id рендерится в двух
  местах (table для desktop, cards для mobile). jsdom НЕ применяет
  Tailwind `sm:`/`hidden` breakpoints → оба layout видны в DOM →
  `getByText` падает на множественном совпадении. Использовать
  `getAllByText(...).length > 0` или `queryAllByText`.
- **Pre-existing warnings**: `svelte-check` выдаёт 2
  `state_referenced_locally` warnings в `src/routes/jobs/[id]/+page.svelte`
  (строки 10-11) — НЕ связаны с этим PR, существуют до него. 0 errors.