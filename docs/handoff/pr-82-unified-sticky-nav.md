---
pr: 82
issue: 81
branch: feat/web/unified-sticky-nav
status: ready
created: 2026-07-22
---

# Handoff — PR 82: unified sticky top navigation on all devices

## Что сделано

Реализован issue #81 — единая sticky-навигация в шапке на всех
устройствах (мобиле + десктопе), нижний таб-бар удалён.

### Шаг 1: Top nav всегда видим (убрано responsive скрытие)

- Файл: `web/src/routes/+layout.svelte`
- С `<nav>` убрано `hidden sm:flex` → `flex items-center gap-2` — nav
  виден на всех устройствах (мобиле + десктоп).
- `space-x-1` заменён на `gap-2` (flex+gap единообразно с остальной
  шапкой, в отличие от `space-x-*` для inline-потока).
- Tap targets адаптированы для touch на мобиле: `py-2` → `py-2.5`
  (крупнее область нажатия).
- `gap-6` на контейнере левой части шапки сужен до `gap-4` (wordmark +
  nav ближе друг к другу на узком экране мобилы).

### Шаг 2: Header сделан sticky

- Файл: `web/src/routes/+layout.svelte`
- К `<header>` добавлено `sticky top-0 z-50` — header приклеен к верху
  viewport'а, двигается вместе со скроллом страницы, всегда виден.
- Background остался непрозрачным `bg-slate-900` (как и был) — контент
  под sticky header не просвечивает.
- `shrink-0` сохранён — header не сжимается при переполнении контентом.

### Шаг 3: Удалён bottom tab bar

- Файл: `web/src/routes/+layout.svelte`
- Полностью удалён блок `<nav class="grid grid-cols-2 border-t
  border-slate-800 bg-slate-900 sm:hidden" aria-label="Мобильная
  навигация">` (нижний таб-бар для мобилы).
- `aria-label="Мобильная навигация"` удалён вместе с блоком (больше
  нигде не используется — см. grep по `web/src/`).

### Шаг 4: Адаптирован layout

- Файл: `web/src/routes/+layout.svelte`
- Контент `<main>` (`<div class="flex-1 overflow-y-auto p-4 sm:p-6">`)
  корректно скроллится под sticky header — `overflow-y-auto` + `flex-1`
  в flex-column контейнере обеспечивает скролл контента, header остаётся
  прикреплённым к верху.
- Отдельный padding-bottom для bottom bar отсутствовал (контент
  обрезался `overflow-y-auto`, а не `padding-bottom`) — убирать нечего.

### Шаг 5: Тест layout.test.ts

- Файл: `web/src/tests/layout.test.ts`
- Обновление НЕ потребовалось — assertions ссылаются на «Каналы»
  (текст, `getAllByText`) и «Выйти» (кнопка, `getByRole`), оба
  присутствуют в обновлённой навигации (top nav на всех устройствах).
  Assertions на `Мобильная навигация`, `grid-cols-2` или bottom tab bar
  отсутствовали (см. PR #74 handoff, Watch out; PR #80 handoff,
  Watch out).
- `screen.getAllByText("Каналы")` использует `getAllByText` — раньше
  «Каналы» рендерился в двух местах (top nav desktop + mobile tab bar),
  сейчас только в top nav (один элемент). `>=1` assertion проходит.

## Коммиты

1. `feat(web): unified sticky top nav on all devices` — шаги 1–4
   (`hidden sm:flex` → `flex gap-2`, `py-2.5` tap targets, header
   `sticky top-0 z-50`, bottom tab bar удалён, layout адаптирован).
2. `docs(handoff): set PR number` — заполнение `<PR-NUMBER>` placeholder
   после создания PR.

## Почему

Bottom tab bar неудобен: на странице с большим количеством задач
(например, 100 записей) для переключения на «Каналы» нужно скроллить
в самый низ страницы. Sticky header всегда виден — переключение
доступно мгновенно из любого места страницы, без скролла.

Единая навигация (top nav на всех устройствах) упрощает код: одна
разметка вместо двух (desktop top nav + mobile bottom tab bar), одно
место логики активного состояния (`isActive` хелпер использовался в
обоих местах, теперь только в top nav).

## Pending

— (backend не затронут, чисто UI-изменение)

## Watch out

- **Header `sticky top-0 z-50`** — sticky (не `fixed`): header
  занимает место в normal flow, контент `<main>` естественно идёт под
  ним (отдельный `padding-top` НЕ нужен, в отличие от `fixed`).
  `z-50` поднимает header над контентом при скролле (контент уходит
  «под» header, а не перекрывает его). `bg-slate-900` непрозрачный —
  контент не просвечивает сквозь header.

- **Top nav всегда видим (нет `hidden sm:flex`)** — nav из двух пунктов
  («Каналы», «Задачи») на мобиле помещается в шапку рядом с wordmark и
  кнопкой «Выйти» (узкие пункты, `gap-2`). Если пунктов станет больше —
  может потребоваться hamburger menu или overflow (но для текущих двух
  пунктов top nav достаточно).

- **Tap targets `py-2.5`** — увеличены с `py-2` для удобства touch на
  мобиле (рекомендация WCAG 2.5.5 — minimum 44×44px target). `px-3`
  сохранён (горизонтальный padding не влияет на touch-comfort для
  горизонтального nav).

- **`gap-2` вместо `space-x-1`** — flex+gap единообразно с остальной
  шапкой (контейнеры используют `gap-*`). `space-x-*` работает через
  margin на inline-потоке, менее предсказуемо с flex-wrap. `gap` —
  свойство flex/grid контейнера.

- **`getAllByText("Каналы")` в тесте** — раньше «Каналы» рендерился в
  двух местах (desktop top nav + mobile tab bar), assertion `>=1`
  покрывал оба. Сейчас один top nav — `getAllByText` возвращает массив
  длины 1, `>=1` проходит. Можно заменить на `getByText` (один
  элемент), но `getAllByText` + `>=1` более устойчив к будущим
  изменениям (добавление ещё одного места с «Каналы» не сломает тест).

- **Layout test НЕ потребовал обновления** — assertions на «Каналы» и
  «Выйти» проходят; assertions на `Мобильная навигация`, `grid-cols-2`
  или bottom tab bar отсутствовали (см. PR #74, PR #80 handoffs).

- **2 pre-existing svelte warnings** `state_referenced_locally` в
  `jobs/[id]/+page.svelte:10-11` — НЕ связаны с этим PR (наследие
  PR #26). Advisory, не error.

## Проверка

```bash
cd web && npm run lint        # Biome: 41 files, no fixes
cd web && npm run typecheck   # svelte-check: 0 errors, 2 warnings (pre-existing)
cd web && npm run test        # vitest: 37 tests, 6 files — all green
```

Все проверки пройдены.