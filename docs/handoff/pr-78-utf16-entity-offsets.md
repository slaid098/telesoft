---
pr: 78
issue: 77
branch: fix/replace/utf16-entity-offsets
status: ready
created: 2026-07-22
---

# Handoff — PR 78: UTF-16 code units for entity offset math + case 5

## Что сделано

Реализован issue #77 — исправление root cause потери форматирования
(bold/italic) при замене ссылок в постах с emoji (non-BMP символами,
например 👇 U+1F447).

1. **`src/telesoft/core/link_replacer.py`** — `_adjust_entity_offsets`
   теперь работает в UTF-16 code units:
   - Импорт `from telethon.helpers import add_surrogate`.
   - В начале функции:
     - `sur_text = add_surrogate(text)` — конвертация text в UTF-16.
     - `sur_new_link = add_surrogate(new_link)` — конвертация new_link.
     - `new_link_len = len(sur_new_link)` — UTF-16 length.
     - `matches = list(re.finditer(pattern, sur_text))` — regex на
       surrogate-encoded text → offsets в UTF-16 code units.
     - `new_text_sur = re.sub(pattern, sur_new_link, sur_text)` —
       substitution в UTF-16.
   - Все формулы (cases 1, 2, 3a, 3b) используют `new_link_len` вместо
     `len(new_link)`.
   - Defensive validation:
     `new_entity.offset + new_entity.length > len(new_text_sur)` —
     сравнение с UTF-16 длиной post-substitution text.
   - Возвращаемые entities имеют UTF-16 offsets (как ожидает Telegram).
   - `del_surrogate` НЕ импортирован — `replace_link_in_post` использует
     `replace_link` для получения `new_text` в code points (нужно для
     `edit_message`).

2. **Case 5 добавлен** в `_adjust_entity_offsets` — match полностью
   поглощает entity (`m_start < e_offset` AND `m_end > e_end`):
   ```python
   elif m_start < e_offset and m_end > e_end:
       e_offset = m_start
       e_length = new_link_len
   ```
   Entity выживает с offset=match start, length=new_link length —
   покрывает весь replacement.

3. **`replace_link_in_post` НЕ изменён** — `new_text` уже вычисляется в
   code points через `replace_link` (строка 169) и передаётся в
   `edit_message`. Entities возвращаются с UTF-16 offsets (Telegram's
   native unit). Сигнатура `_adjust_entity_offsets` осталась
   `(entities, text, pattern, new_link) -> list[Any]` — `new_text`
   отдельно не возвращается.

4. **3 regression теста** в `tests/test_link_replacer.py`:
   - `test_adjust_entity_offsets_emoji_before_bold_entity` — 1 emoji 👇
     перед bold link, advanced mode `tg://\S*`, new_link `https://new.io`.
     Entity (Bold offset=0, length=47 UTF-16) → offset=0, length=25 UTF-16
     (покрывает "Написать👇 https://new.io").
   - `test_adjust_entity_offsets_multiple_emoji_bold_entity` — 4 emoji
     👇👇👇👇, pattern `https?://\S*`, new_link
     `https://t.me/mynewbot?start=app`. Entity → offset=0, length=40
     UTF-16 (покрывает "👇👇👇👇 https://t.me/mynewbot?start=app"
     включая `=app`).
   - `test_adjust_entity_offsets_emoji_case3b_greedy` — emoji + Simple
     mode `*` (compile_pattern с `full_replace=True`, но pattern уже
     заканчивается на `.*` → `\S*` tail НЕ добавляется, остаётся
     greedy `.*`). Match поглощает trailing " end" → case 3b. Entity →
     offset=0, length=24 UTF-16 (покрывает "👇 https://t.me/mynewbot").
   - Все тесты дополнительно проверяют `bold_region.endswith(new_link)`
     декодируя surrogate-encoded post-substitution text slice —
     подтверждает что entity покрывает ВСЮ новую ссылку.

5. **Все 38 существующих тестов** проходят без изменений — ASCII-only
   text где code-point == UTF-16, формулы не меняются.

## Почему

Telegram MTProto `MessageEntity*` `offset`/`length` — **UTF-16 code
units** (с surrogate pairs для non-BMP U+10000+). Python `re.finditer`
возвращает code-point offsets, `len(str)` — code-point length.
`_adjust_entity_offsets` смешивал единицы измерения: брал UTF-16 entity
offsets из Telegram, но code-point offsets из `re.finditer` и `len()`.

Каждый non-BMP символ (emoji) перед или внутри entity:
- 1 Python code point (`len("👇") == 1`)
- 2 UTF-16 code units (surrogate pair 0xD83D 0xDC47)

→ математика уезжает на N символов (N = количество emoji) → entity
становится короче на N → user видит "последние N символов ссылки
нежирные".

Production репродукция (канал `znak_tut_nowbot`, формат
`**Написать👇**\n\n**tg://resolve?...**`): 4 emoji → bold покрывает
"Написать 👇👇👇👇 https://t.me/mynewbot?start" — последние 4 символа
`=app` нежирные. После фикса bold покрывает "Написать 👇👇👇👇
https://t.me/mynewbot?start=app" — вся ссылка жирная.

Telethon source подтверждает UTF-16 контракт:
- `telethon/helpers.py:add_surrogate()` —
  "SMP -> Surrogate Pairs (Telegram offsets are calculated with these)".
- `telethon/extensions/markdown.py` —
  "Work on byte level with the utf-16le encoding to get the offsets right."

## Pending

- **E2E проверка на production** — backend-фикс математически корректен,
  но требует проверки на реальном канале (`-1003903711726`) с постами
  где emoji пересекаются с bold/italic entity и заменяемой ссылкой.

- **Посты 140, 141, 143 испорчены** (PR#68 Pending) — literal `**` в
  `message.message` после предыдущих edit'ов. Backend-фикс НЕ
  восстанавливает испорченные посты — нужно переопубликовать вручную.

## Watch out

- **`del_surrogate` НЕ нужен в `link_replacer.py`** — `new_text` для
  `edit_message` вычисляется в `replace_link` (code points). Entities
  остаются в UTF-16 (Telegram native unit). Если будущий код захочет
  вернуть `new_text` из `_adjust_entity_offsets` — нужно
  `del_surrogate(new_text_sur)`.

- **`new_link` с non-BMP символами** — `add_surrogate(new_link)`
  корректно обрабатывает emoji в new_link (редко для URL, но возможно).
  `new_link_len = len(sur_new_link)` — UTF-16 length.

- **Case 5 vs case 3a/3b** — case 5 (match полностью поглощает entity)
  проверяется ПОСЛЕ cases 3a/3b. Если match начинается до entity и
  заканчивается после — cases 3a (m_end <= e_end) и 3b (m_start >=
  e_offset) НЕ срабатывают, доходит до case 5. Порядок branch'ей важен:
  5 идёт последним, иначе перехватит случаи 3a/3b.

- **`compile_simple("*" → ".*")` НЕ изменён** — `*` в simple mode всё
  ещё компилируется в `.*` (greedy). `full_replace=True` tail `\S*`
  добавляется ТОЛЬКО если pattern НЕ заканчивается на `.*` или `\S+`.
  Если пользователь явно использует `*` в simple mode — pattern уже
  заканчивается на `.*` → `\S*` НЕ добавляется → greedy `.*` match'ит
  trailing text. Это ожидаемое поведение (PR#70 не менял его).

- **Тест 3 (case3b_greedy) использует greedy `.*`** —
  `compile_pattern("https://old.example.com/bot?start=flow-*", "simple",
  full_replace=True)` → `https://old\.example\.com/bot\?start=flow\-.*`
  (greedy, `\S*` tail НЕ добавляется т.к. pattern уже заканчивается на
  `.*`). Match поглощает trailing " end" → case 3b. Это правильный
  сценарий для теста case 3b с emoji.