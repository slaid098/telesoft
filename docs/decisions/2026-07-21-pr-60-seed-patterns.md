---
pr: 60
issue: 59
status: Accepted
created: 2026-07-21
---

# ADR — PR 60: seed built-in link patterns

## Статус

Accepted (2026-07-21). Реализует issue #59 (PR#3 из 3 — финальный).
Зависит от PR#56 (pattern library DB + CRUD) и PR#58 (frontend UI).

## Контекст

PR#56 добавил таблицу `link_patterns` с CRUD. PR#58 добавил UI для
Pattern Library (dropdown выбора паттернов). Сейчас таблица пуста —
юзеру нечего выбирать в Library mode. Нужно добавить seed built-in
паттернов при инициализации БД — 4 паттерна для наиболее частых случаев
замены ссылок в Telegram.

### Требования из issue #59

- 4 built-in паттерна (Telegram bot links, with groups, channel post
  links, generic URLs)
- `is_builtin=1` — нельзя удалить (через API → 403, уже реализовано в
  PR#56)
- Идемпотентность — повторный seed не дублирует
- seed не затирает кастомные паттерны (`is_builtin=0`)
- Вызов после создания таблиц в `init_db`

## Решение

**3 изменения (2 коммита + docs):**

1. **`db/models/pattern.py`** — module-level кортеж `_BUILTIN_PATTERNS`
   (4 dicts) + функция `seed_builtin_patterns(db) -> int`. Идемпотентная:
   для каждого built-in проверяет `SELECT id WHERE name=? AND is_builtin=1`,
   если нет — `create_pattern(is_builtin=1, created_at=_now_iso())`.
   Возвращает количество вставленных. Хелпер `_now_iso()` — локальная
   копия `now_iso` из `schemas/job.py` (избегает circular import).

2. **`db/connection.py`** — вызов `pattern_model.seed_builtin_patterns(db)`
   в `_create_schema` после `db.commit()` (после создания таблиц +
   индексов).

3. **`db/models/__init__.py`** — экспорт `seed_builtin_patterns`.

4. **`.env.example`** — комментарий про built-in patterns после
   `DB_PATH`.

5. **Тесты** — `tests/test_seed_patterns.py` (5 новых), обновлены
   `tests/test_api_patterns.py` (4 теста) и `tests/test_models_pattern.py`
   (2 теста) под seed.

## Альтернативы

1. **Идемпотентность по `name+is_builtin` vs `INSERT OR IGNORE` vs
   count-based** — выбрано `SELECT WHERE name=? AND is_builtin=1` +
   `create_pattern`. Альтернативы:
   - `INSERT OR IGNORE` с UNIQUE constraint на `(name, is_builtin)` —
     minimal SQL, но не возвращает inserted row, нужен отдельный
     `get_pattern` после. Также требует миграции (UNIQUE constraint).
   - `count WHERE is_builtin=1` — если 0, вставить все; иначе skip.
     Проблема: если юзер удалил один built-in через прямой SQL, seed не
     вставит его обратно (count=3, не 0). Не self-healing.
   - Выбранный подход — per-pattern check, self-healing (если один
     удалён, seed вставит только его), работает без schema changes.
   Минус: 2 запроса per pattern (SELECT + INSERT). Для 4 patterns —
   negligible.

2. **Seed в `_create_schema` vs отдельный lifecycle hook vs migration** —
   выбрано в `_create_schema` (после `db.commit()`). Альтернативы:
   - Отдельная функция `seed_db()` вызывается из `init_db` после
     `_create_schema` — separation of concerns (schema vs data). Но
     `_create_schema` уже называется "create schema" а делает commit —
     semantic blur. Принято: seed — часть schema setup (built-ins —
     "default schema data").
   - Migration (alembic) — over-engineering для MVP (нет migration
     framework, см. PR#12 ADR).
   - Lifespan startup hook (в `main.py`) — отдельный call site, можно
     забыть при тестах. Seed в `_create_schema` гарантирует что любой
     `init_db` (test, production) имеет built-ins.

3. **`_now_iso()` локальная копия vs вынести в `utils/time.py`** —
   выбрано локальная копия. Альтернатива: `src/telesoft/utils/time.py`
   с `now_iso()` и импорт из обоих `schemas/job.py` и `db/models/pattern.py`.
   Плюс: DRY. Минус: new module + refactor `schemas/job.py` (out of
   scope for this PR). Принято: локальная копия (2 строки), refactor
   отдельно.

4. **`_BUILTIN_PATTERNS` tuple of dicts vs dataclass vs list of
   `PatternCreateRequest`** — выбрано tuple of dicts. Альтернативы:
   - `dataclass BuiltinPattern(name, pattern, description)` — type
     safety, но 4 статичных entries — over-engineering.
   - `list[PatternCreateRequest]` — Pydantic model, но `is_builtin` не
     в `PatternCreateRequest` (custom-only). Нужен новый schema.
   Принято: tuple of dicts — minimal, readable.

5. **Seed patterns hardcoded vs env-configurable** — выбрано hardcoded.
   Альтернатива: env var `BUILTIN_PATTERNS_JSON` для кастомизации. Но
   4 паттерна — stable set, не требует кастомизации. Если понадобится
   — отдельный PR.

## Последствия

- Любой `init_db()` (test, production) теперь вставляет 4 built-in
  patterns. Тесты, которые проверяют empty `link_patterns` или
  `id=1` для первого custom — должны учитывать seed (обновлено в этом
  PR).
- На existing production DB с пустой `link_patterns` — seed вставит 4
  patterns при следующем app restart. Если есть кастомные — built-ins
  добавятся после них (ORDER BY id).
- `seed_builtin_patterns` — public API (экспортирован из
  `db.models`), может вызываться вручную (например, в migration
  скриптах).
- `_now_iso()` дублирует `now_iso()` из `schemas/job.py` — known
  duplication, можно отрефакторить в `utils/time.py` отдельно.