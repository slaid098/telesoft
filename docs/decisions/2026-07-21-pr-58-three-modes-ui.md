---
pr: 58
issue: 57
status: Accepted
created: 2026-07-21
---

# ADR — PR 58: three replace modes + preview UI

## Статус

Accepted (2026-07-21). Реализует issue #57 (frontend часть). Backend (PR#56) — merged. Seed built-in patterns (PR#3) — отдельно, согласно плану в issue #55.

## Контекст

PR#56 (merged) добавил backend: pattern compiler (simple mode `*` → `.*`), preview endpoint, pattern library DB + CRUD. `ReplaceLinkRequest` принимает `mode` (simple|library|advanced) и `keep_tail` (bool). Но frontend оставался старым — один raw regex input с frontend-валидацией regex. Обычный юзер не знает regex и не может составить паттерн.

Нужно сделать **тупой frontend** (dumb client): только отображает и дёргает endpoints. Всю логику (конвертация `*`, экранирование, keep_tail, валидация regex) делает backend. Frontend = UI с 3 режимами + превью модалкой + CRUD для pattern library.

Это PR#2 из 3. PR#3 (seed built-in patterns) — отдельно.

## Решение

**5 изменений (4 коммита):**

1. **`web/src/lib/api.ts` + `web/src/lib/types.ts`** — 4 новых API-функции (`previewReplace`, `listPatterns`, `createPattern`, `deletePattern`) + типизированный `replaceLink` wrapper. Новые типы: `ReplaceMode`, `PreviewRequest/Item/Response`, `PatternResponse/ListResponse/CreateRequest`. `ReplaceLinkRequest` расширен `mode` + `keep_tail`.

2. **`ReplaceLinkForm.svelte` — редизайн** — 3 таба (Simple/Library/Advanced) через `role="tablist"`. Simple mode: input с placeholder `https://t.me/bot?start=flow-*` и подсказкой про `*`. Library mode: `<select>` из `listPatterns()` + кнопка "Управление паттернами". Advanced mode: raw regex input. Общее: "Заменить на", keep_tail checkbox, Limit, "Предпросмотр" + "Запустить". `effectivePattern = $derived` для library (берёт `selectedPattern.pattern`) vs simple/advanced (берёт `trimmedPattern`). Frontend НЕ валидирует regex (убран `$effect` с `new RegExp`).

3. **`PreviewModal.svelte` (новый)** — modal с `role="dialog"`. Список пар before→after (post #id + text), `compiled_pattern` мелким. Кнопки "Изменить pattern" (onEdit) | "Запустить job" (onRun).

4. **`PatternLibrary.svelte` (новый)** — modal с CRUD. Загрузка `listPatterns()` на mount, форма добавления (name, pattern, description) через `createPattern()`, удаление (`!is_builtin` только) через `deletePattern()` с `window.confirm`. `onPatternsChanged` callback → родитель перезагружает.

5. **`channels/[id]/+page.svelte` интеграция** — состояние `preview` + `runNonce`. `<ReplaceLinkForm onPreview runSignal>`. PreviewModal рендерится при `preview !== null`. onRun → `preview = null; runNonce += 1` (триггерит submit в форме через `$effect`).

## Альтернативы

1. **`runSignal` pattern vs `bind:this` на form** — для триггера submit из PreviewModal. `runSignal: { nonce: number }` + `$effect` в форме vs `bind:this={formEl}` + `formEl.requestSubmit()` в onRun. Плюс `runSignal`: декларативный, Svelte-idiomatic (reacts to prop change). Минус: extra state. Принят `runSignal` — декларативный, работает с Svelte 5 reactivity.

2. **Frontend regex validation vs backend-only** — старый UI делал `new RegExp()` в `$effect` и показывал ошибку live. Новый UI убрал это — backend возвращает 422, frontend показывает в error-блоке после submit/preview. Плюс backend-only: less code, single source of truth (backend уже валидирует), соответствует "dumb frontend". Минус: пользователь видит ошибку позже (после submit, не live). Принят backend-only — соответствует спеке issue #57.

3. **Tabs как radio buttons vs `<select>` vs buttons** — 3 режима. `role="tablist"` + кнопки с `aria-selected` vs `<input type="radio">` vs `<select>`. Плюс tabs: визуально понятно, mobile-friendly. Принят tabs — UX лучше для 3 режимов, accessible.

4. **PatternLibrary как separate component vs inline в ReplaceLinkForm** — отдельный `.svelte` файл vs встроенный блок. Плюс separate: переиспользуем, тестируем изолированно. Принят separate — single responsibility.

5. **Lazy load patterns vs eager load** — `listPatterns()` при первом переключении на Library tab (`$effect` с guard) vs на mount. Плюс lazy: не дёргает API для Simple/Advanced users. Минус: extra latency при первом открытии Library. Принят lazy — большинство юзеров используют Simple mode.

6. **Russian labels vs English** — UI на русском (Найти ссылки, Заменить на, Сохранить хвост, Предпросмотр, Запустить). Плюс: целевая аудитория — русскоязычные. Минус: не i18n. Принят русский — MVP, single language, соответствует остальному UI (который смешанный, но user-facing текст на русском).

7. **PreviewModal показывает compiled_pattern vs hide** — показывает `compiled_pattern` мелким шрифтом внизу. Плюс: transparency (юзер видит во что превратился его `*`), debug. Минус: может смутить новичка. Принят show — transparency важнее, мелким шрифтом + можно проигнорировать.

## Последствия

- Frontend теперь "тупой" — вся логика замены (конвертация, экранирование, keep_tail, валидация) в backend. Меньше кода на frontend, проще поддерживать.
- `ReplaceLinkForm` обратно несовместим с старым API (требует `mode` + `keep_tail` в payload). Но backend (PR#56) имеет defaults (`mode="advanced"`, `keep_tail=false`) — старые клиенты работают. Frontend всегда шлёт явные значения.
- Pattern Library UI готов к PR#3 (seed built-in patterns) — `is_builtin` бейдж и запрет удаления уже реализованы.
- PreviewModal — dry-run без edit в Telegram (backend `preview_replace` pure function). Безопасно для частых вызовов.
- `replace-link.test.ts` переписан (8 тестов вместо 6) — старые тесты не работают с новым UI. Mock `replaceLink` вместо `api.post`.
- E2E тесты (PR#42) могут падать на новом UI — нужно проверить и обновить отдельно (не в этом PR).
- ADR pointer: ADR принят для three replace modes + preview UI → `docs/decisions/2026-07-21-pr-58-three-modes-ui.md` (альтернативы: `runSignal` vs `bind:this`, frontend regex validation vs backend-only, tabs vs radio vs select, PatternLibrary separate vs inline, lazy vs eager load, Russian vs English labels, show vs hide compiled_pattern).