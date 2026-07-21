---
status: accepted
date: 2026-07-21
pr: 64
supersedes: []
---

# ADR — PR 64: preserve formatting entities + preview context + full/partial radio

## Статус

Accepted.

## Контекст

При тестировании на production (посты 1369-1371 канала "Познакомиться с
девушкой") обнаружены три проблемы:

1. **Потеря форматирования (CRITICAL).** При замене ссылки в **text** (не
   entity), `replace_link_in_post` вызывал `edit_message(chat_id, message_id,
   text=new_text)` БЕЗ `formatting_entities`. Telegram терял bold/italic/link
   entities — посты с `**Елена, 47 лет**` после замены рендерились как сырой
   markdown без форматирования. Entity-ветка (formatted links) этой проблемы
   не имела — `edit_message_entities` передавал `formatting_entities=entities`.

2. **Превью показывало весь пост.** `_preview_one` text-ветка возвращала
   `"before": text, "after": new_text` — ВЕСЬ текст поста (500+ символов),
   включая markdown-разметку. Несогласовано с entity-веткой (только URL). Юзер
   видел простыню текста вместо фокуса на замене.

3. **"Сохранить хвост" хардкод -s-*.** `apply_keep_tail` (pattern_compiler.py)
   захардкожен на конкретные формы `-s-\d+` / `-s-.*`. Универсальное решение:
   radio "Полная" / "Частичная" замена через `*` wildcard в Simple mode.

## Решение

1. **Пересчёт entity offsets.** Добавлена функция
   `_adjust_entity_offsets(entities, text, pattern, new_link)` которая для
   каждого match of pattern in text:
   - match strictly before entity → shift `entity.offset` by cumulative delta
     (`len(new_link) - len(match)`)
   - match strictly inside entity → adjust `entity.length` by per-match delta
   - match crossing entity boundary → leave as is (edge case)
   Копии entities через `copy.copy` (оригиналы не мутируются). `edit_message`
   принимает опциональный `formatting_entities` параметр.

2. **50 символов контекста.** `_preview_one` text-ветка возвращает
   `context_50_before + matched_link + context_50_after` и
   `context_50_before + new_link + context_50_after`. Посты < 100 символов
   показываются целиком (естественный результат формулы).

3. **Radio "Полная" / "Частичная".** Удалён `apply_keep_tail` (хардкод).
   `compile_pattern(raw, mode, full_replace: bool = True)`:
   - `full_replace=True` → если pattern не заканчивается на `.*` или `\S+`,
     добавить `.*` в конец (покрывает всю ссылку)
   - `full_replace=False` → pattern as is (частичная, окончание остаётся)
   `ReplaceLinkRequest` / `PreviewRequest`: `keep_tail: bool` → `full_replace:
   bool = True`. Frontend: чекбокс "Сохранить хвост" заменён на radio.

## Альтернативы

1. **Всё через entities (не пересчёт offsets).** Создать entity для новой
   ссылки (`MessageEntityTextUrl`), оригинальные entities сохранить. Проще но
   может потерять inline-ссылки (если ссылка в text — это уже entity, замена
   через новый entity дублирует). Отвергнуто: пересчёт offsets универсальнее.

2. **Убрать чекбокс "Сохранить хвост" полностью, оставить только Simple `*`.**
   `*` в Simple mode уже даёт контроль: куда поставишь, там обрежется. Radio
   избыточен. Отвергнуто: radio понятнее для юзера (не нужно объяснять `*`).

3. **Хардкодить конкретные хвосты (расширить `_TAIL_RE`).** Добавить
   `&utm=*`, `?ref=*`, и т.д. Отвергнуто: не универсально, требует
   поддержки каждого нового формата.

4. **Превью: только ссылка без контекста.** Совсем чисто, но юзер не видит
   где в посте ссылка находится. Отвергнуто: 50 символов контекста дают
   минимальный ориентир.

5. **Превью: весь пост с подсветкой заменяемой части.** Максимальный
   контекст, но визуально шумно и сложно в UI. Отвергнуто: избыточно.

## Последствия

- Bold/italic/ссылки сохраняются при замене в text-ветке (fix problem 1)
- Превью показывает 50 символов контекста вместо 500+ символов (fix problem 2)
- `keep_tail` API параметр заменён на `full_replace` (backward incompatible
  для API callers, но backward compatible в UI — default changed from
  `keep_tail=False` to `full_replace=True`, что семантически эквивалентно
  "заменить целиком")
- `apply_keep_tail` и `_TAIL_RE` удалены — хардкод `-s-*` больше не
  поддерживается. Юзеры использовавшие `keep_tail=True` должны переключиться
  на `full_replace=False` + `*` в pattern для частичной замены.