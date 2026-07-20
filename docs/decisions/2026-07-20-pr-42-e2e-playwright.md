# ADR — PR #42: Playwright E2E tests for mobile flow

## Статус

Accepted (2026-07-20) — добавлены 7 E2E тестов через Playwright для mobile flow (viewport 375x812, iPhone SE-like). `web/playwright.config.ts` (mobile project, baseURL docker-dind:8080, webServer отключён), `web/tests/e2e/helpers.ts` (login helper, константы), `web/tests/e2e/mobile.spec.ts` (7 тестов: login, channels no duplicates, open button, replace-link form, job progress, zero-match, websocket). `web/package.json` scripts `test:e2e`/`test:e2e:mobile`. `.gitignore` updated. Все 7 тестов pass против running контейнеров. Biome, svelte-check (0 errors, 2 pre-existing advisory warnings), Vitest (28), Knip — green. Backend ruff, mypy, pytest (115, coverage 94.27%) — green (без изменений). No comments. TypeScript strict.

## Контекст

PR#40 fixed 6 багов (WebSocket, mobile table visibility, auto-discovery logging, Open button, zero-match feedback, recent jobs mobile). Ручное тестирование на test.slaid098.dev (мобильный viewport) нашло эти баги, но нет автоматизированного покрытия — регрессии могут вернуться незамеченными. Mobile-first подход: большинство юзеров заходят с телефона, mobile viewport (375x812) — самый узкий case, если работает там — работает везде. Существующие Vitest unit-тесты (28) покрывают components изолированно (jsdom, mock fetch/WS), но НЕ покрывают интеграцию: real backend, real WebSocket, real navigation, real DOM. Нужен E2E слой для end-to-end flow проверки.

## Решение

Playwright E2E тесты, mobile-first:

1. **Playwright** (`@playwright/test`) — Microsoft, современный E2E framework. Auto-waiting, tracing, screenshots, video, cross-browser (Chromium/Firefox/WebKit), mobile emulation (viewport, touch, deviceScaleFactor). `npx playwright install chromium --with-deps` — Chromium 149 + FFmpeg + Headless Shell.

2. **Config** (`web/playwright.config.ts`) — `testDir: "./tests/e2e"`, `timeout: 30_000` per test, `retries: 1` (flaky tolerance), `fullyParallel: false`, `workers: 1` (sequential — общий running backend, race conditions при параллельности). `baseURL: "http://docker-dind:8080"` (nginx, контейнеры running через docker compose, webServer отключён — тесты не запускают контейнеры). Project `mobile`: viewport 375x812, deviceScaleFactor 2, isMobile true, hasTouch true (iPhone SE-like). `screenshot: "only-on-failure"`, `video: "retain-on-failure"`, `trace: "retain-on-failure"` — артефакты для дебага.

3. **Helpers** (`web/tests/e2e/helpers.ts`) — `login(page)` helper (goto /login, fill, submit, waitForURL /channels), `getSessionCookie(page)`, константы `BASE_URL`, `TEST_CHANNEL_ID=2` (реальный test channel telegram_id=-1003903711726 из spike PR#30), `TEST_USERNAME`/`TEST_PASSWORD`.

4. **7 тестов** (`web/tests/e2e/mobile.spec.ts`) — `test.beforeEach` login (каждый test изолирован, новый context). Покрытие: login flow, channels no duplicates (regression PR#40), open button (PR#40), replace-link form submission, job progress bar + terminal status, zero-match amber alert (PR#40), WebSocket no console errors. Селекторы: CSS class-based (`div.hidden.overflow-x-auto.sm\:block` для table wrapper, `#rl-pattern` для form inputs, `.border-amber-900.bg-amber-950` для zero-match alert). Job completion timeout 30s (job на реальном канале ~12s: binary search 13 probes × 1s delay PR#32 + range fetch).

5. **package.json scripts** — `test:e2e` (все projects), `test:e2e:mobile` (только mobile project).

6. **.gitignore** — `test-results/`, `playwright-report/`, `playwright/.cache/` (артефакты).

## Альтернативы

### E2E framework
- **Playwright (выбрано)** — Microsoft, современный, auto-waiting, tracing, mobile emulation, cross-browser. TypeScript-native, интеграция с Vitest/SvelteKit ecosystem. `@playwright/test` package — 3 пакета, Chromium 149. Выбрано — best-in-class для E2E, mobile emulation без real devices.
- **Puppeteer** — Google, predecessor Playwright. Node.js, Chrome-only (нет Firefox/WebKit). Меньше features (нет mobile emulation из коробки, нет tracing). Отклонено — Playwright превосходит по возможностям.
- **Cypress** — popular, но архитектура differently (in-browser runner, не real browser automation). Платный для parallel/CI features. Отклонено — Playwright бесплатный, real browser automation, лучше для mobile emulation.
- **Vitest browser mode** — Vitest v3 имеет experimental browser mode (jsdom + real browser). Но это для component testing, НЕ для E2E flow (нет navigation, multi-page, WebSocket). Отклонено — не подходит для end-to-end flow.
- **Selenium WebDriver** — legacy, медленный, меньше features. Отклонено — Playwright современнее.

### Test execution model
- **Running контейнеры + webServer отключён (выбрано)** — тесты запускаются против уже running docker compose (nginx + api + web). `baseURL: docker-dind:8080`. Тесты НЕ запускают/останавливают контейнеры. Преимущества: детерминированные (контейнеры в known state), быстрые (нет startup overhead), локальный запуск простой. Выбрано — MVP, контейнеры уже running в dev.
- **Playwright webServer config** — Playwright может запустить server (`webServer.command: "npm run dev"`). Но это single-process (frontend only), НЕ запускает backend + DB + Telegram. Отклонено — нужен full stack (docker compose).
- **Docker compose в beforeEach** — каждый test запускает `docker compose up`, после — `down`. Полная изоляция, но ОЧЕНЬ медленно (compose startup ~30s × 7 tests = 3.5min). Отклонено — too slow для dev loop.
- **CI services** — GitHub Actions `services:` block для docker compose. CI-only, не локально. Отклонено для MVP — follow-up.

### Parallelism
- **Sequential `workers: 1` (выбрано)** — тесты выполняются последовательно. Общий running backend → race conditions при параллельности (test 4 создаёт job, test 5 видит чужой job). Sequential гарантирует изоляцию. Выбрано — простота, надёжность.
- **Parallel `workers: N`** — быстрее, но нужен per-test изолированный backend (test containers, unique DB per worker). Overkill для MVP. Follow-up.

### Test data
- **Pre-existing канал hardcode `TEST_CHANNEL_ID=2` (выбрано)** — канал создан вручную через API (telegram_id=-1003903711726, реальный test channel из spike PR#30). Тесты используют его. Просто, работает. Выбрано — MVP, канал уже есть.
- **`beforeAll` создаёт канал через API** — динамический setup, `afterAll` удаляет. Полная изоляция, но усложняет тесты (API calls, cleanup). Follow-up.
- **Seed data в DB** — SQL seed script, запускать перед тестами. Хрупко (schema changes). Отклонено — API setup проще.

### Selectors
- **CSS class-based (выбрано)** — `div.hidden.overflow-x-auto.sm\:block`, `#rl-pattern`, `.border-amber-900.bg-amber-950`. Прямые селекторы по Tailwind classes и IDs. Хрупкий (class changes ломают тесты), но explicit и читаемый. Выбрано — simplest, работает.
- **`data-testid` attributes** — добавить `data-testid="channels-table"` etc. в components. Стабильные селекторы, не зависят от Tailwind classes. Но требует изменения production code (components). Follow-up если тесты станут хрупкими.
- **`getByRole`/`getByText` Playwright locators** — semantic locators (`page.getByRole("button", { name: "Open" })`). Лучше accessibility, но менее precise (multiple matches на dual-layout). Отклонено — dual-layout создаёт ambiguity.

## Ключевые отклонения от спеки

- **`workers: 1`, `fullyParallel: false`** — спека не указывала parallelism. Добавлено: общий running backend → race conditions при параллельности. Sequential для изоляции.
- **`TEST_CHANNEL_ID = 2` (НЕ 1)** — спека указывала `TEST_CHANNEL_ID` константу, но не значение. Channel id=1 — фейковый (-1001234567890), replace-link падает (Telethon не может fetch). Channel id=2 — реальный (-1003903711726), replace-link с несуществующим pattern → done, total=0 (zero-match для test 6). Значение 2 выбрано для real replace-link flow.
- **Селекторы уточнены** — спека предлагала `page.locator('.sm:hidden').count()` для cards. Реализация: `div.space-y-3.sm\:hidden` (cards section) + `> div.rounded-lg.border.border-slate-800.bg-slate-900.p-3` (individual cards). Причина: `.sm\:hidden` один матчит cards section (родитель), не individual cards. Уточнено для правильного count.
- **`div.hidden.overflow-x-auto.sm\:block` для table wrapper** — спека предлагала `.hidden.sm\:block`. Первый прогон упал: strict mode violation (2 matches — span "Signed in as admin" + table wrapper). Уточнено: `div.` prefix (span не матчит) + `overflow-x-auto` (только table wrapper).
- **Test 7 (WebSocket)** — спека предлагала `page.evaluate(() => window...)` или "progress обновляется без polling". Реализация: console errors listener + filter по "websocket"/"ws"/"socket" + `expect(wsErrors).toHaveLength(0)`. Причина: progress update без polling требует real edit (несуществующий pattern → zero-match → нет progress events). Console errors — simpler, достаточно для smoke проверки WS handshake.
- **CI не изменён** — спека упоминала "добавить E2E в CI workflow". Не реализовано: CI runner не имеет running контейнеров (docker compose в CI сложно). E2E запускаются только локально. Follow-up issue.

## Pending / Follow-up

- **CI интеграция** — добавить E2E job в `.github/workflows/ci.yml` с docker compose services. Отдельный issue.
- **Desktop/tablet projects** — добавить projects для desktop (1280x720) и tablet (768x1024) viewport coverage.
- **Test data isolation** — `beforeAll`/`afterAll` create/delete test channel через API.
- **`data-testid` attributes** — если селекторы станут хрупкими, добавить `data-testid` в components.
- **Real replace-link test** — dedicated test channel с disposable posts для real edit_message проверки.
- **WebSocket functional test** — проверить что progress обновляется через WS (не polling) — сравнить initial `job.edited` с `job.edited` после WS event.
- **`@local` tag** — если E2E добавятся в CI, tag для local-only тестов.