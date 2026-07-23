---
adr: 104
title: Show username on all devices
status: Accepted
date: 2026-07-23
pr: 104
issue: 103
---

# ADR PR#104 — Show username on all devices

## Статус

Accepted

## Контекст

Username «Вы вошли как admin» в top nav bar был скрыт на mobile через
Tailwind-классы `hidden sm:block` — span отображался только на экранах
≥640px (`sm` breakpoint). На mobile юзер видел кнопку «Выйти», но не
видел, под каким аккаунтом он вошёл, — нет контекста для действия
выхода.

## Решение

Убрать `hidden sm:block` с username span в
`web/src/routes/+layout.svelte`. Span виден на всех breakpoints.
Добавлен `whitespace-nowrap` — предотвращает перенос «Вы вошли как
admin» на две строки на узких экранах.

## Альтернативы

- **Оставить скрытым** (status quo): username невидим на mobile —
  issue #103 не закрыт, UX-проблема сохраняется.
- **Показывать только на >md** (`hidden md:block`): сдвиг breakpoint
  с `sm` (640px) на `md` (768px) не решает проблему — на экранах
  640–768px username всё ещё скрыт, а это популярный диапазон
  мобильных устройств.