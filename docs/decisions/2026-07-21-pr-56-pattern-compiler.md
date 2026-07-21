---
pr: 56
issue: 55
status: Accepted
created: 2026-07-21
---

# ADR — PR 56: pattern compiler + preview endpoint + pattern library DB

## Статус

Accepted (2026-07-21). Реализует issue #55 (backend часть). Frontend (PR#2) и seed built-in patterns (PR#3) — отдельно, согласно плану в issue.

## Контекст

Замена ссылок работала только через raw regex — обычный юзер не может составить паттерн (не знает regex-синтаксис). Нужно:

1. **Simple mode** — `*` → `.*`, `re.escape()` остальных частей.
2. **Pattern Library** — встроенные + кастомные паттерны в БД.
3. **Preview** — 3 реальных поста "было → стало" до запуска job (dry-run).
4. **Keep tail** — опция "сохранить хвост" (заменить только префикс, `-s-*` оставить).

Это PR#1 из 3: только backend. Frontend и seed — отдельно.

### Спека issue #55 содержит неточность

Пример `compile_simple("https://t.me/bot?start=flow-*")` → `https://t\.me/bot\?start=flow-.*` (без `\-`) НЕточный: Python 3.12+ `re.escape()` экранирует `-` тоже → реальный output `https://t\.me/bot\?start=flow\-.*`. Это correct/safe behavior ( `-` может быть спецсимволом в character classes). Тесты отражают реальный output. Зафиксировано в handoff Watch out.

## Решение

**8 изменений (4 коммита):**

1. **`core/pattern_compiler.py` (новый)** — 3 функции: `compile_simple` (split `*` → escape → join `.*`), `apply_keep_tail` (`_TAIL_RE` обрезает 5 форм хвоста), `compile_pattern` (оркестратор по mode + keep_tail). Unknown mode → `ValueError` (router → 422).

2. **`core/link_replacer.py`** — `preview_replace(messages, pattern, new_link, limit=3)` + хелпер `_preview_one`. Dry-run: фильтрует через `find_posts_with_pattern`, берёт `limit`, строит before/after в памяти (без Telethon edit). `match_source` = "text" | "entity" (text приоритетнее, как в `replace_link_in_post`).

3. **`db/models/pattern.py` (новый)** — таблица `link_patterns` (id, name, pattern, description, is_builtin, created_at) + индекс `idx_link_patterns_name`. CRUD: `create_pattern` (`# noqa: PLR0913`), `get_pattern`, `list_patterns`, `delete_pattern` (raise `PermissionError` для builtin → 403).

4. **`db/connection.py` + `db/models/__init__.py`** — регистрация `pattern_model._CREATE_SQL` + `_CREATE_INDEXES_SQL` в `_create_schema`, экспорт `PatternRow` + 4 функций.

5. **`schemas/job.py`** — `ReplaceLinkRequest` +`mode: str = "advanced"`, +`keep_tail: bool = False` (backward compat). Новые: `PreviewRequest`, `PreviewResponse`, `PreviewItem`, `PatternCreateRequest`, `PatternResponse` (`from_row`), `PatternListResponse`.

6. **`api/routers/patterns.py` (новый)** — `GET /api/patterns`, `POST /api/patterns` (is_builtin=0 всегда, regex validation 422), `DELETE /api/patterns/{id}` (403 builtin, 404 absent). Router-level `Depends(require_auth)`.

7. **`api/routers/jobs.py`** — новый `POST /api/channels/{id}/preview-replace` (compile → validate → get_last_messages → preview_replace(3) → PreviewResponse с compiled_pattern). Обновлён `replace-link`: `compile_pattern(pattern, mode, keep_tail)` → `validate_pattern(compiled)` → сохраняет **скомпилированный** regex в `edit_jobs.pattern`.

8. **`main.py`** — зарегистрирован `patterns_router`.

## Альтернативы

1. **`before`/`after` только ссылка vs полный текст** — спека issue #55 говорит "before/after — только ссылка (не весь пост)". Для entity-матчей реализовано так (before = entity.url). Для text-матчей реализация возвращает полный текст с встроенной ссылкой (т.к. `replace_link` работает на полном тексте, вычленение только ссылки — extra work). Плюс: проще реализация, frontend может подсветить ссылку. Минус: больше payload. Отклонено вычленение ссылки — frontend (PR#2) сделает visual highlighting.

2. **`apply_keep_tail` regex vs string operations** — regex `_TAIL_RE` обрабатывает 5 форм хвоста. Альтернатива — string `endswith` / `rsplit`. Плюс regex: один pass, declarative. Минус: 5 альтернатив в pattern (нужно покрыть escaped + raw forms). Принят regex — compact и тестируемый.

3. **`delete_pattern` return False vs raise для builtin** — raise `PermissionError` даёт router'у явный signal для 403 (vs 404 если просто не удалил). Альтернатива — return False и router проверяет is_builtin отдельно. Принят raise — separation of concerns (model знает про builtin constraint, router маппит в HTTP).

4. **Compiled regex в DB vs raw pattern** — `edit_jobs.pattern` хранит скомпилированный regex (после `compile_pattern`), не raw ввод. Плюс: transparency в логах, runner использует финальный regex. Минус: backward-incompatible для existing jobs (старые имеют raw). Принят compiled — frontend (PR#2) покажет compiled regex для transparency.

5. **Preview limit в router vs в request** — `preview_replace` limit=3 hardcoded в router (не из `PreviewRequest.limit`). `PreviewRequest.limit` контролирует fetch из Telegram (default 100). Альтернатива — `PreviewRequest.preview_limit` поле. Отклонено — 3 пары достаточно для preview, extra поле — over-engineering.

6. **`db_handle` fixture в conftest vs per-file** — `test_api_jobs.py` уже имеет свой `db_handle`. Новый `test_api_patterns.py` дублирует (не вынесен в conftest). Плюс: scoped changes (не трогает conftest). Минус: дублирование. Отклонено вынесение — минимальный diff, можно отрефакторить отдельно.

7. **Pattern compiler как separate module vs в link_replacer** — `pattern_compiler.py` отдельный модуль (не в `link_replacer.py`). Плюс: single responsibility, тестируемость. Отклонено объединение — `link_replacer` уже 200+ строк, compiler — отдельная concern.

## Последствия

- `edit_jobs.pattern` теперь хранит **скомпилированный** regex (для новых jobs через `replace-link` endpoint). Existing jobs (на main) имеют raw pattern — backward-incompatible, но jobs одноразовые (не re-run), так что не критично.
- `ReplaceLinkRequest` расширен `mode` + `keep_tail` с backward-compat defaults — existing клиенты работают без изменений.
- Новая таблица `link_patterns` — миграция не нужна (idempotent `CREATE TABLE IF NOT EXISTS` в `_create_schema`).
- `preview_replace` — pure dry-run (не мутирует message, не вызывает Telethon) — безопасно для частых вызовов.
- Frontend (PR#2) должен: radio simple/advanced, Pattern Library selector, Preview modal, keep_tail checkbox, учитывать что `JobResponse.pattern` — regex.
- Seed (PR#3) — built-in patterns через `create_pattern(is_builtin=1)` (seed-скрипт вне этого PR).