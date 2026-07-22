# ADR — PR 68: use raw text message.message instead of markdown message.text

## Статус

Accepted — 2026-07-22

## Контекст

telesoft заменяет ссылки в постах Telegram-каналов. Посты могут содержать
formatting (bold/italic) через entities. При replace нужно сохранить
formatting — для этого PR#64 добавил `_adjust_entity_offsets` который
пересчитывает offsets entities после замены текста.

E2E тестирование на production выявило критический баг: после replace в
постах с bold/italic literal `**`/`__` markdown markers утекали в raw text
(`message.message`), а entities становились сломанными. Telegram reject'ил
edit или сохранял literal markers.

Корневая причина: `replace_link_in_post` брал `message.text` для regex.
Telethon property `message.text` возвращает **markdown-rendered** text (с
`**`/`__` markers для display), а НЕ raw plain text. Entities offsets
относятся к `message.message` (raw text, БЕЗ markers).

Цепочка:
1. `text = message.text` → `"**bold text** tg://... **bold end**"` (markdown)
2. `new_text = re.sub(pattern, new_link, text)` → содержит `**`
3. `_adjust_entity_offsets(entities, text, ...)` считает offsets относительно
   markdown text → неверно (offsets должны быть относительно raw text)
4. `edit_message(text=new_text, formatting_entities=adjusted)` → Telegram
   получает text с `**` + `formatting_entities` → конфликт → literal `**`
   сохраняются в `message.message`, entities ломаются

Баг существовал с самого начала, но маскировался в тестах: `MockMessage`
использовал `text` = `message` (plain text, без markdown), так что тесты
не покрывали случай с formatting.

## Решение

Использовать `message.message` (raw plain text) вместо `message.text`
(markdown-rendered) во всех местах где:
1. Выполняется regex substitution (`replace_link_in_post`)
2. Выполняется edit (`edit_message_entities`)
3. Выполняется поиск постов (`find_posts_with_pattern`)
4. Выполняется preview (`_preview_one`)

`message.message` — это raw plain text БЕЗ markdown markers. Entities
offsets относятся именно к этому полю. `edit_message(text=new_text,
formatting_entities=adjusted)` где `new_text` без markers → Telegram
корректно применяет entities без конфликта с markdown parsing.

`MockMessage.__post_init__` defaults `message` to `text` если не задано —
тесты с plain-text постами работают без изменений. Тесты с formatting
могут задавать `text` (markdown) и `message` (raw) раздельно.

## Альтернативы

1. **Использовать `message.text` но убрать `formatting_entities`** — тогда
   Telegram сам парсит markdown. Но `**` markers остаются в `message.message`
   → entities теряются (Telegram не может применить оба способа одновременно).
   Отвергнуто — теряем formatting preservation.

2. **Парсить markdown обратно в raw text** — сложно, error-prone, дублирует
   логику Telegram. Отвергнуто — `message.message` уже даёт raw text.

3. **Использовать `message.raw_text`** — alias для `message.message` в
   Telethon. Эквивалентно выбранному решению, но `message.message` более
   каноничное имя поля в Telethon API.

4. **Оставить `message.text` и убрать `**` из new_text перед edit** — hack,
   не решает проблему offsets (они уже считались относительно markdown text).
   Отвергнуто — не решает корневую проблему.