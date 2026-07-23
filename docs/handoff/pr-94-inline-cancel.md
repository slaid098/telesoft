---
pr: 94
issue: 93
branch: feat/jobs/inline-cancel
status: ready
created: 2026-07-23
---

# Handoff — PR 94: inline cancel button on jobs list

## Что сделано

Реализован issue #93 — inline-кнопка «Отменить» в списке задач `/jobs`
(desktop таблица + mobile карточки) для running/pending задач, плюс
переиспользуемый хелпер `cancelJob(id)`.

### Шаг 1: `cancelJob(id)` хелпер в `web/src/lib/api.ts`

- Добавлен `export async function cancelJob(id: number): Promise<void>`:
  `await api.post<void>('/api/jobs/${id}/cancel')`.
- Паттерн совпадает с другими хелперами (`previewReplace`, `replaceLink`,
  `listPatterns`, `createPattern`, `deletePattern`) — тонкая обёртка над
  `api.post` с типизированным возвращаемым значением.

### Шаг 2: Inline-кнопка в `web/src/routes/jobs/+page.svelte`

- Добавлены импорты `ApiError` и `cancelJob` из `$lib/api` (один import
  statement, отсортирован Biome).
- Добавлен state `cancelling = $state<number | null>(null)` — id задачи
  в процессе отмены (для `disabled` на кнопке, показывает «…»).
- Добавлена функция-предикат `isStoppable(status): boolean` —
  `status === "running" || status === "pending"`. Вынесена из инлайн-проверки
  для переиспользования в desktop и mobile рендере.
- Добавлена `async function handleCancel(jobId: number)`:
  - `cancelling = jobId` (disabled).
  - `await cancelJob(jobId)` → `await refresh()` (обновить список).
  - `catch (err)`: если `err instanceof ApiError && err.status === 409`
    (terminal, уже завершена) — молча `await refresh()` (список обновится,
    задача уйдёт из stoppable). Иначе — `error = err.message` (общая ошибка).
  - `finally`: `cancelling = null`.
- **Desktop таблица**: добавлена колонка «Действия» в header (`<th>`) и
  `<td>` в каждой строке с кнопкой при `isStoppable(job.status)`. Стиль:
  `rounded-md bg-red-700 px-2 py-1 text-xs font-medium text-white
  hover:bg-red-600 disabled:opacity-60`. Кнопка показывает «Отменить» или
  «…» (если `cancelling === job.id`). `colspan` в empty state увеличен с 6
  до 7.
- **Mobile карточки**: добавлена кнопка «Отменить» после блока `<dl>`
  (внутри `.space-y-3.sm:hidden` секции) при `isStoppable(job.status)`.
  Тот же стиль и поведение, что и в desktop.
- Для terminal статусов (done/failed/cancelled) кнопка не рендерится.

### Шаг 3: Рефакторинг детальной страницы `web/src/routes/jobs/[id]/+page.svelte`

- Импорт `cancelJob` из `$lib/api` (объединён с существующим `api` import).
- `handleCancel()` заменён: инлайн `api.post<{ job_id: number; status:
  string }>(...)` → `await cancelJob(job.id)`. Поведение не изменилось
  (`cancelling` state, `cancelError`, `refetchJob`).
- 409 на детальной НЕ обрабатывается специально — `cancelError` покажет
  message из `ApiError` (как и было до рефакторинга).

### Шаг 4: Тесты `web/src/tests/jobs.test.ts`

- В `vi.hoisted` добавлен `mockCancelJob = vi.fn()`. В `vi.mock("../lib/api",
  ...)` добавлен `cancelJob: mockCancelJob`. Импортированы `ApiError` и
  `cancelJob` из `../lib/api` (для использования в тестах).
- `beforeEach` сбрасывает `mockCancelJob.mockReset()`.
- Импортирован `cleanup` из `@testing-library/svelte` (для теста
  терминальных статусов с render/cleanup в цикле).
- Обновлён существующий тест детальной страницы: `calls POST
  /api/jobs/{id}/cancel when Cancel button is clicked` → `calls cancelJob
  when Cancel button is clicked on detail page`. Проверяет
  `expect(cancelJob).toHaveBeenCalledWith(1)` вместо `mockPost`.
- Добавлен `describe("Jobs list page — inline cancel button")` с 5 тестами:
  1. `renders Cancel button for running job` — 2 кнопки (desktop + mobile).
  2. `renders Cancel button for pending job` — 2 кнопки.
  3. `does not render Cancel button for terminal statuses` — для
     done/failed/cancelled: `queryAllByRole(...).length === 0`.
  4. `calls cancelJob and refresh when Cancel is clicked` — клик по
     первой кнопке → `cancelJob` вызван с id → `mockGet` вызван с
     `/api/jobs` (refresh).
  5. `handles 409 from cancelJob gracefully (refreshes, no crash)` —
     `mockCancelJob.mockRejectedValue(new ApiError(409, ...))` → клик →
     `cancelJob` вызван, `mockGet` вызван (refresh), нет текста
     «Не удалось отменить» (409 обработан тихо).

## Почему

Симптом из issue #93: пользователь не находил кнопку отмены задачи. Кнопка
«Отменить задачу» была только на детальной странице `/jobs/{id}`
(`jobs/[id]/+page.svelte:170`) и показывалась только при `isStoppable`
(running/pending). На списке `/jobs` кнопки не было — только status badge.

Пользователь хочет отменить задачу прямо из списка, не открывая каждую.
Backend `POST /api/jobs/{id}/cancel` готов (`api/routers/jobs.py:265-289`)
— возвращает 409 для terminal, иначе `runner.cancel(job_id)` +
`update_job_status(status="cancelled")`.

Решение: inline-кнопка в каждой строке таблицы (desktop) и карточке
(mobile) для running/pending задач. Клик → `cancelJob` → `refresh()`.
409 (уже terminal — race с WS/async) обрабатывается тихо (refresh
обновляет список, задача уйдёт из stoppable).

Хелпер `cancelJob(id)` вынесен в `api.ts` для переиспользования (список +
детальная) и консистентности с другими хелперами (`previewReplace`,
`replaceLink`).

## Pending

- Нет. Backend готов, frontend-часть завершает задачу.
- ADR не нужен (feature, но не архитектурное решение — переиспользование
  существующего endpoint + хелпер-обёртка).

## Watch out

- **`getByRole("button", { name: /Отменить/i })` находит 2 кнопки**: job
  рендерится и в desktop таблице (`hidden sm:block`), и в mobile карточках
  (`sm:hidden`). jsdom НЕ применяет Tailwind `sm:`/`hidden` breakpoints →
  оба layout видны в DOM → 2 кнопки с одинаковым текстом. В тестах
  использовать `getAllByRole(...)` + `.length` или `getAllByRole(...)[0]`
  для клика. НЕ `getByRole` (падает на множественном совпадении). Тот же
  паттерн, что и `getAllByText` для job id (PR#92).
- **`isStoppable` как функция, не inline**: вынесена отдельно для
  переиспользования в desktop и mobile рендере. НЕ `$derived` — зависит
  от `job.status` параметра, а не от state.
- **`cancelling = $state<number | null>`**: хранит id задачи в процессе
  отмены (не boolean) — позволяет disable только конкретную кнопку, если
  на странице несколько stoppable задач. `disabled={cancelling === job.id}`.
- **409 handling только в списке**: детальная страница НЕ обрабатывает 409
  специально — `cancelError` покажет message из `ApiError`. Это
  сознательно: на детальной странице пользователь видит подробную ошибку,
  в списке — тихий refresh (задача уже terminal, обновится визуально).
- **`vi.hoisted` для mockCancelJob**: `mockCancelJob` объявлен в
  `vi.hoisted` (как `mockGet`/`mockPost`), чтобы быть доступным в
  `vi.mock` factory (которая hoisted до импортов). НЕ обычный `vi.fn()` —
  будет `ReferenceError` в factory.
- **Pre-existing warnings**: `svelte-check` выдаёт 2
  `state_referenced_locally` warnings в `src/routes/jobs/[id]/+page.svelte`
  (строки 10-11) — НЕ связаны с этим PR, существуют до него. 0 errors.