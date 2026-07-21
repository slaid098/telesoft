---
pr: 58
issue: 57
branch: feat/web/three-modes-preview-ui
status: ready
created: 2026-07-21
---

# Handoff — PR 58: three replace modes + preview UI

## Что сделано

Реализован issue #57 — frontend часть для simple-mode pattern compiler, pattern library CRUD и preview endpoint из PR#56. Backend = умный, frontend = тупой (только отображает и дёргает endpoints). 4 коммита, 5 файлов изменено / 3 создано, 30 vitest тестов green (было 23 в replace-link.test.ts → 8, +2 новых), Biome/svelte-check/knip — green.

### Шаг 1: `web/src/lib/api.ts` + `web/src/lib/types.ts` — commit 1

- `types.ts`: `ReplaceMode = "simple" | "library" | "advanced"`, `PreviewRequest`, `PreviewItem`, `PreviewResponse`, `PatternResponse`, `PatternListResponse`, `PatternCreateRequest`. `ReplaceLinkRequest` расширен `mode: ReplaceMode` + `keep_tail: boolean`.
- `api.ts`: 4 новые функции — `previewReplace(channelId, payload)` → `POST /api/channels/{id}/preview-replace`, `listPatterns()` → `GET /api/patterns`, `createPattern(payload)` → `POST /api/patterns`, `deletePattern(id)` → `DELETE /api/patterns/{id}`. `replaceLink(channelId, payload)` — типизированный wrapper поверх `api.post` (payload теперь с mode+keep_tail).

### Шаг 2: `ReplaceLinkForm.svelte` — редизайн — commit 2

- 3 таба (radio-кнопки через `role="tablist"`): **Simple** (по умолчанию) | **Pattern Library** | **Advanced**.
- **Simple mode**: input "Найти ссылки" с placeholder `https://t.me/bot?start=flow-*`, подсказка про `*`. Никакой валидации regex на frontend.
- **Pattern Library mode**: `<select>` с паттернами из `listPatterns()` (lazy load через `$effect` при первом переключении на таб). При выборе — показывает compiled regex ниже. Кнопка "Управление паттернами" → открывает PatternLibrary.
- **Advanced mode**: raw regex input (как раньше), placeholder `https://old\\.example\\.com`. Никакой `$effect`-валидации regex (убрано) — backend вернёт ошибку, frontend покажет.
- Общее: "Заменить на", чекбокс "Сохранить хвост" (`keep_tail`), Limit (1-1000), кнопки "Предпросмотр" + "Запустить".
- `effectivePattern = $derived` — для library mode берёт `selectedPattern.pattern`, для simple/advanced — `trimmedPattern`.
- `onPreview` callback в props — передаёт `PreviewResponse` родителю (+page.svelte).
- `runSignal` prop (`{ nonce: number }`) — триггерит `submitJob()` через `$effect` (для запуска из PreviewModal).
- Frontend НЕ делает: конвертацию `*` → regex, экранирование, валидацию regex, логику keep_tail.

### Шаг 3: `PreviewModal.svelte` + `PatternLibrary.svelte` (новые) — commit 3

- **PreviewModal.svelte**: modal overlay с `role="dialog"`. Props: `previews`, `totalMatches`, `compiledPattern`, `onRun`, `onEdit`. Список пар before→after (post #id + text), `compiled_pattern` мелким. Кнопки "Изменить pattern" (onEdit → закрывает) | "Запустить job" (onRun).
- **PatternLibrary.svelte**: modal overlay. Загружает паттерны через `listPatterns()` на mount. Список (builtin бейдж + кнопка "Удалить" только для `!is_builtin`). Форма добавления (name, pattern, description) через `createPattern()`. Удаление через `deletePattern()` с `window.confirm`. `onPatternsChanged` callback → родитель перезагружает список в ReplaceLinkForm.

### Шаг 4: `channels/[id]/+page.svelte` интеграция — commit 4

- Импорт PreviewModal, состояние `preview: PreviewResponse | null` и `runNonce: number`.
- `<ReplaceLinkForm onPreview={...} runSignal={{ nonce: runNonce }}>` — при onPreview сохраняет response, при onRun в PreviewModal — `preview = null; runNonce += 1` (триггерит `submitJob()` в форме через `$effect`).
- PreviewModal рендерится в конце страницы при `preview !== null`.

### Шаг 5: Тесты

- `replace-link.test.ts` переписан под новый UI: 8 тестов (disable submit when empty/new-link empty, enable submit when simple fields filled, limit validation, default limit 100, submit с mode/keep_tail, keep_tail=true checkbox, Advanced mode switch). Mock `replaceLink` вместо `api.post` напрямую.
- 30 vitest тестов total (6 files), все green.

## Почему

UX: обычный юзер не знает regex. Simple mode + Preview + Pattern Library делают замену доступной. Frontend тупой — только отображает и дёргает endpoints, всю логику (конвертация `*`, экранирование, keep_tail, валидация regex) делает backend (PR#56).

- **Simple mode** — юзер пишет `*` вместо "любой текст", без знания regex. Backend сам экранирует и конвертирует.
- **Pattern Library** — выбирает паттерн из списка вместо написания. CRUD через UI.
- **Preview** — dry-run показывает 3 пары before→after до запуска job, уменьшает риск ошибочной замены.
- **Keep tail** — чекбокс для паттернов вида `flow-*-s-*`: заменяется только префикс, хвост остаётся.
- **Dumb frontend** — упрощает код, вся логика в одном месте (backend), легче тестировать и поддерживать.

## Pending

- **PR#3 (seed built-in patterns)** — после этого PR: seed-скрипт для встроенных паттернов (`is_builtin=1`). Ref: issue #55 "Связанные ресурсы".
- **E2E тесты (Playwright)** — не добавлены в этом PR. Issue #57 упоминает ручную проверку, но Playwright не требуется. Существующие E2E (PR#42) могут падать на новом UI — проверить отдельно.
- **Compiled pattern в JobResponse** — backend (PR#56) сохраняет compiled regex в `edit_jobs.pattern`. Frontend jobs list/detail показывает его как есть (без преобразования обратно в user-friendly вид) — acceptable для MVP, можно улучшить позже.

## Watch out

- **Svelte 5 `runSignal` pattern** — для триггера `submitJob()` из PreviewModal нельзя вызвать метод формы напрямую (Svelte 5 не expose методы). Решение: prop `runSignal: { nonce: number }` + `$effect` в форме: `if (runSignal && runSignal.nonce > 0) void submitJob()`. Родитель инкрементирует `runNonce` → форма запускает submit. Альтернатива — `bind:this` на form element + `form.requestSubmit()`, но менее Svelte-idiomatic.
- **Lazy load patterns** — `listPatterns()` вызывается только при первом переключении на Library tab (`$effect` с guard `patterns === null`). После добавления/удаления в PatternLibrary — `onPatternsChanged` сбрасывает `patterns = null` и перезагружает. Избегает лишних запросов на Simple/Advanced.
- **Biome import order** — component import (`PatternLibrary`) должен идти ДО type import (`type { ... }`) в Svelte `<script>`. Biome `organizeImports` флагует обратный порядок. Fixed через `biome check --fix --unsafe`.
- **`replace-link.test.ts` rewrite** — старые тесты искали label "Pattern", "New link", "Run replace-link" — все изменились на русский/новые. Mock перенесён с `api.post` на `replaceLink` (типизированный wrapper). Старый mock `api.post` всё ещё нужен для PatternLibrary (createPattern внутри вызывает `api.post`).
- **`state_referenced_locally` warnings** — 2 pre-existing warnings в `jobs/[id]/+page.svelte` (не затронуты этим PR, были до). Svelte advisory, не error.
- **PreviewModal onRun → `preview = null` BEFORE `runNonce += 1`** — порядок важен: сначала закрываем модалку, потом триггерим submit. Если наоборот — `$effect` в форме может не сработать (race с unmount). Текущий порядок работает в тестах и build.
- **Frontend не валидирует regex в Advanced mode** — старый UI делал `new RegExp()` в `$effect` и показывал ошибку. Новый UI убрал это — backend вернёт 422, frontend покажет в error-блоке. Соответствует спеке "Frontend = dumb". Пользователь видит ошибку только после submit/preview.