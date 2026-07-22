# ADR — PR 69: correct entity offset math + non-greedy wildcard

## Статус

Accepted — 2026-07-22

## Контекст

telesoft заменяет ссылки в постах Telegram-каналов. Посты могут содержать
formatting (bold/italic) через entities. При replace нужно сохранить
formatting — для этого PR#64 добавил `_adjust_entity_offsets` который
пересчитывает offsets entities после замены текста.

PR#66 добавил handling для case 3a/3b (match пересекает границу entity),
но формулы были математически неверны:

- **Case 3b** (match starts inside entity, ends outside) — типичный
  production сценарий: ссылка обёрнута в bold, match заменяет её на более
  короткую. Формула `e_length += len(new_link) - (m_end - m_start)` давала
  **отрицательную длину** когда new_link короче match (обычный случай:
  длинный `tg://resolve?domain=...&start=flow-123` → короткий
  `https://new.io`). Defensive validation (строки 110-115) дропала entity
  полностью → жирность пропадала.

- **Case 3a** (match starts outside entity, ends inside) — формула
  `e_length -= new_offset - e_offset` давала неверную длину выжившего хвоста.

Дополнительно, `pattern_compiler.py:58` — `full_replace=True` добавлял
`.*` (greedy) к compiled pattern. Жадный `.*` захватывал trailing text
после URL (включая пробелы и текст после ссылки), усугубляя Bug #2 — match
выходил за пределы entity, trigger'ая case 3b с большой разницей длин.

## Решение

### Case 3a: `e_length = e_end - m_end`

Match начинается вне entity, заканчивается внутри. Выживший хвост entity —
от конца match (`m_end`) до оригинального конца entity (`e_end`).
Offset сдвигается на `m_start + len(new_link)` (начало replacement в
post-substitution text).

### Case 3b: `e_length = (m_start + len(new_link)) - e_offset`

Match начинается внутри entity, заканчивается вне. Entity покрывает от
своего начала (`e_offset`) до конца replacement (`m_start + len(new_link)`
в post-substitution text). Всегда ≥ 0 если match начинается внутри entity
(т.к. `m_start >= e_offset`).

### `.*` → `\S*` в `full_replace=True`

`\S*` (non-whitespace, zero-or-more) вместо `.*` (greedy, любой символ).
URL не содержит whitespace, поэтому `\S*` match'ит только trailing
non-whitespace символы после pattern prefix, НЕ захватывая пробелы и
текст после ссылки. Существующий check `not compiled.endswith(r"\S+")`
предотвращает дублирование если pattern уже заканчивается на `\S+`.

## Альтернативы

1. **Сохранить старые формулы, поднять defensive validation threshold** —
   не решает проблему, entity всё равно дропается. Отвергнуто.

2. **Использовать `\S+` вместо `\S*`** — `\S+` требует минимум один
   non-whitespace символ после pattern prefix. Если URL точно совпадает с
   pattern (без trailing символов) — match не происходит. Отвергнуто —
   `\S*` (zero-or-more) match'ит и точное совпадение, и trailing символы.

3. **Использовать `\b` (word boundary) вместо `\S*`** — word boundary
   работает для alphanumeric, но URL может содержать `-`, `_`, `.`, `?`,
   `=` которые не являются word characters. `\b` может match'ить
   посередине URL. Отвергнуто — `\S*` более предсказуем.

4. **Изменить `compile_simple("*" → ".*")` на `"*" → "\S*"`** — изменило бы
   семантику simple mode для пользователей которые явно используют `*`.
   Отвергнуто — изменён только `full_replace=True` tail, `*` в simple mode
   остаётся `.*` (ожидающий behavior).

5. **Симметричные формулы для 3a/3b** — 3a сохраняет хвост, 3b сохраняет
   начало. Можно сделать обе формулы сохраняющими начало (или обе хвост).
   Отвергнуто — семантика разная: в 3b entity начинается ДО match
   (выживает начало), в 3a entity начинается ПОСЛЕ начала match (выживает
   хвост). Асимметрия правильная.