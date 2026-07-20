# ADR — PR <PR-NUMBER>: aiosqlite layer with channels, edit_jobs, edit_logs models

## Статус

Accepted (2026-07-20)

## Контекст

PR #2 создал backend skeleton (`src/telesoft/main.py` с lifespan placeholder, `config.py`). БД нет — `init_db()`/`close_db()` не реализованы. Для MVP (замена ссылок в постах Telegram-каналов) нужно хранить: список каналов (telegram_id, title, username), историю запусков замены (edit_jobs с pattern/new_link/status/progress), детальные логи по каждому посту (edit_logs с message_id/old_text/success/error).

Референс паттернов — `slaid098/media-gen` (`src/media_gen/db/`): raw aiosqlite без ORM, `type Row = dict[str, Any]` (PEP 695), `_CREATE_SQL` + `_CREATE_INDEXES_SQL` константы, идемпотентный `init_db()` через `CREATE TABLE IF NOT EXISTS`, `@dataclass _State` holder вместо `global` (ruff PLW0603).

## Решение

Реализованы 4 шага спецификации issue #11:

1. **DB connection layer** (`src/telesoft/db/{__init__,base,connection}.py`): `type Row = dict[str, Any]`, базовые `execute`/`executemany`/`insert`/`fetchone`/`fetchall`, singleton через `_State.db`, `init_db()` (WAL + foreign_keys=ON + `_create_schema`), `get_db()` async context manager, `close_db()`. `get_db_path()` читает `Settings.from_env().db_path` + `mkdir(parents=True, exist_ok=True)`.
2. **3 модели** (`src/telesoft/db/models/{channel,job,log}.py`): `channels` (telegram_id UNIQUE, is_active), `edit_jobs` (FK→channels CASCADE, status/total/edited/failed), `edit_logs` (FK→edit_jobs CASCADE, message_id/old_text/success/error). CRUD функции принимают `aiosqlite.Connection` первым аргументом (no global state), возвращают `dict[str, Any]`.
3. **Интеграция в main.py**: `from telesoft.db.connection import close_db, init_db`, lifespan startup → `init_db()`, shutdown → `close_db()`.
4. **Тесты** (22 теста): `test_db.py` (6: file/idempotent/pragmas/schema/get_db/noop-close), `test_models_channel.py` (7: CRUD + UNIQUE + whitelist), `test_models_job.py` (5: CRUD + filters + CASCADE), `test_models_log.py` (4: CRUD + pagination + CASCADE channel→jobs→logs).

Ключевые отклонения от спецификации (зафиксированы в handoff, раздел "Watch out"):
- `ruff S608` per-file-ignore для `src/telesoft/db/models/*` (false positive на f-strings с `_TABLE` константой).
- `ruff PLR0913` noqa на `list_jobs`/`update_job_status`/`create_log` (>5 args, faithful to spec).
- `mock_db` fixture возвращает `aiosqlite.Connection` (не `None`) — тестам нужен conn для прямых запросов к моделям.
- `update_channel` whitelist (`title`/`username`/`is_active`) с `ValueError` на неизвестном поле — защита целостности, явная в коде (не магическая).
- `tests/conftest.py` типизирован (PEP 695 `ChannelFactory`/`JobFactory`), но pre-commit mypy остаётся красным на `@pytest.fixture` (pre-existing, не блокирует CI).

## Альтернативы

- **ORM vs raw aiosqlite**: выбран raw aiosqlite (паттерн media-gen). Альтернативы — SQLAlchemy 2.0 async, Tortoise ORM + aerich. ORM добавляет dependency + migration overhead для MVP с 3 таблицами. Raw SQL с `_CREATE_TABLE IF NOT EXISTS` проще и достаточен.
- **Миграции vs идемпотентный init**: выбран идемпотентный `init_db()` (CREATE TABLE IF NOT EXISTS на startup). Альтернатива — alembic миграции. Для MVP без schema evolution — overkill. Миграции можно добавить позже при необходимости.
- **`global` vs `@dataclass _State`**: выбран `_State` holder (ruff PLW0603 запрещает global). Альтернатива — module-level `db: aiosqlite.Connection | None = None` без dataclass, но ruff PLW0603 флагует re-assignment.
- **`mock_db` возвращает conn vs None**: выбран conn (тесты моделей вызывают `model.fn(mock_db, ...)`). Альтернатива — None + `async with get_db() as db` в каждом тесте — многословнее, дублирует логику.
- **`update_channel` whitelist vs принимать всё**: выбран whitelist (`title`/`username`/`is_active`). Альтернатива — принимать любые поля (риск обновить `telegram_id`/`added_at`/`id`). Whitelist явный и безопасный.
- **`type` statement (PEP 695) vs `TypeAlias`**: выбран `type Row = dict[str, Any]` (ruff UP040 запрещает `TypeAlias`). PEP 695 native syntax, Python 3.12+, читаемее.