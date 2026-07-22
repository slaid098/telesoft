---
pr: <PR-NUMBER>
issue: 73
branch: feat/web/top-navigation
status: ready
created: 2026-07-22
---

# Handoff — PR <PR-NUMBER>: replace sidebar with top navigation bar

## Что сделано

Реализован issue #73 — замена левого сайдбара на верхнюю навигационную
панель в `web/src/routes/+layout.svelte`.

### Шаг 1: Убрать левый сайдбар

- Удалён `<aside>` (ширина `w-60`, nav + footer «Вы вошли как» + «Выйти»).
- Контейнер `flex h-full min-h-screen flex-col sm:flex-row` упрощён до
  `flex h-full min-h-screen flex-col` — layout стал одноколоночным
  (sidebar больше не нужен).

### Шаг 2: Превратить `<header>` в верхний навбар

Header (`h-14`) теперь горизонтальная строка:
- **Слева**: wordmark «telesoft» (кликабельный `<a href="/">`), затем
  горизонтальный `<nav class="hidden space-x-1 sm:flex">` со ссылками
  (Каналы, Задачи — на desktop sm+).
- **Справа**: «Вы вошли как {username}» (`hidden sm:block`) + кнопка «Выйти»
  (перенесена из сайдбара).

### Шаг 3: Активное состояние

Хелпер `isActive(item)` в `<script>`:
```ts
function isActive(item: NavItem): boolean {
  const pathname = page.url.pathname;
  return item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
}
```
- Для «Главная» (`href: "/"`) — строгое `pathname === "/"` (иначе
  `startsWith("/")` сработает на всех страницах).
- Для «Каналы» и «Задачи» — `pathname.startsWith(item.href)` (как было).
Применяется и в desktop nav, и в mobile tab bar.

### Шаг 4: Мобильская навигация

Нижний таб-бар `grid grid-cols-2` → `grid grid-cols-3` (три пункта:
Главная, Каналы, Задачи). Активное состояние — через тот же `isActive`.

### Шаг 5: Сохранить login guard

`{#if isLogin}{@render children()}{:else}...` — login-страница рендерится
без оболочки (как раньше). Guard не тронут.

## Коммиты

1. `feat(web): replace sidebar with top navigation bar` — шаги 1–2, 5
   (sidebar удалён, header превращён в навбар, login guard сохранён).
   navItems содержал 2 пункта (Каналы, Задачи), mobile tab bar —
   `grid-cols-2`, активное состояние через `startsWith`.
2. `feat(web): add Home link to mobile tab bar` — шаги 3–4 (добавлен
   «Главная» в navItems, `isActive` хелпер со строгим сравнением для `/`,
   mobile `grid-cols-3`).
3. `docs(handoff): set PR number` — после создания PR (заполнение
   `<PR-NUMBER>` placeholder).

## Почему

Сайдбал занимал место на desktop и дублировал навигацию с mobile tab bar.
Верхняя навигация удобнее для пользователя: едиственное место навигации
на desktop (header), нижний таб-бар на mobile. Кнопка «Главная» добавлена
для быстрого возврата к корню приложения (`/` редиректит на `/channels`
через `web/src/routes/+page.ts`, поэтому «Главная» и «Каналы» ведут на
одну страницу — это ок, оставлено как есть).

## Pending

— (backend не затронут, чисто UI-изменение)

## Watch out

- **`isActive` хелпер обязателен для "/"** — без строгого сравнения
  `pathname.startsWith("/")` вернёт `true` на всех страницах, и «Главная»
  будет подсвечена всегда. Хелпер инкапсулирует это правило в одном месте
  (используется и desktop nav, и mobile tab bar).

- **Layout test (`layout.test.ts`) НЕ потребовал обновления** — assertions
  ссылаются на «Каналы» (текст) и «Выйти» (кнопка), оба присутствуют в
  новом top-nav. Sidebar-специфичные assertions отсутствовали. Mock
  `page.url.pathname` = `/channels` → `isActive("/" )` = false (строгое),
  «Главная» НЕ подсвечена — корректно.

- **`/` редиректит на `/channels`** — «Главная» и «Каналы» ведут на одну
  страницу (`+page.ts` root делает `redirect(307, "/channels")`). Это
  намеренно оставлено (см. контекст issue #73). «Главная» полезна как
  «домой» семантически и для быстрого возврата.

- **2 pre-existing svelte warnings** `state_referenced_locally` в
  `jobs/[id]/+page.svelte:10-11` — НЕ связаны с этим PR (наследие PR#26).
  Advisory, не error.