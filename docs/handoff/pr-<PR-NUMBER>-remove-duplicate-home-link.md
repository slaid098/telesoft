---
pr: <PR-NUMBER>
issue: 79
branch: fix/web/remove-duplicate-home-link
status: ready
created: 2026-07-22
---

# Handoff — PR <PR-NUMBER>: remove duplicate Home link from top navigation

## Что сделано

Реализован issue #79 — убрано дублирование в шапке (wordmark «telesoft»,
пункт «Главная» и «Каналы» вели на одну страницу `/channels` через
редирект `/` → `/channels`).

### Шаг 1: Убран пункт «Главная» из navItems

- Файл: `web/src/routes/+layout.svelte`
- Из массива `navItems` удалён первый элемент
  `{ href: "/", label: "Главная", icon: "🏠" }`.
- Остались только «Каналы» (`/channels`) и «Задачи» (`/jobs`).

### Шаг 2: Wordmark «telesoft» кликабельный → /channels

- Файл: `web/src/routes/+layout.svelte`
- `<a href="/" class="text-lg font-semibold text-white">telesoft</a>` →
  `href="/channels"`.
- Wordmark берёт на себя роль «домой» (раньше вёл на `/`, который
  редиректит на `/channels` — теперь сразу на `/channels`, без
  лишнего редиректа).

### Шаг 3: Упрощён isActive хелпер

- Файл: `web/src/routes/+layout.svelte`
- Убрано строгое сравнение `item.href === "/" ? pathname === "/" : ...`
  (больше не нужно — нет пункта с `href: "/"`).
- Хелпер упрощён до одной строки:
  ```ts
  function isActive(item: NavItem): boolean {
    return page.url.pathname.startsWith(item.href);
  }
  ```
- Применяется и в desktop nav, и в mobile tab bar (как раньше).

### Шаг 4: Мобильский таб-бар grid-cols-3 → grid-cols-2

- Файл: `web/src/routes/+layout.svelte`
- `class="grid grid-cols-3 border-t ..."` → `class="grid grid-cols-2
  border-t ..."` (два пункта вместо трёх).

### Шаг 5: Тест layout.test.ts

- Файл: `web/src/tests/layout.test.ts`
- Обновление НЕ потребовалось — assertions ссылаются на «Каналы»
  (текст) и «Выйти» (кнопка), оба присутствуют в обновлённой навигации.
  Assertions на «Главная» или `grid-cols-3` отсутствовали.

## Коммиты

1. `fix(web): remove duplicate Home link from top navigation` — шаги
   1–4 (navItems, wordmark href, isActive, grid-cols-2).
2. `docs(handoff): set PR number` — заполнение `<PR-NUMBER>` placeholder
   после создания PR.

## Почему

Три ссылки в шапке (wordmark, «Главная», «Каналы») вели на одну
страницу — `/` редиректит на `/channels` через `web/src/routes/+page.ts`.
Wordmark «telesoft» выполняет роль «домой» сам по себе (кликабельный
логотип — стандартный UX-паттерн), отдельный пункт «Главная» дублировал
его и «Каналы». Убран «Главная» как наименее информативный (wordmark
виднее и всегда доступен). Wordmark теперь ведёт сразу на `/channels`
без промежуточного редиректа. `isActive` упрощён — строгое сравнение
для `/` больше не нужно (нет пункта с `href: "/"`).

## Pending

— (backend не затронут, чисто UI-изменение)

## Watch out

- **Wordmark ведёт на `/channels` напрямую** (не на `/`) — убран
  лишний редирект `/` → `/channels`. Семантически идентично: `/` всё
  равно редиректил на `/channels`. Если когда-нибудь `/` станет
  отдельной landing-страницей — wordmark можно будет вернуть на `/`.

- **`isActive` упрощён до `startsWith`** — строгое сравнение для `/`
  больше не нужно (убран единственный пункт с `href: "/"`). Все
  оставшиеся пункты (`/channels`, `/jobs`) используют `startsWith`
  (как и до PR #74). Хелпер оставлен (а не inline) — единая точка
  логики активного состояния для desktop nav и mobile tab bar.

- **Layout test (`layout.test.ts`) НЕ потребовал обновления** — mock
  `page.url.pathname` = `/channels`, assertions на «Каналы» и «Выйти»
  проходят. Assertions на «Главная» или `grid-cols-3` отсутствовали
  (см. PR #74 handoff, Watch out).

- **2 pre-existing svelte warnings** `state_referenced_locally` в
  `jobs/[id]/+page.svelte:10-11` — НЕ связаны с этим PR (наследие
  PR #26). Advisory, не error.