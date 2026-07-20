---
pr: PLACEHOLDER
issue: 41
branch: test/e2e/playwright-mobile
status: ready
created: 2026-07-20
---

# Handoff — PR #PLACEHOLDER: Playwright E2E tests for mobile flow

## Что сделано

Реализован issue #41 — добавлены автоматизированные E2E тесты через Playwright для mobile flow (viewport 375x812, iPhone SE-like). Цель — проверить фиксы PR#40 (WebSocket, mobile table visibility, Open button, zero-match feedback) и предотвратить регрессии. 4 файла: `web/playwright.config.ts` (config, mobile project), `web/tests/e2e/helpers.ts` (login helper, константы), `web/tests/e2e/mobile.spec.ts` (7 тестов), `web/package.json` (scripts `test:e2e`/`test:e2e:mobile`), `web/.gitignore` (test-results, playwright-report, playwright/.cache). No comments. TypeScript strict. Biome, svelte-check (0 errors, 2 pre-existing advisory warnings), Vitest (28 тестов), Knip — green. Backend ruff, mypy, pytest (115 тестов, coverage 94.27%) — green (без изменений, E2E не трогает backend). Все 7 E2E тестов pass против running контейнеров (docker-dind:8080, nginx → api + web).

### Установка и config — `web/playwright.config.ts`

- `npm install -D @playwright/test` (3 пакета: `@playwright/test`, `playwright`, `playwright-core`).
- `npx playwright install chromium --with-deps` — Chromium 149.0.7827.55 + FFmpeg + Chrome Headless Shell в `~/.cache/ms-playwright/`.
- Config: `testDir: "./tests/e2e"`, `timeout: 30_000`, `retries: 1`, `fullyParallel: false`, `workers: 1` (sequential — тесты используют общий running backend, параллельность создаст race conditions на jobs/channels). `baseURL: "http://docker-dind:8080"` (nginx, контейнеры running через docker compose, webServer НЕ запускается). `use.screenshot: "only-on-failure"`, `video: "retain-on-failure"`, `trace: "retain-on-failure"`. Project `mobile`: viewport 375x812, deviceScaleFactor 2, isMobile true, hasTouch true.

### Хелперы — `web/tests/e2e/helpers.ts`

- `BASE_URL = "http://docker-dind:8080"` — nginx endpoint (контейнеры running).
- `TEST_CHANNEL_ID = 2` — реальный тестовый канал (telegram_id=-1003903711726, из spike PR#30). Channel id=1 — фейковый (-1001234567890), replace-link на нём падает (Telethon не может fetch). Channel id=2 — реальный, replace-link с несуществующим pattern → done, total=0 (zero-match scenario для test 6).
- `TEST_USERNAME = "admin"`, `TEST_PASSWORD = "admin"` — из `.env` контейнера api.
- `login(page, username, password)` — `page.goto("/login")`, fill `#username`/`#password`, click submit, `waitForURL("**/channels")`.
- `getSessionCookie(page)` — читает cookie "session" из context (SessionMiddleware Starlette, PR#18).

### E2E тесты — `web/tests/e2e/mobile.spec.ts`

7 тестов, каждый изолирован (новый context через `test.beforeEach` → login):

1. **login flow redirects to channels** — после login (beforeEach), проверка `page.url` matches `/\/channels$/`, `h1` содержит "Channels". 698ms.
2. **channels list has no duplicates on mobile** — `page.goto("/channels")`, table wrapper (`div.hidden.overflow-x-auto.sm\:block`) `toBeHidden()`, cards section (`div.space-y-3.sm\:hidden`) `toBeVisible()`, cards count ≥1, `table` `toBeHidden()`. Селекторы уточнены после первого прогона (`.hidden.sm\:block` матчит 2 элемента — span "Signed in as admin" в layout + table wrapper → strict mode violation; добавлен `div.` prefix + `overflow-x-auto` для уникальности). 723ms.
3. **open button on channel card navigates to detail** — `page.goto("/channels")`, `a[href="/channels/2"]` с `hasText: "Open"` в cards section, click → `waitForURL("**/channels/2")`, `form` visible, `#rl-pattern` visible. 794ms.
4. **replace-link form submission redirects to job detail** — `page.goto("/channels/2")`, fill `#rl-pattern` = `https://nonexistent-zzz-test-12345\.example\.com` (несуществующий pattern → zero-match), `#rl-new-link` = `https://new.example.com`, `#rl-limit` = `3`, click submit → `waitForURL(/\/jobs\/\d+$/, timeout: 30s)`, `h1` содержит "Job #". 1.3s.
5. **job detail shows progress bar and reaches terminal status** — submit form (как test 4), `waitForURL(/\/jobs\/\d+$/)`, progress bar (`.h-2.w-full.overflow-hidden.rounded-full.bg-slate-800`) visible, status badge visible, `toContainText(/done|failed|cancelled/i, timeout: 30s)` — ждёт terminal status. 14.3s (job работает ~12s: binary search 13 probes × 1s delay + range fetch PR#32).
6. **zero-match feedback shows amber alert when total is zero** — submit form (несуществующий pattern), `waitForURL`, status badge `toContainText(/done/i, timeout: 30s)`, amber alert (`.border-amber-900.bg-amber-950`) visible, `toContainText(/No posts matched/i)`. 13.9s.
7. **websocket connection establishes without console errors** — listener `page.on("console", msg => if error: push)`, submit form, `waitForURL`, `waitForFunction` проверяет `window.WebSocket` defined, `waitForTimeout(2000)` для WS handshake, filter console errors по "websocket"/"ws"/"socket", `expect(wsErrors).toHaveLength(0)`. 3.6s.

### package.json scripts

- `"test:e2e": "playwright test"` — запустить все E2E тесты (все projects).
- `"test:e2e:mobile": "playwright test --project=mobile"` — только mobile project.

### .gitignore

- Добавлены `test-results/`, `playwright-report/`, `playwright/.cache/` — артефакты Playwright (скриншоты, видео, trace, HTML report, browser cache).

## Почему

PR#40 fixed 6 багов (WebSocket, mobile table visibility, auto-discovery logging, Open button, zero-match feedback, recent jobs mobile). Контейнеры пересобраны, tunnel поднят на test.slaid098.dev. Нужно автоматизированное покрытие для предотвращения регрессий — ручное тестирование на mobile viewport после каждого PR трудозатратно. Mobile-first E2E через Playwright: viewport 375x812 (iPhone SE-like), isMobile + hasTouch для реалистичного mobile окружения. 7 тестов покрывают полный mobile flow: login → channels list (no duplicates regression PR#40) → open channel → replace-link form → job detail (progress bar, zero-match feedback) → WebSocket (no console errors). Тесты запускаются против running контейнеров (docker-dind:8080) — НЕ запускают контейнеры сами (webServer config отключён), что упрощает локальный запуск и делает тесты детерминированными (контейнеры уже running, тесты только упражняют UI).

## Pending

- **CI интеграция** — E2E тесты НЕ запускаются в CI (`.github/workflows/ci.yml` не изменён). Причина: CI runner не имеет running контейнеров (docker compose в CI сложно — нужен services, healthchecks, seed data). Для MVP E2E запускаются только локально (`npm run test:e2e`). Follow-up: добавить E2E job в CI с docker compose services (как `services:` в workflow) — отдельный issue.
- **Больше projects (desktop, tablet)** — сейчас только mobile project (375x812). Добавить desktop (1280x720) и tablet (768x1024) для coverage desktop flow. Follow-up.
- **Test data isolation** — тесты используют pre-existing канал (id=2, создан вручную через API). Если канал удалить — тесты упадут. Follow-up: `beforeAll` создает тестовый канал через API, `afterAll` удаляет. Пока — ручной setup.
- **`@local` tag** — спека упоминала `@local` tag для исключения из CI. Не реализовано (CI и так не запускает E2E). Если добавим E2E в CI — добавить tag для local-only тестов.
- **Real replace-link test** — тесты используют несуществующий pattern (zero-match scenario). Не проверяют real edit (замена ссылки в реальном посте Telegram). Причина: edit_message на test channel меняет реальный пост — побочные эффекты. Follow-up: dedicated test channel с disposable posts.
- **WebSocket functional test** — test 7 проверяет отсутствие console errors, НЕ проверяет что WS реально доставляет progress events. Follow-up: проверить что progress обновляется через WS (не polling) — сравнить initial `job.edited` с `job.edited` после WS event.

## Watch out

- **`baseURL: http://docker-dind:8080`** — тесты запускаются в opencode container, docker-dind — DinD host (Docker-in-Docker). `localhost:8080` НЕ работает из opencode container (nginx проброшен на DinD host, не на opencode). Если запускать с другой машины — изменить baseURL на `http://localhost:8080` или tunnel URL.
- **Контейнеры должны быть running** — `docker compose up --build` ДО запуска `npm run test:e2e`. Если контейнеры не running — `page.goto` упадёт с connection refused. webServer config отключён намеренно (контейнеры управляются отдельно).
- **`TEST_CHANNEL_ID = 2`** — hardcode. Канал должен существовать в БД (telegram_id=-1003903711726, реальный test channel из spike PR#30). Channel id=1 — фейковый (-1001234567890), replace-link на нём падает (Telethon не может fetch сообщения с несуществующего канала → job failed). Channel id=2 — реальный, replace-link с несуществующим pattern → done, total=0 (zero-match, идеально для test 6).
- **`workers: 1`, `fullyParallel: false`** — sequential execution. Тесты используют общий running backend (docker-dind:8080). Параллельность создаст race conditions: test 4 создаёт job, test 5 может увидеть чужой job. Sequential гарантирует изоляцию. Для параллельности нужен per-test изолированный backend (test containers) — overkill для MVP.
- **`.hidden.sm\:block` strict mode violation** — первый прогон упал: `.hidden.sm\:block` матчит 2 элемента (span "Signed in as admin" в layout + table wrapper). Playwright strict mode падает на multiple matches. Фикс: `div.hidden.overflow-x-auto.sm\:block` — добавлен `div.` prefix (span не матчит) + `overflow-x-auto` (только table wrapper имеет). Аналогично cards section: `div.space-y-3.sm\:hidden` (не просто `.sm\:hidden`).
- **Job completion timeout 30s** — test 5/6 ждут terminal status (done/failed/cancelled) с timeout 30s. Job на реальном канале (id=2) с limit=3 занимает ~12s (binary search 13 probes × 1s delay PR#32 + range fetch). Если канал медленный / FloodWait — может занять дольше. 30s — баланс. Если тесты падают по timeout — увеличить или использовать mock backend.
- **`retries: 1`** — Playwright автоматически retry failed тесты 1 раз. Помогает с flaky tests (network, timing). Если тест падает 2 раза подряд — реальный баг.
- **Biome trailing newline** — `helpers.ts` после первого `npm run lint` ругался на missing trailing newline. `npm run format` добавил. Run `npm run format` после каждого edit (паттерн из PR#24).
- **Knip green без изменений** — `knip.json` `entry` не включает `tests/e2e/` (Playwright tests не part of SvelteKit build). Knip не анализирует `tests/` — только `src/`. `playwright.config.ts` в корне `web/` — Knip `project: ["src/**/*.{svelte,ts,js}"]` не включает root config files. Нет need в knip ignores.
- **svelte-check 0 errors** — `playwright.config.ts` и `tests/e2e/*.ts` НЕ проверяются svelte-check (только `src/`). TypeScript strict в tsconfig применяется, но svelte-check не запускается на `tests/`. Biome проверяет все `.ts` файлы (включая tests/) — green.
- **Pre-existing advisory warnings** — `state_referenced_locally` на `jobs/[id]/+page.svelte` строки 10-11 (PR#26 documented as intentional). НЕ фиксятся в этом PR.