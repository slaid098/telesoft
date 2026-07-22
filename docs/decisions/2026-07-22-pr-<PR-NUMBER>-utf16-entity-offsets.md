# ADR — PR <PR-NUMBER>: UTF-16 code units for entity offset math

## Статус

Accepted — 2026-07-22

## Контекст

telesoft заменяет ссылки в постах Telegram-каналов. Посты могут содержать
formatting (bold/italic) через `MessageEntity*`. При replace нужно
сохранить formatting — `_adjust_entity_offsets` пересчитывает offsets
entities после замены текста.

PR#70 исправил математические формулы для cases 3a/3b, но НЕ исправил
**единицы измерения**. Telegram MTProto `MessageEntity*` `offset` /
`length` — **UTF-16 code units** (с surrogate pairs для non-BMP U+10000+).
Python `re.finditer` возвращает code-point offsets, `len(str)` —
code-point length. `_adjust_entity_offsets` смешивал единицы:
- `entity.offset` / `entity.length` из Telegram → UTF-16
- `re.finditer(pattern, text)` → code-point offsets
- `len(new_link)` → code-point length

Каждый non-BMP символ (emoji 👇 = U+1F447, 🔥, и т.д.):
- 1 Python code point (`len("👇") == 1`)
- 2 UTF-16 code units (surrogate pair 0xD83D 0xDC47)

Для текста с N emoji перед или внутри entity математика уезжает на N
символов → entity становится короче на N → user видит "последние N
символов ссылки нежирные".

Production репродукция (канал `znak_tut_nowbot`, формат
`**Написать👇**\n\n**tg://resolve?...**`): 4 emoji 👇👇👇👇 перед
URL в bold entity → bold покрывает "Написать 👇👇👇👇
https://t.me/mynewbot?start" — последние 4 символа `=app` нежирные.

Telethon source подтверждает UTF-16 контракт:
- `telethon/helpers.py:add_surrogate()` —
  "SMP -> Surrogate Pairs (Telegram offsets are calculated with these)".
- `telethon/extensions/markdown.py` —
  "Work on byte level with the utf-16le encoding to get the offsets right."

Дополнительно: если match полностью поглощает entity (`m_start <
e_offset` AND `m_end > e_end`) — ни один существующий branch не
срабатывал, entity оставался с устаревшим offset/length.

## Решение

### UTF-16 code units для всего offset math

`_adjust_entity_offsets` теперь работает в UTF-16 code units:

```python
from telethon.helpers import add_surrogate

sur_text = add_surrogate(text)
sur_new_link = add_surrogate(new_link)
new_link_len = len(sur_new_link)
matches = list(re.finditer(pattern, sur_text))   # UTF-16 offsets
new_text_sur = re.sub(pattern, sur_new_link, sur_text)
```

Все формулы (cases 1, 2, 3a, 3b, 5) используют `new_link_len` (UTF-16).
Defensive validation:
`new_entity.offset + new_entity.length > len(new_text_sur)` (UTF-16).

Возвращаемые entities имеют UTF-16 offsets (как ожидает Telegram).
`new_text` для `edit_message` вычисляется отдельно в `replace_link_in_post`
через `replace_link` (code points) — `del_surrogate` в `link_replacer.py`
не нужен.

### Case 5: match полностью поглощает entity

```python
elif m_start < e_offset and m_end > e_end:
    e_offset = m_start
    e_length = new_link_len
```

Entity выживает с offset = match start, length = new_link length —
покрывает весь replacement. Проверяется ПОСЛЕ cases 3a/3b (порядок
важен — 5 идёт последним, иначе перехватит 3a/3b).

## Альтернативы

1. **Code-point-only с поправкой на non-BMP** — вручную считать
   non-BMP символы между смещениями и добавлять N к code-point offsets.
   Отвергнуто — дублирует логику `add_surrogate`, хрупко (нужно
   считать символы в каждом диапазоне), легко ошибиться. Telethon уже
   предоставляет `add_surrogate` / `del_surrogate` именно для этого.

2. **Ручной пересчёт** — конвертировать entity offsets из UTF-16 в
   code points на входе, делать math в code points, конвертировать
   обратно в UTF-16 на выходе. Отвергнуто — две конверсии на entity,
   больше мест для багов. Проще делать весь math в UTF-16 (одна
   конверсия text на входе).

3. **Игнорировать emoji** — оставить code-point math, документировать
   что emoji не поддерживаются. Отвергнуто — production каналы
   активно используют emoji в постах (👇, 🔥, ✅, и т.д.), баг
   проявляется у реальных пользователей.

4. **Использовать `len(text.encode('utf-16le')) // 2` вместо
   `add_surrogate`** — ручной расчёт UTF-16 length без surrogate
   encoding. Отвергнуто — `re.finditer` работает на `str` (code
   points), нужен именно surrogate-encoded `str` чтобы regex offsets
   были UTF-16. `add_surrogate` даёт именно это: `str` где non-BMP
   символы заменены на surrogate pairs.

5. **Вернуть `new_text` из `_adjust_entity_offsets`** — изменить
   сигнатуру на `(entities, text, pattern, new_link) -> tuple[list,
   str]`. Отвергнуто — `replace_link_in_post` уже вычисляет `new_text`
   через `replace_link` (строка 169), дублирование не нужно.
   `del_surrogate` не импортируется в `link_replacer.py`.