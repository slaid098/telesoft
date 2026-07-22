---
pr: 86
issue: 85
branch: feat/replace/preview-ux
status: ready
created: 2026-07-22
---

# Handoff — PR 86: link_preview configurable + preview-confirm-run workflow

## Что сделано

Реализован issue #85 — две связанные UX-правки в replace-link flow:

1. **Backend: `link_preview` configurable per-job** — `edit_message()` больше
   не передаёт Telethon default (`True`) → превьюшка ссылки больше НЕ
   показывается после редактирования. Юзер может включить превью через
   чекбокс (по умолчанию выкл).

   - `src/telesoft/schemas/job.py` — `ReplaceLinkRequest.link_preview: bool = False`
   - `src/telesoft/core/telegram.py` — `edit_message()` и
     `edit_message_entities()` принимают `link_preview: bool = False`,
     передают `link_preview=link_preview` в `client.edit_message()`.
   - `src/telesoft/core/link_replacer.py` — `replace_link_in_post()` и
     `replace_link_in_posts()` принимают `link_preview: bool = False`,
     форвардят в `edit_message()` / `edit_message_entities()`
     (`replace_link_in_posts` → `replace_link_in_post`).
     `replace_link_in_posts` получил `# noqa: PLR0913` (6 > 5 args).
   - `src/telesoft/core/runner.py` — `submit()` и `_run_job()` принимают
     `link_preview: bool = False`, `_run_job` передаёт в
     `replace_link_in_post(link_preview=link_preview)`.
   - `src/telesoft/api/routers/jobs.py` — `replace_link_endpoint` передаёт
     `link_preview=payload.link_preview` в `runner.submit()`.

2. **Frontend: workflow preview-confirm-run** — «Запустить» больше НЕ
   запускает job напрямую. Вместо этого показывается PreviewModal
   (before→after), юзер подтверждает («Запустить» в модалке → `runNonce += 1`
   → `$effect` запускает `submitJob()`) или отменяет («Отменить» → закрытие).
   Старый чекбокс «Показать предпросмотр» + отдельная кнопка «Предпросмотр»
   убраны — preview теперь обязательный шаг перед запуском.

   - `web/src/lib/components/ReplaceLinkForm.svelte`:
     - Убран `showPreview` state, чекбокс «Показать предпросмотр», отдельная
       кнопка «Предпросмотр».
     - Добавлен `linkPreview = $state(false)` + чекбокс «Включить превью
       ссылки» (после radio «Полная/Частичная замена», перед лимитом).
     - `handleSubmit` теперь вызывает `handlePreview()` (НЕ `submitJob()`).
     - `link_preview: linkPreview` добавлен в payload `previewReplace()` и
       `replaceLink()`.
     - Кнопка «Запустить» показывает `previewing ? "Предпросмотр…" : "Запустить"`
       (раньше показывала `submitting ? "Запуск…" : "Запустить"`).
     - `$effect` на `runNonce` оставлен без изменений (запускает `submitJob()`
       при подтверждении из модалки).
   - `web/src/lib/components/PreviewModal.svelte`:
     - «Изменить pattern» → «Отменить».
     - «Запустить job» → «Запустить».
   - `web/src/lib/types.ts` — `ReplaceLinkRequest.link_preview: boolean`
     (required), `PreviewRequest.link_preview?: boolean` (optional, для
     консистентности; backend `PreviewRequest` пока не имеет поля, но
     extra key игнорируется Pydantic).

3. **Тесты backend:**
   - `tests/test_telegram_client.py`:
     - Обновлены `test_edit_message_success` и
       `test_edit_message_entities_uses_high_level_api` — expected call args
       теперь включают `link_preview=False` (default).
     - `test_edit_message_link_preview_false_passes_to_telethon` —
       `edit_message(link_preview=False)` → mock call с `link_preview=False`.
     - `test_edit_message_link_preview_true_passes_to_telethon` —
       `edit_message(link_preview=True)` → mock call с `link_preview=True`.
     - `test_edit_message_entities_link_preview_true_passes_to_telethon` —
       entity path с `link_preview=True`.
   - `tests/test_link_replacer.py`:
     - `test_replace_link_in_post_link_preview_false_passes_to_edit` —
       text path, `link_preview=False`.
     - `test_replace_link_in_post_link_preview_true_passes_to_edit` —
       text path, `link_preview=True`.
     - `test_replace_link_in_post_link_preview_true_entity_path` —
       entity path, `link_preview=True` доходит до `edit_message_entities`.
     - `test_replace_link_in_post_defaults_to_link_preview_false` —
       без kwarg → `link_preview=False` (default).
   - `tests/test_api_jobs.py`:
     - `test_replace_link_link_preview_true_reaches_runner` — POST с
       `link_preview: true` → `runner.submit(link_preview=True)` (через
       `MagicMock(wraps=mock_runner.submit)` spy).
     - `test_replace_link_link_preview_defaults_to_false` — без
       `link_preview` → `runner.submit(link_preview=False)`.

4. **Тесты frontend (`web/src/tests/replace-link.test.ts`):**
   - Обновлены submit-тесты: form submit теперь вызывает `previewReplace`
     (НЕ `replaceLink` напрямую).
   - «submits with pattern…» → проверяет `previewReplace` call с `link_preview: false`.
   - «sends full_replace=false…» → `previewReplace` с `full_replace: false`.
   - «preview button calls previewReplace» → переименован в
     «Запустить button triggers previewReplace (preview-confirm-run flow)»,
     проверяет `previewReplace` call + `onPreview` callback.
   - Новый тест `link_preview checkbox passes link_preview=true to previewReplace` —
     чекбокс «Включить превью ссылки» → `link_preview: true` в payload.
   - `runNonce` тесты обновлены: expected `replaceLink` call теперь включает
     `link_preview: false`.
   - Новый тест `runNonce passes link_preview=true when checkbox checked` —
     чекбокс + runNonce → `replaceLink` с `link_preview: true`.

## Почему

- **Link preview показывался всегда** после редактирования поста (Telethon
  `client.edit_message` default `link_preview=True`). Юзер не хотел
  превьюшки — теперь default `False`, с опцией включить через чекбокс.
- **Workflow без подтверждения** приводил к ошибкам: юзер нажимал «Запустить»
  и job стартовал сразу, без шанса проверить before→after. Теперь
  «Запустить» → PreviewModal → confirm → run.

## Pending

— (нет pending технических задач; E2E проверка на production канале как
обычно выходит за рамки PR).

## Watch out

- **`link_preview` default `False` ломает старое поведение** — любой
  существующий code, ожидавший превью после edit, получит её отсутствие.
  В telesoft это ожидаемое поведение (issue #85 требует `False` default).

- **`PreviewRequest.link_preview` в TS optional** — backend
  `PreviewRequest` (Pydantic) НЕ имеет поля `link_preview` (preview не
  редактирует). TS тип помечен `?` для консистентности; extra key
  игнорируется Pydantic (no `extra="forbid"`). Если backend когда-нибудь
  добавит `extra="forbid"` — нужно либо добавить поле в backend
  `PreviewRequest`, либо убрать из TS.

- **`MagicMock(wraps=...)` для sync `submit()`** — `runner.submit` sync
  (не async), `AsyncMock` создавал coroutine-warning (`coroutine was never
  awaited`). Использован `MagicMock` (sync spy), `submit` вызывается
  синхронно, spy записывает call args.

- **PreviewModal кнопки renamed** — «Изменить pattern» → «Отменить»,
  «Запустить job» → «Запустить». Тест `PreviewModal > shows before→after
  pairs` НЕ проверяет текст кнопок (только preview content) — не упал.

- **`submitJob()` НЕ вызывается из form submit** — только из `$effect` на
  `runNonce` (подтверждение из модалки). Если кто-то добавит кнопку «run
  without preview» — нужно вернуть прямой вызов `submitJob()`.