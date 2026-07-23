---
adr: 96
title: Channels action menu + edit + is_active toggle
status: Accepted
date: 2026-07-23
pr: 96
issue: 95
---

# ADR PR#96 — Channels action menu + edit + is_active toggle

## Статус

Accepted

## Контекст

UX каналов в telesoft имел 3 проблемы (issue #95):

1. **2 клика до действия**: юзер кликал на название канала → переход на
   `/channels/[id]` → форма «Заменить ссылки» → запуск. Любое действие
   требовало минимум 2 клика (открытие детальной страницы + взаимодействие
   с формой). Для частой операции «заменить ссылки» это лишний friction.
2. **Нет редактирования канала**: если юзер ввёл неправильный `title` или
   `username` при создании, единственный путь — удалить канал и создать
   заново (что теряет историю задач в cascade-удалении `edit_jobs` +
   `edit_logs`). Backend `PATCH /api/channels/{id}` готов, но frontend
   формы редактирования не было.
3. **`is_active` — мёртвое поле**: показывалось как бейдж «активен»/
   «неактивен» в списке каналов, но изменить его из UI было нельзя.
   Деактивация канала (архивирование без удаления, с сохранением истории
   задач) была невозможна — только полное удаление.

Дополнительно: кнопка «Удалить» была standalone в каждой строке —
визуальный шум для редкой операции и не скалируется при добавлении
новых действий.

## Решение

**Action menu dropdown** на каждой карточке/строке канала (кнопка «⋯»):
- `ActionMenu.svelte` — переиспользуемый компонент с 4 пунктами:
  «Заменить ссылки», «Редактировать», «Деактивировать»/«Активировать»
  (toggle is_active), «Удалить».
- a11y: `role="menu"`, `aria-haspopup`, `aria-expanded`, `role="menuitem"`,
  Escape закрывает, click-outside закрывает, фокус управляется браузером.
- Кнопка «Удалить» переехала внутрь меню (с confirm dialog как было).

**Модалки для действий** (вместо отдельного маршрута):
- `ReplaceLinkModal.svelte` — обёртка над `ReplaceLinkForm` в модалке
  (`fixed inset-0 z-50 bg-black/60`, `role="dialog"`). `PreviewModal`
  рендерится поверх (два слоя модалок). On submit success — `goto("/jobs/{id}")`.
- `EditChannelModal.svelte` — обёртка над `ChannelForm` в edit-mode.

**Edit-mode в `ChannelForm.svelte`**:
- Новый опциональный prop `channel?: Channel` → предзаполнение title/username.
- `telegram_id` показан, но disabled (не редактируется после создания).
- Submit → `PATCH /api/channels/{id}` (через `updateChannel` helper).
- Заголовок «Редактировать канал» (edit) / «Новый канал» (create).

**`is_active` toggle**:
- `toggleChannelActive(id, active)` helper → `PATCH /api/channels/{id}`
  с `{ is_active: bool }`.
- В action menu: пункт «Деактивировать» (если active) / «Активировать»
  (если inactive).
- Неактивные каналы: `opacity-60` в списке, toggle «Показывать неактивные»
  для фильтрации.

**Backend `show_inactive` параметр**:
- `GET /api/channels?show_inactive=true` → все каналы (active + inactive).
- `GET /api/channels?show_inactive=false` → только активные.
- `active_only` параметр сохранён (backwards-compatible), `show_inactive` —
  alias с более интуитивной семантикой (True → показать inactive).

**Клик по названию канала** остаётся (переход на `/channels/[id]` для
истории задач) — два пути к одной цели (action menu + детальная страница).

## Альтернативы

- **Hub на детальной странице** (status quo): 2 клика до действия, нет
  редактирования, нет is_active toggle. Не решает issue #95.
- **Кнопки в каждой строке** (inline, без dropdown): «Заменить», «Изменить»,
  «Удалить» в строке таблицы — визуальный шум, не скалируется при добавлении
  новых действий (3+ кнопки в строке). На mobile — переполнение.
- **Отдельные маршруты** (`/channels/{id}/edit`, `/channels/{id}/replace`):
  больше кликов (переход + render), теряется контекст списка. URL-маршруты
  для модальных операций — избыточно.
- **Inline editing** (клик по полю → редактируется прямо в строке): сложно
  для multiple fields (title + username), плохой UX на mobile, нет
  валидации перед submit.
- **`PUT` вместо `PATCH`** для update: `PUT` требует все поля (включая
  `telegram_id`, который не должен меняться). `PATCH` — partial update,
  semantics соответствуют `ChannelUpdate` schema (all fields optional).
- **Убрать форму замены с детальной страницы**: issue #95 допускал, но
  оставлено для backwards-compat и двух путей к одной цели.