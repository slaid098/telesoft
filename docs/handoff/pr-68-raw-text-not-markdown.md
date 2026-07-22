---
pr: 68
issue: 67
branch: fix/replace/raw-text-not-markdown
status: ready
created: 2026-07-22
---

# Handoff — PR 68: use raw text message.message instead of markdown message.text

## Что сделано

Реализован issue #67 — критический фикс markdown leakage: после replace в
постах с bold/italic formatting literal `**`/`__` markers утекали в raw text
(`message.message`), а entities становились сломанными.

1. **`link_replacer.py:142`** — `text = message.text or ""` → `text = message.message or ""`.
   `message.message` — raw plain text БЕЗ markdown markers. Entities offsets
   относятся именно к этому полю. `message.text` — markdown-rendered text (с
   `**`/`__`), конфликтует с `formatting_entities` при `edit_message`.

2. **`telegram.py:154`** — `text=message.text or ""` → `text=message.message or ""`
   в `edit_message_entities`. То же исправление для entity-edit path.

3. **`link_replacer.py:229`** — `find_posts_with_pattern`: `getattr(m, "text", ...)`
   → `getattr(m, "message", ...)`. Поиск постов теперь работает по raw text.

4. **`link_replacer.py:290`** — `_preview_one`: `getattr(message, "text", ...)`
   → `getattr(message, "message", ...)`. Preview показывает raw text (без
   markdown markers).

5. **`conftest.py:MockMessage`** — `__post_init__` defaults `message` to `text`
   если не задано явно. Тесты с plain-text постами (без formatting) работают
   без изменений — `message` = `text`. Тесты с formatting могут задавать
   `text` (markdown) и `message` (raw) раздельно.

6. **2 новых теста** — `test_replace_link_in_post_preserves_bold_no_markdown_leakage`
   и `test_replace_link_in_post_with_italic_no_markdown_leakage`. Проверяют
   что результат НЕ содержит `**`/`__`/`_` markdown markers, entities имеют
   корректные offsets (внутри `len(sent_text)`), link заменён.

7. **Обновлены существующие тесты** — `msg.text = None` → `msg.message = None`
   (2 места), `result["old_text"] == msg.text` → `result["old_text"] == msg.message`,
   `message.text = "hello"` → `message.message = "hello"` в `test_telegram_client.py`
   (3 места).

## Почему

E2E тестирование на production (канал "Test portfolio", `-1003903711726`)
выявило что после replace в постах с bold/italic formatting literal `**`
markers утекают в `message.message` (raw text), а entities становились
сломанными. Telegram reject'ил edit с `"Some of provided entities have invalid
bounds"` или сохранял literal `**` в raw text.

Корневая причина: `replace_link_in_post` брал `message.text` (markdown-rendered,
с `**`/`__` markers) для regex substitution, потом передавал результат в
`edit_message(text=new_text, formatting_entities=adjusted)`. Telegram получал
text с `**` + `formatting_entities` → конфликт (markdown parse vs explicit
entities) → literal `**` сохранялись в `message.message` и entities ломались.

Баг существовал с самого начала (`7d3b300 feat(core): add link replacer`),
PR#44/PR#64/PR#66 работали с ним не замечая — тесты использовали `MockMessage`
где `text` = `message` (plain text, без markdown), маскируя проблему.

## Pending

- **`.*` жадность в Simple mode** — `compile_simple("*" → ".*")` + `full_replace=true`
  захватывает trailing text после URL. Рекомендация: `*` → `\S*` (URL-semantic,
  no-whitespace). Не фиксировано в этом PR — требует отдельного тестирования.

- **Посты 140, 141, 143 испорчены** — literal `**` в `message.message` после
  предыдущих edit'ов (pre-PR#68). Backend-фикс НЕ восстанавливает испорченные
  посты — нужно переопубликовать вручную.

- **`_adjust_entity_offsets` формулы case 3a/3b** — reviewer PR#66 отметил
  математическую неточность (under-cover на delta). Defensive validation
  маскирует проблему, но формулы стоит исправить в follow-up.

## Watch out

- **`MockMessage.__post_init__`** — если тест создаёт `MockMessage(text="foo")`
  без явного `message=`, то `message` автоматически = `text`. Для тестов с
  formatting нужно задавать `text` (markdown) и `message` (raw) раздельно.

- **`message.text` vs `message.message` в Telethon** — `text` = markdown-rendered
  (с `**`/`__`), `message` = raw plain text (БЕЗ markers). Для regex/edit
  ВСЕГДА использовать `message.message`. Сохрани в memory.

- **`find_posts_with_pattern` и `_preview_one`** — тоже используют `message.message`
  (не `message.text`). Это значит preview показывает raw text без markdown
  markers — это правильно (пользователь видит что заменится, без артефактов).