---
pr: 76
issue: 75
branch: feat/web/preview-checkbox-off
status: ready
created: 2026-07-22
---

# Handoff — PR 76: preview checkbox off by default

## Что сделано

Реализован issue #75 — кнопка «Предпросмотр» стала опциональной (по
умолчанию выключена) в `web/src/lib/components/ReplaceLinkForm.svelte`.

### Шаг 1: Добавлен state `showPreview`

- `let showPreview = $state(false)` — по умолчанию выкл (предпросмотр
  скрыт при первичном рендере).

### Шаг 2: Чекбокс «Показать предпросмотр»

- Добавлен в блоке кнопок (`flex items-center justify-end gap-2`),
  перед кнопками. Ненавязчивый, использует существующие Tailwind-классы
  (`flex items-center gap-2 text-sm text-slate-300`, чекбокс
  `border-slate-700 bg-slate-800`).
- `bind:checked={showPreview}` — Svelte 5 two-way binding.

### Шаг 3: Условная видимость кнопки «Предпросмотр»

- Кнопка обёрнута в `{#if showPreview}` — рендерится ТОЛЬКО когда
  чекбокс включён.
- Кнопка «Запустить» (submit) — всегда видна, вне `{#if}`.

## Коммиты

1. `feat(web): add preview checkbox off by default` — шаги 1–3 (state,
   чекбокс, условная видимость), обновлён тест
   `replace-link.test.ts` (preview-кнопка появляется после клика на
   чекбокс).
2. `docs(handoff): set PR number` — заполнение `<PR-NUMBER>` placeholder
   после создания PR.

## Почему

Пользователь сказал, что предпросмотр «портит весь вид» — кнопка всегда
была видна рядом с «Запустить». Чекбокс делает предпросмотр опциональным:
по умолчанию выкл, включается одним кликом, не занимает место. Кнопка
«Запустить» остаётся всегда доступной.

## Pending

— (backend не затронут, чисто UI-изменение)

## Watch out

- **Тест `replace-link.test.ts` обновлён** — assertion «preview button
  calls previewReplace and opens modal» теперь сначала кликает чекбокс
  «Показать предпросмотр» (`screen.getByLabelText(/Показать предпросмотр/i)`),
  затем `screen.getByRole("button", { name: /Предпросмотр/i })`. Без
  клика на чекбокс кнопка предпросмотра НЕ рендерится → тест упал бы на
  `getByRole` (элемент не найден).

- **`canSubmit` не учитывает `showPreview`** — `showPreview` влияет только
  на видимость кнопки, не на валидность формы. Кнопка «Предпросмотр»
  наследует `disabled={!canSubmit}` (как и «Запустить»).

- **Чекбокс размещён в строке кнопок** (`flex items-center justify-end
  gap-2`) — визуально: чекбокс-метка слева, затем (опц.) «Предпросмотр»,
  затем «Запустить». `justify-end` прижимает всю группу вправо.

- **2 pre-existing svelte warnings**
  `state_referenced_locally` в `jobs/[id]/+page.svelte:10-11` — НЕ связаны
  с этим PR (наследие PR#26). Advisory, не error.