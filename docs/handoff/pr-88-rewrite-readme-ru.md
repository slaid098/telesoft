---
pr: 88
issue: 87
title: Rewrite README in Russian
type: docs
---

# Handoff — PR#88: Rewrite README in Russian

## Что сделано

- `README.md` полностью переписан на русский (255 строк, было 181 English)
- 15 секций по структуре из issue #87:
  1. `# telesoft` + tagline на русском
  2. `## Описание` — workflow, 3 режима, preservation, link_preview
  3. `## Архитектура` — **Mermaid flowchart** (вместо ASCII-арт), GitHub рендерит нативно
  4. `## Возможности` — 11 буллетов (каналы CRUD, 3 режима, pattern library, preview-confirm-run, link_preview, full/partial replace, preservation UTF-16, entity URLs, пагинация, mobile responsive)
  5. `## Стек` — 3 подкатегории (Backend / Frontend / Tooling)
  6. `## Требования`
  7. `## Быстрый старт (Docker)` — `docker compose up --build -d`, порт 8080
  8. `## Локальная разработка` — backend uv + frontend npm
  9. `## Переменные окружения` — таблица 15 vars (все из `.env.example` + `config.py`)
  10. `## Настройка бота` — BotFather, my.telegram.org, StringSession сниппет, ограничение ботов
  11. `## Тестирование` — unit (232), integration (4, `-m integration`), frontend (43), E2E mobile (7)
  12. `## Структура проекта` — обновлённое дерево (pattern_compiler, patterns router, pattern model, Dockerfile.nginx, nginx.conf)
  13. `## Деплой (production)` — nginx :8080, внешний reverse proxy, bind-mount, VITE_API_BASE
  14. `## Ограничения` — актуальные: бот не листает историю, нет редактирования канала в UI, нет retry/delete
  15. `## Лицензия` — MIT

- `docs/project-map/README.md` — обновлены 2 упоминания README (теперь «на русском, 15 секций» вместо «overview, getting started, env vars table»), `last_updated` → PR#87

## Почему

README устарел на ~30 PR:
- Порты неверные: README говорил `:8000`/`:3000`, реально nginx `:8080` (PR#54)
- "List of post URLs" удалено (PR#34/62), теперь один `post_link` + `limit`
- StringSession claim устарел (PR#48 добавил `TELEGRAM_SESSION_STRING`)
- 6 крупных фич не описаны: 3 режима замены, pattern library, preview-confirm-run, link_preview чекбокс, пагинация задач, форматирование preservation
- 3 env vars отсутствовали: `TELEGRAM_SESSION_STRING`, `TELEGRAM_REQUEST_DELAY`, `TELEGRAM_EDIT_DELAY`
- Тесты: не упомянуты integration и Playwright E2E
- Project structure: нет `pattern_compiler.py`, `patterns.py` router, `pattern.py` model, `Dockerfile.nginx`
- Удаление канала в UI есть, но README говорил «не реализовано»

## Pending

- Нет. Docs-only PR, архитектурных решений нет (ADR не нужен).

## Watch out

- **Тест-каунты**: README говорит «~232 backend unit», «~43 frontend», «7 E2E mobile» — числа точные на момент PR#88. При добавлении тестов обновить.
- **Mermaid рендеринг**: GitHub рендерит Mermaid нативно в README, но другие viewers (VS Code preview, некоторые git UI) могут не рендерить — показывают raw code block. Это OK для GitHub-first README.
- **`.env.example` имеет 15 vars**: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `HOST`, `PORT`, `LOG_LEVEL`, `DB_PATH`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_SESSION_STRING`, `SESSION_PATH`, `JOBS_MAX_CONCURRENCY`, `TELEGRAM_REQUEST_DELAY`, `TELEGRAM_EDIT_DELAY`. Таблица в README включает все 15. При добавлении новой env var — обновить таблицу + `.env.example` + `config.py`.
- **`VITE_API_BASE=""`** — установлен в `docker-compose.yml` build args для web, НЕ в `.env.example` (это build-time arg, не runtime env). В README секция «Деплой» упоминает.
- **issue #87 упоминало «~300 строк»** — реально 255 строк. Структура полная, но compact. Не стоит раздувать ради цифры.