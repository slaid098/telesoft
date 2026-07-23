---
adr: 90
pr: 90
issue: 89
status: Accepted
date: 2026-07-23
---

# ADR — PR #90: fix(jobs): mobile table duplication

## Статус

Accepted

## Контекст

На мобиле (<640px) таблица jobs дублировалась карточками — на 2 из 4 table wrappers в jobs-страницах (`jobs/+page.svelte`, `jobs/[id]/+page.svelte`) пропущён Tailwind-класс `hidden`. Это регрессия PR#38 (mobile responsive layout): PR#40 фиксил channels-страницы, jobs-страницы пропустил. Без `hidden` таблица видна на всех экранах, а cards (`sm:hidden`) видны на <640px → оба блока одновременно.

## Решение

Добавить `hidden` на 2 table wrappers (`jobs/+page.svelte:121`, `jobs/[id]/+page.svelte:201`) — паттерн `hidden sm:block` (скрыт <640px, block ≥640px). Добавить regression test в `web/src/tests/jobs.test.ts` — проверка `classList.contains("hidden")` и `classList.contains("sm:block")` через DOM (jsdom не применяет Tailwind, но классы в DOM присутствуют).

## Альтернативы

- **Только CSS media query вместо Tailwind responsive** — писать `@media (max-width: 640px) { .table-wrapper { display: none } }` вручную. Отвергнуто: проект уже на Tailwind, dual-layout паттерн (`hidden sm:block` / `sm:hidden`) консистентен по всем страницам.
- **Убрать dual-layout совсем** — оставить только таблицу или только карточки. Отвергнуто: UX-решение PR#38 (таблица на десктопе, карточки на мобиле) принято и работает на channels-страницах.