---
pr: 60
issue: 59
branch: feat/db/seed-builtin-patterns
status: ready
created: 2026-07-21
---

# Handoff — PR 60: seed built-in link patterns

## Что сделано

Реализован issue #59 — seed 4 built-in link patterns при инициализации
БД. 3 коммита, 4 файла изменено / 1 создан, 189 unit tests green (184 →
189, +5 новых), ruff/mypy green, coverage 94.70% (gate 80%).

### Шаг 1: `seed_builtin_patterns` в `src/telesoft/db/models/pattern.py` — commit 1

- Новый module-level кортеж `_BUILTIN_PATTERNS` с 4 паттернами:
  1. `Telegram bot links` — `https://t\.me/\w+\?start=\S+`
  2. `Telegram bot links (with groups)` — `https://t\.me/(\w+)\?(start=\S+)`
  3. `Telegram channel post links` — `https://t\.me/(\w+)/(\d+)`
  4. `Generic URLs` — `https?://\S+`
- Новая функция `seed_builtin_patterns(db) -> int` — идемпотентная:
  для каждого built-in проверяет `SELECT id WHERE name=? AND is_builtin=1`,
  если нет — вставляет через `create_pattern(is_builtin=1)`. Возвращает
  количество вставленных (0 на повторном запуске).
- Хелпер `_now_iso()` (локальная копия `now_iso` из `schemas/job.py`) —
  избегает circular import `schemas.job` ↔ `db.models` (`schemas/job.py`
  импортирует `PatternRow` из `db.models`).
- Вызов seed добавлен в `src/telesoft/db/connection.py::_create_schema`
  после `db.commit()` (после создания таблиц + индексов).
- `src/telesoft/db/models/__init__.py` — экспорт `seed_builtin_patterns`.

### Шаг 2: Тесты — commit 2

- `tests/test_seed_patterns.py` (новый, 5 тестов):
  - `test_seed_inserts_four_builtin_patterns` — fresh DB → 4 built-ins
  - `test_seed_is_idempotent` — повторный `seed_builtin_patterns` → 0 inserted
  - `test_seed_preserves_custom_patterns` — кастомный (is_builtin=0) не затирается
  - `test_seed_does_not_collide_with_custom_name` — кастомный с тем же name не блокирует seed
  - `test_seeded_builtin_cannot_be_deleted` — seeded builtin → `PermissionError`
- `tests/test_api_patterns.py` — обновлены под seed:
  - `test_patterns_list_empty` → `test_patterns_list_seeded` (4 built-ins, names check)
  - `test_patterns_create_and_list` — id=5 (после 4 built-ins), total=5, patterns[0].is_builtin=True
  - `test_patterns_delete_custom` — total=4 после delete (built-ins остаются)
  - `test_patterns_delete_builtin_403` — использует seeded built-in (не создаёт свой)
  - Удалён unused import `pattern_model`
- `tests/test_models_pattern.py` — обновлены под seed:
  - `test_create_pattern_returns_row` — id=5 (после 4 built-ins)
  - `test_list_patterns_ordered_by_id` — len=6, проверка `rows[-2]`/`rows[-1]`

### Шаг 3: `.env.example` — commit 3 (вместе с docs)

- Комментарий про built-in patterns после `DB_PATH`.

## Почему

Pattern Library UI (PR#58) пуста без seed — юзеру нечего выбирать в
Library mode. 4 паттерна покрывают наиболее частые кейсы замены ссылок
в Telegram: bot deep-links (с/без capture groups), post links, generic
URLs.

- **Идемпотентность по name+is_builtin** — позволяет юзеру удалить
  built-in через прямой SQL (если очень нужно) и seed не вставит его
  обратно на следующем init. Также защищает от коллизий с кастомными
  паттернами с тем же name (custom с `name="Telegram bot links"` не
  блокирует seed, т.к. проверяется `is_builtin=1`).
- **Seed в `_create_schema`** — вызывается один раз при `init_db()`,
  после создания таблиц. Не отдельный lifecycle hook, не migration —
  часть schema setup.
- **`is_builtin=1` → нельзя удалить** — защита от случайного удаления
  seed-данных (PR#56 уже реализовал `PermissionError` → 403 в router).

## Pending

- **Frontend (PR#58)** — Pattern Library UI уже есть, теперь показывает
  4 built-in patterns после первого запуска backend. Проверить UI flow
  вручную после merge.
- **Integration tests** — 4 ошибки pre-existing на main (FloodWait,
  expired session), не затронуты. Главный агент должен прогнать
  `uv run pytest -m integration` с валидными creds.
- **Migration для existing DBs** — на existing production DB с пустой
  `link_patterns` таблицей, seed вставит 4 patterns при следующем
  `init_db()` (app restart). Если на existing DB уже есть кастомные
  patterns — seed добавит built-ins после них (ORDER BY id).

## Watch out

- **Circular import `schemas.job` ↔ `db.models`** — `schemas/job.py`
  импортирует `PatternRow` из `db.models.pattern`. Если `pattern.py`
  импортирует `now_iso` из `schemas.job` — circular. Решение: локальная
  копия `_now_iso()` в `pattern.py` (тот же формат `%Y-%m-%dT%H:%M:%SZ`).
  Не вынесено в общий utils — minimal diff, можно отрефакторить отдельно.
- **`test_patterns_list_empty` переименован в `test_patterns_list_seeded`**
  — semantic change: fresh DB больше не пустая. Если другие тесты
  полагались на empty list — нужно обновить (проверено: только этот тест).
- **`test_patterns_create_and_list` — id=5** (не 1) — первый custom
  pattern получает id=5 после 4 seeded built-ins. Если тесты
  полагаются на id=1 — нужно обновить.
- **`test_patterns_delete_builtin_403`** — теперь использует seeded
  built-in (через `GET /api/patterns`), а не создаёт свой через
  `pattern_model.create_pattern(is_builtin=1)`. Это тестирует реальный
  seed flow.
- **Seed вызывается в `_create_schema`** (не в отдельной функции) —
  значит, любой тест с `mock_db` fixture уже имеет 4 built-ins. Тесты
  моделей, которые проверяют `len(rows) == N` после insert, должны
  учитывать +4 (см. обновлённый `test_list_patterns_ordered_by_id`).
- **`_BUILTIN_PATTERNS` — tuple of dicts** (не list of dataclasses) —
  minimal structure, `create_pattern` принимает kwargs. Можно вынести
  в dataclass `BuiltinPattern`, но over-engineering для 4 статичных
  entries.
- **Seed не использует `INSERT OR IGNORE`** — использует `SELECT` +
  `create_pattern`. Причина: `create_pattern` возвращает row (нужно для
  consistency), `INSERT OR IGNORE` не возвращает inserted row. Плюс:
  один кодpath для built-in и custom. Минус: 2 запроса per pattern
  (SELECT + INSERT) вместо 1 — но 4 patterns, negligible.