pr: 64
issue: 63
branch: fix/replace/formatting-preview-radio
status: ready
created: 2026-07-21
---

# Handoff — PR 64: preserve formatting entities + preview context + full/partial radio

## Что сделано

Реализован issue #63 — три проблемы обнаружены на production при замене
ссылок в постах 1369-1371 канала "Познакомиться с девушкой":

1. **Потеря форматирования (CRITICAL)** — `replace_link_in_post` text-ветка
   вызывала `edit_message(chat_id, message_id, text=new_text)` БЕЗ
   `formatting_entities`. Telegram терял bold/italic/link entities — посты с
   `**Елена, 47 лет**` после замены рендерились как сырой markdown.
   Фикс: `_adjust_entity_offsets(entities, text, pattern, new_link)` пересчитывает
   offsets оригинальных entities (bold/italic/etc) после `re.sub`. Для каждого
   match strictly-before-entity → shift offset; match-inside-entity → adjust
   length; match-crossing-boundary → leave as is. Копии через `copy.copy`
   (оригиналы не мутируются). `edit_message` теперь принимает опциональный
   `formatting_entities` параметр и передаёт в `client.edit_message`.

2. **Превью показывало весь пост** — `_preview_one` text-ветка возвращала
   `"before": text, "after": new_text` (500+ символов). Несогласовано с
   entity-веткой (только URL).
   Фикс: 50 символов контекста до/после match + сама ссылка. Посты < 100
   символов показываются целиком (естественный результат формулы).

3. **"Сохранить хвост" хардкод -s-*** — `apply_keep_tail` (pattern_compiler.py)
   захардкожен на `-s-\d+` / `-s-.*`. Универсальное решение: radio "Полная" /
   "Частичная" замена.
   Фикс: удалён `apply_keep_tail`, `_TAIL_RE`. `compile_pattern(raw, mode,
   full_replace: bool = True)` — `full_replace=True` добавляет `.*` в конец
   если pattern не заканчивается на `.*` / `\S+`; `full_replace=False` — pattern
   as is (частичная). `ReplaceLinkRequest` / `PreviewRequest`:
   `keep_tail: bool` → `full_replace: bool = True`. Frontend: чекбокс "Сохранить
   хвост" заменён на radio "Полная замена" / "Частичная (оставить окончание)".

## Почему

При замене ссылок в text-ветке форматирование (bold/italic) терялось — посты
после редактирования выглядели как сырой markdown. Превью показывало простыню
текста вместо фокуса на замене. Хардкод `-s-*` не подходил для произвольных
окончаний ссылок — универсальный radio "Полная"/"Частичная" через `*` wildcard
даёт юзеру полный контроль.

## Pending

- E2E тесты (`web/tests/e2e/mobile.spec.ts`) — тест 5 (replace-link form
  submission) может сломаться на новом UI (radio вместо чекбокса). Отдельный PR.
- Integration tests на Server 1 — проверить что bold/italic действительно
  сохраняются при реальной замене (через `docker exec` smoke test).

## Watch out

- **`copy.copy(entity)`** — Telethon entities (`MessageEntityBold`,
  `MessageEntityItalic`, etc) — объекты. Оригиналы НЕ мутируются (они в
  message object). Создаём копии через `copy.copy` + изменяем `offset`/`length`.
- **Edge case: match пересекает границу entity** — оставлен as is. Например,
  если `**bold text**` и match начинается внутри bold но заканчивается снаружи.
  В реальных постах встречается редко (ссылки обычно вне bold/italic).
- **`full_replace=True` (default)** — `compile_pattern` добавляет `.*` в конец
  если pattern не заканчивается на `.*` / `\S+`. Это **backward compat** для
  существующих API callers: `keep_tail=False` (default) → `full_replace=True`
  (default). Но семантика изменилась: `full_replace=False` ≠ `keep_tail=True`
  (нет хардкода `-s-*`, просто pattern as is).
- **Preview context 50 chars** — `_PREVIEW_CONTEXT = 50` константа в
  `link_replacer.py`. Если нужно больше/меньше — изменить константу.