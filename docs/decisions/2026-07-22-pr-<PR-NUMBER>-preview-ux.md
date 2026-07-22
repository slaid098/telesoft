# ADR — PR <PR-NUMBER>: link_preview configurable + preview-confirm-run workflow

## Статус

Accepted — 2026-07-22

## Контекст

telesoft заменяет ссылки в постах Telegram-каналов через
`client.edit_message()`. Telethon `client.edit_message()` по умолчанию
передаёт `link_preview=True` в MTProto `MessagesEditMessageRequest` →
после каждого edit Telegram показывает превьюшку (link preview card)
новой ссылки в посте. Юзер не контролировал это поведение — превью
появлялось всегда, даже когда не нужно.

Дополнительно: UI flow «Запустить» сразу запускал job (POST
`/replace-link` → `runner.submit`) без подтверждения. Юзер не видел
before→after до запуска, что приводило к ошибкам (неверный pattern,
не та ссылка и т.д.). Уже существовал PreviewModal (PR#58) и чекбокс
«Показать предпросмотр» (PR#76, default off), но preview был
опциональным, а запуск — прямым.

Требования issue #85:
1. `link_preview` configurable per-job (default `False`).
2. Workflow: «Запустить» → PreviewModal → confirm → run (вместо
   прямого запуска).

## Решение

### 1. `link_preview` прокинут через всю цепочку (default `False`)

`ReplaceLinkRequest.link_preview: bool = False` (Pydantic schema) →
`runner.submit(link_preview=...)` → `runner._run_job(link_preview=...)`
→ `replace_link_in_post(link_preview=...)` →
`edit_message(link_preview=...)` / `edit_message_entities(link_preview=...)`
→ `client.edit_message(link_preview=link_preview)`.

Telethon `client.edit_message` принимает `link_preview` kwarg (не
позиционный), передаёт в MTProto. `False` → Telegram НЕ рендерит
превьюшку. `True` → рендерит (старое поведение).

`replace_link_in_posts` (оркестратор) тоже принял `link_preview` и
форвардит в каждый `replace_link_in_post` — для консистентности, хотя
runner вызывает `replace_link_in_post` напрямую (не через
`replace_link_in_posts`).

### 2. Workflow preview-confirm-run

- Старый чекбокс «Показать предпросмотр» + отдельная кнопка «Предпросмотр»
  убраны. Preview теперь обязательный шаг.
- «Запустить» (form submit) → `handlePreview()` → `previewReplace()` API
  → `onPreview` callback → родительский `+page.svelte` открывает
  `PreviewModal` (before→after pairs).
- В модалке: «Запустить» → `onRun` → `preview = null; runNonce += 1`.
  `runNonce` передаётся в `ReplaceLinkForm` как prop, `$effect` на
  `runNonce` (существовал раньше) вызывает `submitJob()` → `replaceLink()`
  API → `goto(/jobs/{id})`.
- «Отменить» → `onEdit` → `preview = null` (возврат к форме, job НЕ
  запускается).

### 3. Чекбокс «Включить превью ссылки» в форме

`linkPreview = $state(false)` (default off). Размещён после radio
«Полная/Частичная замена», перед лимитом. `link_preview: linkPreview`
добавлен в payload `previewReplace()` (для консистентности, preview не
редактирует) и `replaceLink()` (главный — определяет превью в edit'е).

## Альтернативы

1. **Hardcoded `link_preview=False` без чекбокса** — всегда подавлять
   превью, не давать юзеру выбор. Отвергнуто — issue #85 явно требует
   configurable per-job через чекбокс («по умолчанию False, но юзер
   может включить»).

2. **Чекбокс в PreviewModal (а не в форме)** — размещать
   «Включить превью ссылки» внутри модалки, рядом с кнопками. Отвергнуто
   — modalka показывает before→after текста, превью ссылки логически
   относится к форме (настройки job). К тому же в модалке юзер уже
   решил запускать — переключать настройку в последний момент
   неестественно. Форма даёт время подумать.

3. **Отдельная кнопка «Preview» + «Запустить» (старый flow PR#76)** —
   оставить опциональный preview + прямой запуск. Отвергнуто issue #85:
   workflow без подтверждения приводил к ошибкам. Новая модель
   «preview-confirm-run» гарантированно показывает before→before до
   запуска.

4. **`link_preview` только в `replaceLink()`, НЕ в `previewReplace()`** —
   preview не редактирует, поле не нужно. Частично принято: backend
   `PreviewRequest` НЕ имеет `link_preview` (extra key игнорируется
   Pydantic). Frontend передаёт `link_preview: linkPreview` в обоих
   payload для консистентности (один объект формы, не дублировать).
   TS `PreviewRequest.link_preview?: boolean` (optional) — если backend
   добавит `extra="forbid"`, нужно будет добавить поле в backend или
   убрать из TS.

5. **`link_preview` в DB (`edit_jobs` table)** — персистить с job, чтобы
   видна в logs. Отвергнуто как over-engineering для MVP: поле нужно
   только в момент edit, в `edit_logs` `old_text` уже есть. Если
   понадобится аудит «был ли preview» — миграция в новом PR.