---
pr: <PR-NUMBER>
issue: 65
branch: fix/replace/entity-crossing-boundary
status: ready
created: 2026-07-22
---

# Handoff — PR <PR-NUMBER>: handle entity crossing boundary in _adjust_entity_offsets

## Что сделано

Реализован issue #65 — фикс регрессии PR#64: `_adjust_entity_offsets` не
обрабатывал случай когда match пересекает границу entity (начинается внутри,
заканчивается снаружи, или наоборот).

1. **Crossing boundary case 3a** — match starts outside entity, ends inside.
   `new_offset = m_start + len(new_link)`, `e_length -= new_offset - e_offset`,
   `e_offset = new_offset`. Entity теперь начинается после replacement.

2. **Crossing boundary case 3b** — match starts inside entity, ends outside.
   `e_length += len(new_link) - (m_end - m_start)`. Entity extended чтобы
   покрыть new link.

3. **Defensive validation** — после всех корректировок каждый entity
   проверяется: `offset < 0` OR `length <= 0` OR `offset + length > len(new_text)`
   → entity dropped (не appended). Страховка от будущих edge cases — невалидные
   entities не попадают в Telegram API.

4. **`new_text` вычисляется внутри** `_adjust_entity_offsets` через
   `re.sub(pattern, new_link, text)` (раньше функция не знала итоговую длину
   text, теперь знает для validation).

5. **4 новых теста** в `test_link_replacer.py`:
   - `test_adjust_entity_offsets_crossing_boundary_match_starts_inside_entity`
     — case 3b: entity length extended, original not mutated
   - `test_adjust_entity_offsets_crossing_boundary_match_starts_outside_entity`
     — case 3a: offset shifted to after replacement, length shrunk
   - `test_adjust_entity_offsets_drops_invalid_entities` — entity с
     offset+length > len(new_text) после substitution → dropped
   - `test_replace_link_in_post_with_bold_crossing_boundary` — integration:
     bold entity crossed by match → preserved + clamped, edit_message called

6. **2 existing теста поправлены** — `test_adjust_entity_offsets_no_matches_returns_copies`
   и `test_adjust_entity_offsets_delta_negative` имели entities с
   `offset+length > len(text)` (тестовые артефакты). Теперь defensive validation
   их дропает → assertion `len(adjusted) == 1` падал. Entities сделаны валидными
   относительно text length.

## Почему

PR#64 добавил `_adjust_entity_offsets` для сохранения bold/italic при замене
ссылок, но функция обрабатывала только 2 случая: match strictly before entity
(shift) и match strictly inside entity (grow length). Crossing boundary был
оставлен as-is ("edge case; rare and ambiguous").

На production (канал "Test portfolio", пост 139) crossing boundary встретился:
- Пост: `**Написать👇**\n\n**tg://resolve?domain=znak_tut_nowbot&start=...**`
- Bold entity: offset=428, length=62 (покрывает и "Написать" и ссылку)
- Pattern `tg:.*` match'ит ссылку: start=438 (внутри Bold), end=502 (снаружи
  Bold end=490)
- `_adjust_entity_offsets` оставил entity as-is (crossing boundary не обработан)
- `re.sub` заменил 64 chars на 29 → text стал 467 (был 502, delta=-35)
- Entity остался offset=428, length=62 → end=490 > 467 → **out of bounds**
- Telegram rejects: `"Some of provided entities have invalid bounds"`
- Jobs 7, 8: `failed=1, edited=0`

Тесты `test_link_replacer.py` НЕ покрывали crossing boundary — 8 тестов, ни
одного с match пересекающим границу entity. Регрессия прошла CI.

Defensive validation — страховка от будущих edge cases. Даже если алгоритм
miss'нет какой-то случай, невалидные entities будут dropped, а не отправлены
в Telegram API (где они вызывают reject всего edit).

## Pending

- `pattern_compiler.py` `.*` жадность (issue #65 шаг 4, опциональный) —
  `compile_pattern(full_replace=True)` добавляет `.*` если pattern не
  заканчивается на `.*`/`\S+`. Для Simple mode `tg://*` → `tg://.*` — жадный
  `.*` захватывает trailing `**` markdown markers → match длиннее чем ссылка →
  delta больше → OOB больше. Primary фикс в `_adjust_entity_offsets` (этот PR)
  покрывает последствия. Замена `.*` на `\S+` — отдельный PR (рискованно, может
  ломать другие кейсы — нужно тестировать).
- Ручная проверка на Server 1 после деплоя: создать пост
  `**bold** tg://resolve?domain=test&start=flow-123 **bold**`, заменить
  `tg://*` → `https://new.example.com` (Simple mode, full_replace=true),
  проверить: bold сохранён, ссылка заменена, нет errors.

## Watch out

- **Defensive validation дропает entities с `offset+length > len(new_text)`** —
  это НЕ backward incompatible (раньше такие entities отправлялись в Telegram
  и вызывали reject всего edit → теперь dropped, edit succeeds без этого entity).
  Но если existing тесты создавали entities с невалидными bounds относительно
  text (тестовые артефакты) — они упадут. 2 теста поправлены в этом PR.

- **`new_text` вычисляется внутри `_adjust_entity_offsets`** через
  `re.sub(pattern, new_link, text)`. Сигнатура функции НЕ изменилась
  (`(entities, text, pattern, new_link)`). `new_text` нужен только для
  validation — дублирует `re.sub` из `replace_link_in_post`, но это O(1)
  относительно количества entities (один `re.sub` на функцию, не на entity).

- **Case 3a (match starts outside, ends inside)** — `new_offset = m_start +
  len(new_link)`. Логика: replacement происходит от `m_start`, new link
  занимает `[m_start, m_start + len(new_link))`. Entity теперь начинается
  после replacement. `e_length -= new_offset - e_offset` — shrink на overlap
  между старым entity start и новым offset.

- **Case 3b (match starts inside, ends outside)** — `e_length += delta`.
  Логика: entity extended чтобы покрыть new link (match начинался внутри
  entity, значит new link тоже внутри entity после замены). Delta может быть
  negative (new link короче match) → entity shrinks.

- **Не трогать `pattern_compiler.py`** в этом PR. `.*` жадность — вторичная
  проблема. Primary фикс в `_adjust_entity_offsets`. См. Pending.