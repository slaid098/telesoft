---
adr: 94
title: Inline cancel button on jobs list
status: Accepted
date: 2026-07-23
pr: 94
issue: 93
---

# ADR PR#94 — Inline cancel button on jobs list

## Статус

Accepted

## Контекст

Кнопка отмены задачи была только на детальной странице `/jobs/{id}`
(`jobs/[id]/+page.svelte`) и показывалась только при `isStoppable`
(running/pending). На списке `/jobs` кнопки не было — только status badge.
Пользователь не находил кнопку отмены: чтобы отменить задачу, нужно открыть
детальную страницу каждой running/pending задачи. Backend endpoint
`POST /api/jobs/{id}/cancel` готов (возвращает 409 для terminal, иначе
`runner.cancel(job_id)` + `update_job_status(status="cancelled")`).

## Решение

Inline-кнопка «Отменить» в каждой строке таблицы (desktop, колонка
«Действия») и карточке (mobile) списка `/jobs` для running/pending задач.
Клик → `cancelJob(id)` helper (новый, в `api.ts`, переиспользуется списком
и детальной) → `refresh()`. 409 (terminal, race с WS/async) обрабатывается
тихо — `refresh()` обновляет список, задача уходит из stoppable визуально.
`isStoppable(status)` предикат вынесен отдельно для переиспользования в
desktop и mobile рендере. `cancelling = $state<number | null>` хранит id
задачи в процессе отмены — disable только конкретную кнопку если несколько
stoppable. Детальная страница рефакторится на `cancelJob` helper (поведение
не меняется, 409 НЕ обрабатывается специально — `cancelError` показывает
message).

## Альтернативы

- **Только на детальной странице** (status quo) — пользователь не находил
  кнопку, UX-блокер issue #93 не решается.
- **Disabled-кнопка для terminal статусов** (вместо скрытия) — визуальный
  шум, пользователь видит нерабочую кнопку для done/failed/cancelled задач.
- **Toast с undo** — отмена асинхронная (runner.cancel + DB update), undo
  не тривиален (нужно восстановить runner state). Избыточно для MVP.