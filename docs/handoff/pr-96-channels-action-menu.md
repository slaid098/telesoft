---
pr: 96
issue: 95
branch: feat/channels/action-menu
status: ready
created: 2026-07-23
---

# Handoff — PR 96: channels action menu + edit + is_active toggle

## Что сделано

Реализован issue #95 — action menu (dropdown «⋯») на карточке/строке канала с
пунктами «Заменить ссылки», «Редактировать», «Деактивировать»/«Активировать»,
«Удалить», плюс edit-mode для `ChannelForm`, `is_active` toggle и
`show_inactive` параметр на бэке.

### Шаг 1: Backend `show_inactive` параметр

- `src/telesoft/api/routers/channels.py` — `list_channels_endpoint` получил
  опциональный `show_inactive: bool | None = None` (alias для `active_only`):
  `show_inactive=True` → все каналы, `show_inactive=False` → только активные,
  `None` (default) → управляется `active_only` (backwards-compatible).
  Существующий `active_only` параметр НЕ удалён — оба работают.
- `tests/test_api_channels.py` — 2 новых теста:
  `test_list_channels_show_inactive_true_returns_inactive` и
  `test_list_channels_show_inactive_false_excludes_inactive`.
- **Важно**: бэкенд уже возвращал inactive каналы по умолчанию (`active_only=False`),
  т.е. существующая `list_channels` показывала ВСЕ каналы. Issue спека
  предполагала `WHERE is_active = 1` (устаревшее описание — код эволюционировал).
  Это исправлено в коммите `feat(api): add show_inactive param to list_channels`.

### Шаг 2: `ActionMenu.svelte` (новый компонент)

- `web/src/lib/components/ActionMenu.svelte` — dropdown с кнопкой «⋯»:
  - Props: `channel: Channel`, `onReplace`, `onEdit`, `onToggleActive`, `onDelete`.
  - Пункты: «Заменить ссылки», «Редактировать», «Деактивировать»/«Активировать»
    (label зависит от `channel.is_active`), разделитель, «Удалить» (красный).
  - a11y: `role="menu"`, `aria-haspopup="menu"`, `aria-expanded`, `role="menuitem"`
    на каждом пункте, `role="separator"` перед «Удалить».
  - Закрытие: Escape (keydown listener), click-outside (click listener на
    `document`, проверка `container.contains(event.target)`), после выбора
    пункта (`run()` вызывает `close()` + callback).
  - `$effect` для подписки/отписки listeners (зависит от `open`).

### Шаг 3: `ReplaceLinkModal.svelte` (новый компонент)

- `web/src/lib/components/ReplaceLinkModal.svelte` — модалка-обёртка:
  - `fixed inset-0 z-50 bg-black/60`, `role="dialog"`, `aria-modal="true"`.
  - Внутри `<ReplaceLinkForm channelId={channelId} />` (переиспользуется as-is).
  - Кнопка «×» в углу, Escape закрывает (когда PreviewModal не открыт).
  - `PreviewModal` рендерится поверх (внутри `ReplaceLinkModal`, отдельный
    `z-50` overlay) — два слоя модалок работают.
  - Заголовок «Замена ссылок в канале» (НЕ «Замена ссылки» — конфликт с
    `ReplaceLinkForm`'s `<h2>Замена ссылки</h2>`, тест падал на multiple match).

### Шаг 4: `EditChannelModal.svelte` (новый компонент)

- `web/src/lib/components/EditChannelModal.svelte` — модалка-обёртка для
  `ChannelForm` в edit-mode. Передаёт `channel` prop, `onSaved`, `onClose`.
  Escape закрывает.

### Шаг 5: `ChannelForm.svelte` — edit-mode

- Новый опциональный prop `channel?: Channel` → edit-mode.
- Предзаполнение: `title = channel.title`, `username = channel.username`.
- `telegram_id` показан, но `disabled` (с серым стилем, курсор `not-allowed`).
- Submit: edit → `updateChannel(id, payload)` (PATCH), create → `api.post` (POST).
- Заголовок: «Редактировать канал» в edit-mode, «Новый канал» в create-mode.
- `canSubmit`: edit → только `title` (telegram_id не валидируется), create →
  `title` + `hasTelegramId`.
- 2 Svelte `state_referenced_locally` warnings (prefill `channel?.title` в
  `$state(...)`) — advisory, 0 errors. Тот же паттерн, что в `jobs/[id]/+page.svelte`.

### Шаг 6: `api.ts` — хелперы

- `listChannels(showInactive?)` → `api.get('/api/channels', { show_inactive })`.
- `updateChannel(id, payload)` → `api.patch('/api/channels/${id}', payload)`.
- `toggleChannelActive(id, active)` → `api.patch('/api/channels/${id}',
  { is_active: active })`.

### Шаг 7: `channels/+page.svelte` — wiring

- Удалена standalone кнопка «Удалить» (desktop + mobile) — переехала в
  `ActionMenu`.
- Добавлен `<ActionMenu channel={ch} .../>` в каждой строке/карточке.
- State: `replaceChannel: Channel | null`, `editChannel: Channel | null` —
  открывают соответствующие модалки.
- `handleToggleActive(channel)` → `toggleChannelActive(id, !is_active)` → reload.
- `deleteChannel(channel)` — confirm + `api.del` + reload (как было).
- `showInactive` toggle (кнопка «Только активные» / «Все каналы») —
  переключает `listChannels(showInactive)`.
- Неактивные каналы: `opacity-60` (desktop + mobile).
- `handleSaved` закрывает и `showForm`, и `editChannel` (edit modal) + reload.

### Шаг 8: Тесты `web/src/tests/channels.test.ts`

- В `vi.hoisted` добавлены `mockPatch`, `mockUpdateChannel`, `mockToggleChannelActive`.
  `mockUpdateChannel` делегирует в `mockPatch` (записывает URL+payload), возвращает
  `makeChannel`. `mockToggleChannelActive` делегирует в `mockPatch`.
- `beforeEach` сбрасывает все 3 новых mock'а.
- 14 новых тестов (всего 24 в файле):
  - **Channels page** (13): open/close menu (Escape), ReplaceLinkModal opens,
    EditChannelModal prefilled, PATCH edit + refresh, Deactivate (PATCH
    is_active:false), Activate (PATCH is_active:true), Delete (confirm + DELETE
    + refresh), плюс существующие create-mode тесты.
  - **ActionMenu** (4): Activate/Deactivate label depends on is_active, closes
    after action, closes on click-outside.
  - **ChannelForm** (4 new edit-mode): prefills title/username, disables
    telegram_id, shows «Редактировать канал» heading, PATCH on submit.
- Удалён старый тест `calls DELETE /api/channels/{id} when Delete is clicked`
  (кнопка «Удалить» переехала в ActionMenu) — заменён на
  `calls DELETE when Delete is chosen (with confirm)`.

## Почему

3 проблемы из issue #95:
1. **2 клика до действия** — клик по названию канала → `/channels/[id]` →
   форма «Заменить ссылки». Action menu → 1 клик до любого действия.
2. **Нет редактирования канала** — если ввёл неправильно title/username,
   только удалять и создавать заново. Edit-mode в `ChannelForm` + PATCH.
3. **`is_active` мёртвое поле** — показывается как бейдж, изменить нельзя.
   Toggle в action menu → архивирование без удаления.

Action menu решает все 3 + скалируется для будущих фич (просто добавить пункт).

## Pending

- Нет. Все 9 пунктов issue #95 реализованы.
- ADR создан: `docs/decisions/2026-07-23-pr-96-channels-action-menu.md`
  (action menu + модалки вместо клика по названию — архитектурное решение).

## Watch out

- **Backend `active_only` vs `show_inactive`**: оба параметра работают.
  `show_inactive` — alias (True → все, False → только активные). Существующие
  тесты `test_list_channels_returns_all` / `test_list_channels_active_only`
  НЕ сломаны (используют `active_only`).
- **ReplaceLinkModal title conflict**: заголовок модалки — «Замена ссылок в
  канале» (НЕ «Замена ссылки»). `ReplaceLinkForm` уже имеет `<h2>Замена
  ссылки</h2>`, `screen.getByText("Замена ссылки")` падал на multiple match.
- **`mockUpdateChannel`/`mockToggleChannelActive` в `vi.hoisted`**: объявлены
  в `vi.hoisted` (как `mockGet`/`mockPost`), чтобы быть доступными в `vi.mock`
  factory (которая hoisted до импортов). `mockUpdateChannel` делегирует в
  `mockPatch` для записи фактического вызова — тесты assert'ят на
  `mockUpdateChannel` (не `mockPatch`).
- **`fireEvent.click(document.body)` для click-outside**: `fireEvent.mouseDown`
  НЕ триггерит мой `click` listener. Использовать `fireEvent.click(document.body)`.
- **Inactive каналы видны по умолчанию**: `listChannels()` без аргумента
  возвращает ВСЕ каналы (backend `active_only=False` default). Toggle «Только
  активные» → `listChannels(false)`.
- **2 pre-existing + 2 new `state_referenced_locally` warnings**: svelte-check
  0 errors. 2 в `jobs/[id]/+page.svelte` (существовали до), 2 в
  `ChannelForm.svelte` (prefill `channel?.title` в `$state(...)`) — advisory,
  pattern matches existing code.
- **`vi.hoisted` arrow function для `mockUpdateChannel`**: возвращает
  `makeChannel(...)` — но `makeChannel` объявлен ПОСЛЕ `vi.hoisted`. Это
  работает т.к. `makeChannel` вызывается только при actual test run (не при
  hoisting). НЕ используй `makeChannel` в `vi.hoisted` factory для mock
  resolution — только внутри `async` callback.