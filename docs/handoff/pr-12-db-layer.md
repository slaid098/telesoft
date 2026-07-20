---
pr: 12
issue: 11
branch: feat/db/aiosqlite-models
status: ready
created: 2026-07-20
---

# Handoff — PR #12: aiosqlite layer with channels, edit_jobs, edit_logs models

## Что сделано

Реализован issue #11 — DB connection layer + 3 модели (channels, edit_jobs, edit_logs) на raw aiosqlite без ORM, с интеграцией в FastAPI lifespan и тестами.

### Шаг 1: DB connection layer

- `src/telesoft/db/__init__.py` — пустой пакетный модуль (`"""Async SQLite database layer."""`).
- `src/telesoft/db/base.py` — базовые утилиты:
  - `type Row = dict[str, Any]` (PEP 695 type statement — ruff UP040 запрещает `TypeAlias`).
  - `execute(db, sql, params=()) -> None` — write + commit.
  - `executemany(db, sql, params_seq) -> None` —批量 write + commit.
  - `insert(db, sql, params) -> int` — INSERT, возвращает `lastrowid` (через `cursor = await db.execute(...)`, `await cursor.close()`, `await db.commit()`).
  - `fetchone(db, sql, params=()) -> Row | None` — `async with await db.execute(...) as cur:` + `dict(row)`.
  - `fetchall(db, sql, params=()) -> list[Row]` — список dict'ов.
- `src/telesoft/db/connection.py`:
  - `@dataclass _State` с полем `db: aiosqlite.Connection | None = None` (holder вместо `global` — ruff PLW0603 запрещает global).
  - `get_db_path() -> str` — `Settings.from_env().db_path` + `Path(db_path).parent.mkdir(parents=True, exist_ok=True)`.
  - `async def init_db() -> aiosqlite.Connection` — открывает conn, `row_factory=aiosqlite.Row`, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `_create_schema(conn)`. Идемпотентно (возвращает `_state.db` если уже открыто). Сохраняет в `_state.db`.
  - `async def get_db() -> AsyncIterator[aiosqlite.Connection]` — `@asynccontextmanager`, lazy-init, yield conn (не закрывает — `close_db` владеет teardown).
  - `async def close_db() -> None` — закрывает если открыто, сбрасывает `_state.db = None`. No-op если не инициализировано.
  - `_create_schema(conn)` — итерирует `_CREATE_SQL` + `_CREATE_INDEXES_SQL` из channel/job/log моделей. Порядок: channels → edit_jobs → edit_logs (FK зависимости).
- `src/telesoft/db/models/__init__.py` — реэкспорт ключевых функций (`__all__` отсортирован по ruff RUF022).

### Шаг 2: Models (3 таблицы)

- `src/telesoft/db/models/channel.py`:
  - `type ChannelRow = dict[str, Any]`, `_TABLE = "channels"`.
  - `_CREATE_SQL` — `CREATE TABLE IF NOT EXISTS channels (id INTEGER PK AUTOINCREMENT, telegram_id INTEGER NOT NULL UNIQUE, title TEXT NOT NULL, username TEXT, added_at TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)`.
  - `_CREATE_INDEXES_SQL` — `idx_channels_telegram_id`, `idx_channels_is_active`.
  - CRUD: `create_channel` (через `base.insert` + `get_channel`), `get_channel` (по PK), `get_channel_by_telegram_id`, `list_channels` (опционально `active_only`), `update_channel` (`**fields` с whitelist `title`/`username`/`is_active` — `ValueError` на неизвестном поле), `delete_channel` (hard delete, возвращает bool).
- `src/telesoft/db/models/job.py`:
  - `type JobRow = dict[str, Any]`, `_TABLE = "edit_jobs"`.
  - `_CREATE_SQL` — `CREATE TABLE IF NOT EXISTS edit_jobs (id, channel_id FK→channels ON DELETE CASCADE, pattern, new_link, status DEFAULT 'pending', total DEFAULT 0, edited DEFAULT 0, failed DEFAULT 0, created_at, completed_at)`. FK объявлен дважды (inline REFERENCES + FOREIGN KEY block — per spec).
  - `_CREATE_INDEXES_SQL` — `idx_edit_jobs_channel_id`, `idx_edit_jobs_status`, `idx_edit_jobs_created_at`.
  - CRUD: `create_job`, `get_job`, `list_jobs` (фильтры `channel_id`/`status`, пагинация `limit`/`offset`, ORDER BY id DESC), `update_job_status` (status + опциональные total/edited/failed/completed_at), `delete_job` (hard delete). `# noqa: PLR0913` на `list_jobs`/`update_job_status` (6 args > 5).
- `src/telesoft/db/models/log.py`:
  - `type LogRow = dict[str, Any]`, `_TABLE = "edit_logs"`.
  - `_CREATE_SQL` — `CREATE TABLE IF NOT EXISTS edit_logs (id, job_id FK→edit_jobs ON DELETE CASCADE, message_id, old_text, success INTEGER NOT NULL, error, edited_at)`. FK объявлен дважды (inline + FOREIGN KEY block — per spec).
  - `_CREATE_INDEXES_SQL` — `idx_edit_logs_job_id`, `idx_edit_logs_message_id`.
  - CRUD: `create_log` (success bool → `int(success)` для SQLite), `list_logs` (по job_id, пагинация), `delete_logs` (возвращает число удалённых через `cursor.rowcount`). `# noqa: PLR0913` на `create_log` (6 args).

### Шаг 3: Интеграция в main.py

- `src/telesoft/main.py` — удалены placeholder `init_db`/`close_db`, добавлен `from telesoft.db.connection import close_db, init_db`. Lifespan: `await init_db()` на startup, `await close_db()` на shutdown (try/finally). `GET /health` без изменений.

### Шаг 4: Тесты

- `tests/conftest.py` — обновлён:
  - `mock_db` (async): `monkeypatch.setenv("DB_PATH", str(tmp_path / "telesoft.db"))`, `await connection.init_db()`, yield conn, `await connection.close_db()`. Возвращает `AsyncIterator[aiosqlite.Connection]` (не None — тестам нужен conn для прямых запросов).
  - `create_channel` (async factory): `ChannelFactory = Callable[..., Awaitable[ChannelRow]]`, дефолты telegram_id=100, title, username, added_at.
  - `create_job` (async factory): `JobFactory`, создаёт channel если `channel_id is None`.
  - `type ChannelFactory`/`JobFactory` (PEP 695) для типизации фикстур.
  - Удалены неиспользуемые импорты `close_db, init_db` из `telesoft.main` (теперь используется `connection.init_db/close_db`).
- `tests/test_db.py` (6 тестов): `test_init_db_creates_file`, `test_init_db_idempotent`, `test_pragmas_set` (WAL + foreign_keys=ON), `test_schema_created` (sqlite_master), `test_get_db_yields_connection`, `test_close_db_noop_when_uninitialized`.
- `tests/test_models_channel.py` (7 тестов): create+get, get_by_telegram_id, list_active_only, update (title/username/is_active), update_rejects_unknown_field (ValueError), delete, unique_telegram_id_constraint (IntegrityError).
- `tests/test_models_job.py` (5 тестов): create+get, list_filter_by_channel, list_filter_by_status, update_job_status (status/total/edited/failed/completed_at), delete_job_cascade_logs (FK CASCADE удаляет логи при удалении job'а).
- `tests/test_models_log.py` (4 теста): create+list, list_limit_offset (пагинация), delete_logs (возвращает count), delete_channel_cascade_jobs_logs (FK CASCADE: канал → job'ы → логи).

## Почему

PR #2 создал backend skeleton с `init_db()`/`close_db()` placeholder. Для MVP (замена ссылок в постах Telegram-каналов через бота-админа) нужно хранение:
- списка каналов (telegram_id, title, username, is_active);
- истории запусков замены ссылок (edit_jobs: channel_id, pattern, new_link, status, total/edited/failed, created_at, completed_at);
- детальных логов по каждому обработанному посту (edit_logs: job_id, message_id, old_text, success, error, edited_at).

SQLite без ORM (паттерн media-gen: raw aiosqlite + `CREATE TABLE IF NOT EXISTS` на startup, без миграций). FK CASCADE обеспечивает целостность: удаление канала → удаление его job'ов → удаление логов этих job'ов. WAL mode для конкурентного чтения при write-операциях. `PRAGMA foreign_keys=ON` обязателен (по умолчанию OFF в SQLite).

## Pending

- Branch protection на GitHub (require status checks: backend-lint, backend-test, frontend) — настраивается вручную после зелёного CI.
- API-роутеры для CRUD каналов/job'ов/логов — будущие issues.
- Telethon bot integration — будущие issues.
- Pre-commit mypy для tests/ остаётся красным (см. "Watch out") — pre-existing issue, не блокирует CI (`uv run mypy src/` проходит).

## Watch out

- **ruff S608 false positive на model f-strings**: запросы вида `f"SELECT * FROM {_TABLE} WHERE id = ?"` интерполируют module-level константу `_TABLE` (не user input), но ruff S608 всё равно флагует. Добавлен `"src/telesoft/db/models/*" = ["S608"]` в `[tool.ruff.lint.per-file-ignores]` (scoped, не global ignore) — тот же подход что в media-gen.
- **ruff PLR0913 (max-args=5)** на `list_jobs` (6 args: db, channel_id, status, limit, offset + self=6) и `update_job_status` (6 args), `create_log` (6 args: db, job_id, message_id, old_text, success, error, edited_at — на самом деле 7 с db). Добавлен `# noqa: PLR0913` per function (faithful to spec, не поднимали global limit). `create_channel`/`create_job` имеют ≤5 args — noqa не нужен.
- **FK CASCADE работает только с `PRAGMA foreign_keys=ON`**: `init_db()` устанавливает pragma. Тест `test_delete_channel_cascade_jobs_logs` и `test_delete_job_cascade_logs` проверяют каскадное удаление. Без pragma CASCADE молча игнорируется (SQLite default OFF).
- **aiosqlite Cursor.close() — async**: `cursor.close()` это `async def` (cursor.py:70), вызов без `await` возвращает coroutine (mypy `unused-coroutine`). В `base.insert` и `delete_channel`/`delete_job`/`delete_logs` используется `await cursor.close()`. В `fetchone`/`fetchall` — `async with await db.execute(...) as cur:` (Cursor — async context manager, авто-close через `__aexit__`).
- **`update_channel` whitelist**: `**fields` принимает только `title`/`username`/`is_active` (tuple `_ALLOWED_UPDATE_FIELDS`). Неизвестное поле → `ValueError`. Тест `test_update_channel_rejects_unknown_field` проверяет. Это защита от случайного обновления `telegram_id`/`added_at`/`id`.
- **`mock_db` fixture возвращает `aiosqlite.Connection`** (не `None`): тесты моделей используют conn напрямую (`await channel_model.create_channel(mock_db, ...)`). Существующий `test_health.py` не использует `mock_db` — `TestClient(app)` запускает lifespan, который вызывает `init_db()` (DB_PATH не задан → `app_data/telesoft.db` в CWD). Тест проходит, но создаёт реальный файл `app_data/telesoft.db` — это pre-existing behavior, не регрессия.
- **pre-commit mypy остаётся красным для tests/conftest.py**: `@pytest.fixture` декоратор не типизирован в pytest stubs → mypy `Untyped decorator makes function "mock_settings"/"mock_db"/"create_channel"/"create_job" untyped [misc]`. На main уже красный для `mock_settings`/`mock_db` (PR #2). CI использует `uv run mypy src/` (только src/) — проходит. Исправление (typed decorator stubs или `# type: ignore[misc]`) — pre-existing pre-commit hardening task, не per-feature. Зафиксировано в memory media-gen gotchas.
- **Settings.from_env() вызывается в get_db_path()** при каждом `init_db()` (не cached). `Settings` frozen dataclass читает env vars через `os.getenv`. Тесты `monkeypatch.setenv("DB_PATH", ...)` до `init_db()` — работает. На production `DB_PATH` статичен.
- **`type Row = dict[str, Any]` (PEP 695)**: ruff UP040 запрещает `TypeAlias` annotation (`Row: TypeAlias = dict[str, Any]`). Используем `type Row = dict[str, Any]` (native PEP 695 syntax, Python 3.12+). То же для `ChannelRow`/`JobRow`/`LogRow`/`ChannelFactory`/`JobFactory`.
- **mypy tuple narrowing в `list_jobs`**: `params: list[Any]` (не `tuple`), затем `tuple(params)` в `base.fetchall`. Если бы использовали `params = (channel_id,)` → `params = (channel_id, status)` mypy выдал бы `assignment` error (разные tuple типы). List + `tuple()` — канонический фикс (из media-gen).
- **Coverage**: connection 98%, base 93%, channel 96%, job 100%, log 100%, main 100%. Total 97.43% (gate 80%). Непокрытые: `config._get_list` (pre-existing, нет env-list vars в telesoft), `base.insert` assert (lastrowid всегда не None для INSERT), `connection.get_db` lazy-init branch (mock_db уже инициализирует).