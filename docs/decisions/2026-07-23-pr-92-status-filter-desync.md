---
adr: 92
title: Status filter desync — server-side filter as single source of truth
status: Accepted
date: 2026-07-23
pr: 92
issue: 91
---

# ADR PR#92 — Status filter desync

## Статус

Accepted

## Контекст

На странице задач (`web/src/routes/jobs/+page.svelte`) фильтрация по
статусу выполнялась в два слоя: client-side `filteredJobs` (через
`$derived` поверх текущей страницы из 20 задач) поверх server-side
пагинации через API. При смене фильтра статусов список «иногда пусто» —
client-side фильтр применялся к текущей странице (20 jobs), а пагинация
шла server-side. Рассинхрон: фильтр на странице 3 не находил running →
«нет задач», хотя они есть на странице 1. `total`/`totalPages` не
пересчитывались под фильтр при смене статуса.

## Решение

Убрать client-side `filteredJobs` — единый источник истины server-side
filter через API. `onchange` на `<select>` → `page = 1` (сброс на первую
страницу) + `refresh()` (server-side filter через `?status=...` query
param). `total`/`totalPages` пересчитываются из API (`count_jobs` с
`status` filter, готов с PR#84). Рендер таблицы/карточек использует
`jobs` напрямую (то, что приходит из API).

## Альтернативы

- Оставить client-side `filteredJobs`, но сбрасывать `page = 1` при
  смене фильтра — не решает рассинхрон `total`/`totalPages` с реальным
  числом задач под фильтром, дублирует server-side filter.
- Гибрид client+server с debounce — лишняя сложность, два источника
  истины остаются, рассинхрон не устраняется полностью.