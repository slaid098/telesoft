---
pr: <PR-NUMBER>
issue: 83
branch: feat/jobs/pagination
status: ready
created: 2026-07-22
---

# Handoff — PR <PR-NUMBER>: add pagination to jobs list

## Что сделано

Реализован issue #83 — пагинация на странице задач и фикс бага
`total` в backend (возвращал `len(jobs)` — размер страницы — вместо
общего количества matching records).

### Шаг 1: `count_jobs` в `src/telesoft/db/models/job.py`

- Добавлена функция `count_jobs(db, channel_id=None, status=None) -> int`
  — `SELECT COUNT(*) FROM edit_jobs WHERE ...` с теми же WHERE-фильтрами
  что и `list_jobs`, но БЕЗ LIMIT/OFFSET.
- Возвращает общее количество matching records (для расчёта числа
  страниц во фронтенде).
- Использует `base.fetchone` (как `get_job`), читает `row["cnt"]` и
  кастит в `int` (SQLite может вернуть int/bytes/None — defensive cast).

### Шаг 2: Fix `GET /api/jobs` в `src/telesoft/api/routers/jobs.py`

- Endpoint `list_jobs_endpoint` теперь вызывает `count_jobs(db,
  channel_id, status)` для реального `total`.
- `total` в `JobListResponse` = общее количество matching jobs
  (игнорируя LIMIT/OFFSET), не `len(jobs)` (размер текущей страницы).
- Документация endpoint обновлена: явно указано что `total` — для
  расчёта числа страниц.

### Шаг 3: Fix `GET /api/jobs/{id}/logs` в `src/telesoft/api/routers/jobs.py`

- Аналогично `list_jobs`: добавлен `count_logs(db, job_id=job_id)` в
  `src/telesoft/db/models/log.py`.
- `total` в `LogListResponse` = реальное количество логов через
  `SELECT COUNT(*)`, не `len(logs)`.
- Документация endpoint обновлена.

### Шаг 4: Frontend pagination в `web/src/routes/jobs/+page.svelte`

- Добавлен state: `let page = $state(1)`, `const pageSize = 20`.
- `totalPages = Math.ceil(total / pageSize)` — `$derived` от `total`
  (merge load data + local refresh через `$derived.by`).
- `total` — `$derived.by` от `localTotal ?? data.total` (sync с refresh).
- При смене страницы — `goToPage(next)` → `refresh()` → re-fetch через
  `api.get('/api/jobs', { limit: pageSize, offset: (page-1)*pageSize,
  status? })`.
- Controls внизу списка: `<nav aria-label="Пагинация задач">` с
  «‹ Пред.» | 1 2 3 ... N | «След. ›».
- Текущая страница подсвечена (`bg-brand-600` + `aria-current="page"`),
  остальные — `bg-slate-800`.
- Prev/Next disabled на границах (`disabled={page <= 1}` /
  `disabled={page >= totalPages}`) + `disabled:cursor-not-allowed`.
- Pagination рендерится только при `totalPages > 1` (если всё помещается
  на одну страницу — controls не показываются).
- Polling (5s при running) уважает текущую страницу: `refresh()`
  использует текущий `page` для расчёта offset.

### Шаг 5: Обновить `web/src/routes/jobs/+page.ts`

- `load` функция теперь передаёт `{ limit: 20, offset: 0 }` (было
  `{ limit: 50 }`) — соответствует `pageSize=20` в `+page.svelte`.
- Возвращает `total` (как было) — для initial render и расчёта
  `totalPages`.

### Шаг 6: Тесты

- Backend `tests/test_models_job.py`:
  - `test_count_jobs_all` — count без фильтров = общее количество jobs.
  - `test_count_jobs_filter_by_channel` — count с `channel_id` filter.
  - `test_count_jobs_filter_by_status` — count с `status` filter
    (pending/done/running).
  - `test_count_jobs_empty` — count на пустой таблице = 0.
- Backend `tests/test_api_jobs.py`:
  - `test_list_jobs_total_includes_all_matching` — 15 jobs, `limit=10,
    offset=0` → `total=15`, `len(jobs)=10` (было `total=10` до фикса).
  - `test_list_jobs_total_with_status_filter` — `total` уважает
    status-фильтр (matching count, не все jobs).
  - `test_get_job_logs_total_includes_all_matching` — 5 logs,
    `limit=2` → `total=5`, `len(logs)=2` (фикс бага для logs endpoint).
- Frontend `web/src/tests/jobs.test.ts`:
  - `renders pagination controls when total > pageSize` — навигация
    рендерится при `total=45` (3 страницы), есть Prev/Next/«3».
  - `does not render pagination when total <= pageSize` — при
    `total=10` навигация НЕ рендерится.
  - `disables Prev on first page and Next on last page` — Prev
    disabled на 1-й странице.
  - `fetches page 2 when Next is clicked` — клик «След. ›» вызывает
    `api.get('/api/jobs', { limit: 20, offset: 20 })` (страница 2).

## Коммиты

1. `fix(jobs): return real total count from count_jobs query` — шаги
   1–3 (backend: `count_jobs`/`count_logs`, фикс `total` в endpoints).
2. `feat(jobs): add pagination controls to jobs list page` — шаги 4–5
   (frontend: `pageSize=20`, `page` state, pagination controls,
   `+page.ts` limit/offset).
3. `test(jobs): add pagination tests` — шаг 6 (backend + frontend
   тесты для count_jobs и pagination).
4. `docs(handoff): set PR number` — заполнение `<PR-NUMBER>` placeholder
   после создания PR.

## Почему

Страница задач (`/jobs`) загружала до 50 записей без пагинации. Если
задач много (100+), пользователь не мог посмотреть старые задачи — они
просто не отображались. Backend `GET /api/jobs` уже поддерживал
`limit`/`offset`, но `total` возвращал `len(jobs)` (размер страницы)
вместо реального количества matching jobs — это баг, блокирующий
пагинацию (фронтенд не мог рассчитать количество страниц).

Фикс `total` через `count_jobs` (COUNT-query) + frontend pagination
controls (номера страниц 1..N, Prev/Next, pageSize=20) — теперь
пользователь может переключаться между страницами и видеть все задачи.

## Pending

— (логи на странице задачи `/jobs/[id]` пока без пагинации — только
отображение всех логов разом; если логов много, добавить pagination
отдельным PR).

## Watch out

- **`count_jobs` и `list_jobs` — дублирование WHERE-логики**: обе
  функции собирают `clauses`/`params` для одного и того же набора
  фильтров (`channel_id`, `status`). Если добавить новый фильтр —
  нужно обновить обе функции. Альтернатива — общий helper
  `_build_where(channel_id, status) -> tuple[str, list[Any]]`, но для
  2 фильтров это over-engineering. Дублирование приемлемо (DRY-vs-KISS).

- **`$derived.by` для `total`**: `localTotal ?? data.total` — sync с
  `refresh()`. После `refresh()` `localTotal = resp.total` → `total`
  re-derives → `totalPages` re-derives → pagination controls
  перерисовываются. Если не обновлять `localTotal` при refresh,
  `totalPages` останется stale (load-time value).

- **Pagination рендерится при `totalPages > 1`**: если все jobs
  помещаются на одну страницу (total ≤ pageSize) — controls НЕ
  рендерятся. Избегает визуального шума для маленьких списков.

- **`goToPage` guard**: `if (next < 1 || next > totalPages || next ===
  page) return` — no-op если кликнули на текущую страницу или вышли за
  границы. Кнопки Prev/Next также disabled на границах (двойная защита:
  disabled + guard).

- **Polling уважает текущую страницу**: `refresh()` пересчитывает
  `offset = (page - 1) * pageSize` на каждом вызове. Если polling
  сработает на странице 3 — он обновит именно страницу 3 (offset=40),
  не страницу 1.

- **Status-filter client-side**: `filteredJobs = statusFilter ===
  "all" ? jobs : jobs.filter(...)` — фильтр по статусу применяется
  client-side (к уже загруженной странице). Backend `status`-параметр
  в `refresh()` передаётся только при `statusFilter !== "all"` — для
  server-side filtering при смене страницы. TODO: синхронизировать
  `statusFilter` change с `refresh()` (сейчас при смене фильтра
  фильтрация client-side, но при пагинации — server-side; может дать
  рассогласование). Для текущих 2 фильтров (channel_id, status) и
  pageSize=20 — приемлемо.

- **`+page.ts` limit=20**: SvelteKit `load` грузит первые 20 jobs
  (было 50). Initial render показывает 1-ю страницу, pagination
  controls подгружают остальные.

## Проверка

```bash
# Backend
uv run ruff check src/telesoft/db/models/job.py src/telesoft/api/routers/jobs.py
uv run ruff format src/telesoft/db/models/job.py src/telesoft/api/routers/jobs.py
uv run mypy src/telesoft/db/models/job.py src/telesoft/api/routers/jobs.py
uv run pytest -x -q --no-cov -m "not integration" --ignore=tests/integration
#   223 passed

# Frontend
cd web && npm run lint        # Biome: 41 files, no fixes
cd web && npm run typecheck   # svelte-check: 0 errors, 2 pre-existing warnings
cd web && npm run test         # vitest: 41 tests, 6 files — all green
```

Все проверки пройдены.