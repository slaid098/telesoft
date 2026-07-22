---
pr: 70
issue: 69
branch: fix/replace/entity-offset-math
status: ready
created: 2026-07-22
---

# Handoff — PR 70: correct entity offset math + non-greedy wildcard

## Что сделано

Реализован issue #70 — исправление двух корневых причин потери
форматирования (bold/italic) при замене ссылок в постах Telegram-каналов.

1. **`link_replacer.py:102-107`** — исправлены формулы case 3a/3b в
   `_adjust_entity_offsets`:
   - **Case 3a** (match starts outside entity, ends inside): старая формула
     `e_length -= new_offset - e_offset` давала неверную длину. Новая:
     `e_length = e_end - m_end` — выживший хвост entity от конца match до
     оригинального конца entity.
   - **Case 3b** (match starts inside entity, ends outside): старая формула
     `e_length += len(new_link) - (m_end - m_start)` давала **отрицательную
     длину** при короткой замене (типичный случай: длинный `tg://resolve?...`
     → короткий `https://new.io`) → defensive validation дропала entity
     полностью → жирность пропадала. Новая формула:
     `e_length = (m_start + len(new_link)) - e_offset` — entity покрывает
     от своего начала до конца replacement, всегда положительная длина.
   - Обновлён docstring функции (строки 80-86).

2. **`pattern_compiler.py:58`** — `.*` (greedy) → `\S*` (non-whitespace)
   в `full_replace=True` Simple mode. Жадный `.*` захватывал trailing text
   после URL (включая пробелы и текст), усугубляя Bug #2 — match выходил
   за пределы entity. `\S*` ограничивает match non-whitespace символами.
   Обновлён docstring (строки 42-43).

3. **3 false-positive теста** в `tests/test_link_replacer.py` обновлены с
   правильными ожиданиями:
   - `test_adjust_entity_offsets_crossing_boundary_match_starts_inside_entity`
     (case 3b): `length == 5` → `== 6` (entity покрывает "PHRASE").
   - `test_adjust_entity_offsets_crossing_boundary_match_starts_outside_entity`
     (case 3a): `length == 4` → `== 5` (entity покрывает "ORDyy").
   - `test_replace_link_in_post_with_bold_crossing_boundary` (case 3b):
     `length == 20` → `== 24` (entity покрывает "bold text https://new.io").
   - Комментарии в тестах обновлены с правильной математикой.

4. **Regression test** `test_adjust_entity_offsets_case3b_short_replacement_preserves_entity`
   добавлен: text `"aBOLD_LINK_REST_extra"` (22 chars), entity
   `Bold(offset=1, length=10)`, match `"BOLD_LINK_REST"` at [1, 15],
   new_link `"X"` (1 char, короче match). Старый код дропал entity
   (negative length), новый сохраняет с `offset=1, length=1` (покрывает "X").

5. **Тесты pattern_compiler** обновлены для `\S*` — 4 теста в
   `test_pattern_compiler.py` и 3 теста в `test_api_patterns.py` которые
   проверяли `full_replace=True` и ожидали `.*` → обновлены на `\S*`.

## Почему

Форматирование (bold/italic) пропадало при замене ссылок — entity дропалась
из-за отрицательной длины (case 3b) или неправильного offset (case 3a).
Жадный `.*` захватывал trailing text после URL, усугубляя проблему — match
выходил за пределы entity, trigger'ая case 3b с большой разницей длин.

Цепочка:
1. `compile_pattern(pattern, "simple", full_replace=True)` → `pattern.*`
2. URL в посте: `tg://resolve?domain=bot&start=flow-123 some text after`
3. regex `tg://\S*.*` match'ит ВСЮ строку включая " some text after"
4. `replace_link` заменяет на короткий `https://new.io`
5. `_adjust_entity_offsets` case 3b: `e_length += 14 - 40` = `-26` → drop
6. Entity пропадает → жирность теряется

Новые формулы математически корректны:
- Case 3a: выживший хвост = `e_end - m_end` (от конца match до конца entity)
- Case 3b: новая длина = `(m_start + len(new_link)) - e_offset` (от начала
  entity до конца replacement) — всегда ≥ 0 если match начинается внутри

## Pending

- **E2E проверка на production** — backend-фикс математически корректен, но
  требует проверки на реальном канале (`-1003903711726`) с постами где
  bold/italic entity пересекаются с заменяемой ссылкой.

- **Посты 140, 141, 143 испорчены** (PR#68 Pending) — literal `**` в
  `message.message` после предыдущих edit'ов. Backend-фикс НЕ
  восстанавливает испорченные посты — нужно переопубликовать вручную.

## Watch out

- **`compile_simple("*" → ".*")` НЕ изменён** — `*` в simple mode ВСЁ ещё
  компилируется в `.*` (greedy). Изменён только `full_replace=True` tail
  который добавляется к compiled pattern. Если пользователь явно использует
  `*` в simple mode — он получает `.*` (ожидающий behavior).

- **`\S*` vs `\S+`** — `full_replace=True` добавляет `\S*` (zero-or-more),
  НЕ `\S+` (one-or-more). Это позволяет match'ить URL который точно совпадает
  с pattern (без trailing non-whitespace). Существующий check
  `not compiled.endswith(r"\S+")` предотвращает дублирование если pattern
  уже заканчивается на `\S+`.

- **Case 3b формула не symmetric с case 3a** — 3a сохраняет хвост entity
  после match, 3b сохраняет начало entity до конца replacement. Это
  правильно: в 3b entity начинается ДО match, replacement "съедает" конец
  entity, выжившая часть — от начала entity до конца replacement.