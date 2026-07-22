# ADR — PR 88: rewrite README in Russian

## Статус

Accepted — 2026-07-22

## Контекст

README устарел на ~30 PR: порты неверные (`:8000`/`:3000` вместо
nginx `:8080` после PR#54), 6 крупных фич не описаны (3 режима замены,
pattern library, preview-confirm-run, link_preview, пагинация задач,
форматирование preservation), 3 env vars отсутствовали
(`TELEGRAM_SESSION_STRING`, `TELEGRAM_REQUEST_DELAY`,
`TELEGRAM_EDIT_DELAY`), тесты integration/E2E не упомянуты, дерево
проекта не содержало `pattern_compiler.py`, `patterns.py` router,
`pattern.py` model, `Dockerfile.nginx`. UI на русском с PR#72, README
оставался на English — языковое несоответствие.

## Решение

Переписать README на русский (255 строк, 15 секций): описание,
архитектура (Mermaid flowchart вместо ASCII-арта — GitHub рендерит
нативно), возможности, стек, требования, быстрый старт, локальная
разработка, env vars (таблица 15 vars), настройка бота, тестирование,
структура проекта, деплой (production), ограничения, лицензия.

## Альтернативы

1. **Оставить English** — отвергнуто: UI на русском с PR#72, README
   должен соответствовать языку продукта.

2. **Обновить inline (точечные правки)** — отвергнуто: устаревание
   накопилось на ~30 PR, точечные правки не покроют 6 недостающих фич,
   3 env vars, неверные порты и устаревшее дерево проекта.

3. **Отдельный docs-сайт (mkdocs/Docusaurus)** — отвергнуто как
   over-engineering для MVP: README на GitHub — единственная точка
   входа, отдельный сайт требует hosting, build pipeline, maintenance.