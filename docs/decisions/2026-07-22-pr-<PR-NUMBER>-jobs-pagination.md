# ADR — PR <PR-NUMBER>: add pagination to jobs list

## Статус

Accepted — 2026-07-22

## Контекст

telesoft — приложение для замены ссылок в постах Telegram-каналов.
Страница задач (`/jobs`) отображала до 50 записей без пагинации. Если
задач много (100+), пользователь не мог посмотреть старые задачи — они
не отображались.

Backend `GET /api/jobs` уже поддерживал `limit`/`offset`-параметры
(через `Query` в `list_jobs_endpoint`), но `total` в `JobListResponse`
возвращал `len(jobs)` — размер текущей страницы, а не общее количество
matching records. Это баг: фронтенд не мог рассчитать количество
страниц для пагинации (`Math.ceil(total / pageSize)` всегда давало 1,
т.к. `total` был ≤ `limit`).

Тот же баг был в `GET /api/jobs/{id}/logs` — `total` для логов тоже
возвращал `len(logs)`.

Issue #83 просит: исправить `total` (через COUNT-query), добавить
pagination controls на фронтенде (номера страниц 1..N, Prev/Next,
pageSize=20).

## Решение

Разделить запрос данных страницы и подсчёт общего количества
matching records — два SQL-запроса (SELECT для страницы + COUNT(*)
для total), pagination controls с номерами страниц на фронтенде:

1. **`count_jobs` в DB-модели** — `count_jobs(db, channel_id=None,
   status=None) -> int` в `src/telesoft/db/models/job.py`. Аналог
   `list_jobs`, но `SELECT COUNT(*) AS cnt FROM edit_jobs WHERE ...`
   (БЕЗ LIMIT/OFFSET, БЕЗ ORDER BY). Возвращает `int(row["cnt"])`.
   Те же WHERE-фильтры (`channel_id`, `status`) что и `list_jobs`.

2. **`count_logs` в DB-модели** — `count_logs(db, job_id) -> int` в
   `src/telesoft/db/models/log.py`. `SELECT COUNT(*) AS cnt FROM
   edit_logs WHERE job_id = ?`. Возвращает `int(row["cnt"])`.

3. **Fix `GET /api/jobs`** — `list_jobs_endpoint` вызывает
   `count_jobs(db, channel_id, status)` для `total` (вместо
   `len(jobs)`). `JobListResponse(jobs=jobs, total=total)` — `total`
   = общее matching count, `jobs` = страница данных (LIMIT/OFFSET).

4. **Fix `GET /api/jobs/{id}/logs`** — `get_job_logs_endpoint`
   вызывает `count_logs(db, job_id)` для `total` (вместо
   `len(logs)`).

5. **Frontend pagination** — `web/src/routes/jobs/+page.svelte`:
   - `let page = $state(1)`, `const pageSize = 20`.
   - `total = $derived.by(() => localTotal ?? data.total)` — sync с
     refresh (после `refresh()` `localTotal = resp.total`).
   - `totalPages = Math.ceil(total / pageSize)` — `$derived`.
   - `goToPage(next)` → `refresh()` → `api.get('/api/jobs',
     { limit: pageSize, offset: (page-1)*pageSize, status? })`.
   - Controls внизу: `<nav aria-label="Пагинация задач">` с «‹ Пред.» |
     1 2 3 ... N | «След. ›». Текущая страница — `bg-brand-600` +
     `aria-current="page"`. Prev/Next disabled на границах.
   - Pagination рендерится только при `totalPages > 1`.
   - Polling (5s при running) уважает текущую страницу: `refresh()`
     пересчитывает offset на каждом вызове.

6. **`+page.ts` initial load** — `{ limit: 20, offset: 0 }`
   (соответствует `pageSize=20` в `+page.svelte`).

## Альтернативы

1. **"Load more" button** — кнопка «Загрузить ещё» в конце списка,
   подгружает следующую страницу (offset += pageSize) и добавляет к
   существующему списку (append, не replace). Плюсы: нет перехода
   между страницами, контекст сохраняется; нет расчёта `totalPages`.
   Минусы: список растёт без ограничений (DOM-heavy при 1000+ jobs);
   нельзя перейти сразу на последнюю страницу; нет представления
   общего объёма данных. Отвергнуто — issue #83 явно просит «1 2 3
   ... N» (номера страниц).

2. **Infinite scroll** — автозагрузка следующей страницы при
   скролле к концу списка (IntersectionObserver). Плюсы: seamless UX
   (без явных действий), нативный паттерн для mobile. Минусы: нет
   представления общего объёма; нельзя перейти к старым записям сразу
   (только скролл); сложнее тестировать (нужен mock IntersectionObserver
   в vitest); нагрузка на DOM растёт; сложно вернуться на конкретную
   страницу. Отвергнуто — нет явной навигации по страницам, issue
   просит «‹ Пред. | 1 2 3 ... N | След. ›».

3. **Page numbers (выбрано)** — explicit pagination controls с
   номерами страниц 1..N, Prev/Next. Плюсы: пользователь видит
   общий объём (N страниц), может перейти сразу на любую страницу,
   DOM остаётся лёгким (одна страница за раз), легко тестировать
   (клик по «След.» → assert api.get с правильным offset). Минусы:
   два SQL-запроса (SELECT + COUNT) вместо одного; нужно правильно
   считать `total` (fix бага `len(jobs)`). Выбрано — соответствует
   issue #83, явная навигация, простое тестирование.

4. **Cursor-based pagination (keyset)** — вместо OFFSET использовать
   `WHERE id < ? ORDER BY id DESC LIMIT ?` (курсор = последний ID
   предыдущей страницы). Плюсы: стабильный performance при больших
   OFFSET (OFFSET O(N) в SQLite, keyset O(log N)). Минусы: нельзя
   перейти на произвольную страницу (только next/prev); нет
   `totalPages` (нужно отдельное COUNT-query для общего количества);
   сложнее тестировать. Для текущего объёма (100-1000 jobs)
   OFFSET-пагинация достаточно быстрая. Отвергнуто — over-engineering
   для MVP, OFFSET работает.