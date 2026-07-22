---
pr: <PR-NUMBER>
issue: 65
status: Accepted
created: 2026-07-22
supersedes: []
---

# ADR — PR <PR-NUMBER>: handle entity crossing boundary in _adjust_entity_offsets

## Статус

Accepted.

## Контекст

PR#64 добавил `_adjust_entity_offsets(entities, text, pattern, new_link)` для
сохранения bold/italic entities при замене ссылок в text-ветке
`replace_link_in_post`. Функция обрабатывала 2 случая:

1. Match strictly before entity → shift `entity.offset` by cumulative delta
2. Match strictly inside entity → grow/shrink `entity.length` by per-match delta

Match crossing entity boundary (начинается внутри, заканчивается снаружи, или
наоборот) был оставлен as-is ("edge case; rare and ambiguous" — ADR PR#64).

На production (канал "Test portfolio", пост 139) crossing boundary встретился:
- Bold entity покрывала и текст и ссылку (`**Написать👇**\n\n**<ссылка>**`)
- Pattern `tg:.*` match'ил ссылку: start внутри Bold, end снаружи Bold
- `_adjust_entity_offsets` оставил entity as-is → entity end > len(new_text)
  после замены → Telegram rejects: `"Some of provided entities have invalid bounds"`
- Jobs 7, 8: `failed=1, edited=0`

Тесты `test_link_replacer.py` НЕ покрывали crossing boundary — 8 тестов, ни
одного с match пересекающим границу entity. Регрессия прошла CI.

Дополнительно: `.*` (жадный) в `compile_pattern(full_replace=True)` захватывает
trailing `**` markdown markers → match длиннее чем ссылка → delta больше → OOB
больше. Это вторичная проблема — primary фикс в `_adjust_entity_offsets`.

## Решение

1. **Case 3a: match starts outside entity, ends inside** —
   `m_start < e_offset and m_end > e_offset and m_end <= e_end`:
   ```python
   new_offset = m_start + len(new_link)
   e_length -= new_offset - e_offset
   e_offset = new_offset
   ```
   Entity теперь начинается после replacement (replacement произошёл от
   `m_start`, new link занимает `[m_start, m_start + len(new_link))`).

2. **Case 3b: match starts inside entity, ends outside** —
   `m_start >= e_offset and m_start < e_end and m_end > e_end`:
   ```python
   e_length += len(new_link) - (m_end - m_start)
   ```
   Entity extended/shrunk чтобы покрыть new link (match начинался внутри
   entity → new link тоже внутри entity после замены).

3. **Defensive validation (post-adjustment)** — после всех корректировок:
   ```python
   if (new_entity.offset < 0 or new_entity.length <= 0
           or new_entity.offset + new_entity.length > len(new_text)):
       continue  # drop invalid entity
   ```
   `new_text = re.sub(pattern, new_link, text)` вычисляется внутри функции.
   Страховка от будущих edge cases — невалидные entities не попадают в
   Telegram API (где они вызывают reject всего edit).

4. **4 новых теста** покрывают crossing boundary + defensive validation.

5. **`pattern_compiler.py` НЕ трогать** в этом PR. `.*` жадность — вторичная
   проблема. Primary фикс в `_adjust_entity_offsets` покрывает последствия
   (crossing boundary + defensive validation).

## Альтернативы

1. **Clamp вместо drop.** Если entity OOB → `length = len(new_text) - offset`
   вместо drop. Проще, но может дать entity покрывающую мусор (не то что
   хотел автор поста). Отвергнуто: drop безопаснее — entity исчезает, text
   остаётся, Telegram не reject'ит весь edit.

2. **Вычислять `new_text` снаружи и передавать параметром.** Добавить
   `new_text: str` параметр в `_adjust_entity_offsets`. Отвергнуто: сигнатура
   уже принимает `pattern` + `new_link` + `text` — `re.sub` внутри дешёвый
   (O(1) на функцию, не на entity). Внутреннее вычисление проще для callers.

3. **Fix `.*` жадность в `pattern_compiler.py` (замена на `\S+`).** Primary
   фикс на уровне pattern — match не захватывает `**` markers → crossing
   boundary не возникает. Отвергнуто для этого PR: рискованно (может ломать
   другие кейсы — нужно тестировать), secondary к `_adjust_entity_offsets`.
   Отдельный PR.

4. **Полностью переписать `_adjust_entity_offsets` через diff algorithm.**
   Вместо case-by-case — построить diff между `text` и `new_text`, применить
   к offsets. Отвергнуто: overengineering для MVP, case-by-case достаточно
   покрывает реальные кейсы + defensive validation страховка.

## Последствия

- Crossing boundary (match starts inside, ends outside entity) обрабатывается
  — entity extended/shrunk, не оставляется as-is (fix problem 1)
- Crossing boundary (match starts outside, ends inside entity) обрабатывается
  — offset shifted to after replacement (fix problem 1)
- Defensive validation: невалидные entities dropped, не отправляются в
  Telegram API (fix problem 2 — reject "invalid bounds")
- 2 existing теста поправлены (entities с `offset+length > len(text)` были
  тестовыми артефактами, теперь валидны относительно text)
- `pattern_compiler.py` `.*` жадность НЕ фиксирована — secondary, отдельный PR