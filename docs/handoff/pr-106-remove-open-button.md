---
pr: 106
issue: 105
branch: fix/channels/remove-open-button
status: ready
created: 2026-07-23
---

# Handoff — PR 106: remove redundant open button on mobile cards

## Что сделано

Реализован issue #105 — убрана кнопка «Открыть» с mobile-карточек
каналов. Она дублировала кликабельный заголовок-ссылку, который
остался и покрывает навигацию на страницу канала.

### Шаг 1: Удалён блок кнопки «Открыть»

- Файл: `web/src/routes/channels/+page.svelte` (строки ~188-194)
- Было: `<a href="/channels/{ch.id}" class="...bg-brand-600...">Открыть</a>`
  в `div.mt-3.flex.items-center.justify-between` рядом с `ActionMenu`.
- Стало: `<div class="mt-3 flex items-center justify-end gap-2">` —
  остался только `ActionMenu`, `justify-between` заменён на
  `justify-end` (ActionMenu прижат вправо, как в desktop-таблице).
- Кликабельный заголовок-ссылка (строки ~162-167) НЕ тронут —
  навигация на `/channels/{ch.id}` сохранилась.

### Шаг 2: Тесты

- Файл: `web/src/tests/channels.test.ts`
- Обновление НЕ потребовалось — ни один тест не ссылался на кнопку
  «Открыть» (assertions на текст «Открыть» или `role="link"` с этим
  label отсутствовали). 73 теста passed без изменений.

## Коммиты

1. `fix(channels): remove redundant open button on mobile cards` —
   шаг 1 (удаление `<a>Открыть</a>`, `justify-between`→`justify-end`).
2. `docs(handoff): set PR number` — заполнение `<PR-NUMBER>`
   placeholder после создания PR.

## Почему

Desktop и mobile должны быть идентичны по способу навигации. На
desktop клик по названию канала в таблице = переход на страницу
канала. На mobile было 2 способа: кликабельный заголовок + кнопка
«Открыть». Кнопка избыточна — заголовок-ссылка покрывает ту же
навигацию. Убрана для консистентности с desktop и упрощения UI.

## Pending

— (backend не затронут, чисто UI-изменение)

## Watch out

- **`justify-end` вместо `justify-between`** — без левой кнопки
  «Открыть» `justify-between` прижал бы `ActionMenu` влево. Заменено
  на `justify-end`, чтобы меню осталось справа (соответствует
  desktop-таблице, где «Действия» в правой колонке).

- **4 pre-existing svelte warnings** `state_referenced_locally` в
  `ChannelForm.svelte:15-16` и `jobs/[id]/+page.svelte:10-11` — НЕ
  связаны с этим PR (наследие PR #26/#96). Advisory, не error.