---
pr: <PR-NUMBER>
issue: 71
branch: feat/web/russian-ui
status: ready
created: 2026-07-22
---

# Handoff — PR <PR-NUMBER>: translate UI to Russian

## Что сделано

Реализован issue #71 — перевод всех user-facing строк веб-интерфейса
telesoft на русский язык (~95 строк в 14 файлах + 6 тест-файлов).

1. **`web/src/lib/types.ts`** — `JOB_STATUS_LABELS` (single source of truth):
   - pending → «Ожидает», running → «Выполняется», done → «Готово»,
     failed → «Ошибка», cancelled → «Отменена».

2. **`web/src/app.html`** — `<html lang="en">` → `<html lang="ru">`.

3. **`web/src/routes/login/+page.svelte`** — все строки формы входа:
   заголовок, лейблы «Имя пользователя»/«Пароль», кнопка «Войти»,
   сообщения об ошибках («Неверные учётные данные», «Ошибка сети» и т.д.).

4. **`web/src/routes/+layout.svelte`** — навигация («Каналы»/«Задачи»),
   «Вы вошли как», кнопка «Выйти», aria-label «Мобильная навигация».
   Бренд «telesoft» в шапке оставлен без перевода.

5. **`web/src/routes/channels/+page.svelte`** — заголовок «Каналы»,
   кнопка «Добавить канал»/«Закрыть», колонки таблицы («Название»,
   «Активен», «Действия»), бейджи «активен»/«неактивен» (desktop + mobile),
   кнопки «Удалить»/«Открыть», пустое состояние «Нет каналов»,
   confirm-сообщение «Удалить канал «…»?».

6. **`web/src/routes/channels/[id]/+page.svelte`** — «Назад к каналам»,
   «История запусков (последние 5)», «Все задачи →», пустое состояние,
   колонки таблицы («Статус», «Прогресс», «Создан»), «Прогресс:» в mobile,
   бейджи «активен»/«неактивен».

7. **`web/src/routes/channels/+page.ts` и `channels/[id]/+page.ts`** —
   error-сообщения: «Не удалось загрузить каналы», «Некорректный id канала»,
   «Не удалось загрузить канал».

8. **`web/src/routes/jobs/+page.svelte`** — заголовок «Задачи», фильтр
   «Статус» + option «все», авто-обновление подсказка, колонки таблицы
   («Канал», «Паттерн», «Статус», «Прогресс», «Создан»), пустое состояние
   «Нет задач» (desktop + mobile).

9. **`web/src/routes/jobs/[id]/+page.svelte`** — «Задача #N», «Канал:»,
   «Паттерн:», «Новая ссылка:», «Назад к задачам», «Прогресс:»,
   «Изменено:» / «Ошибки:», предупреждение о пустом match, кнопка
   «Отменить задачу»/«Отмена…», «Логи (N)», пустое состояние логов,
   колонки таблицы логов («ID сообщения», «Успех», «Ошибка»,
   «Старый текст», «Изменён»).

10. **`web/src/routes/jobs/+page.ts` и `jobs/[id]/+page.ts`** —
    error-сообщения: «Не удалось загрузить задачи», «Некорректный id задачи»,
    «Не удалось загрузить задачу».

11. **`web/src/lib/components/ChannelForm.svelte`** — заголовок «Новый канал»,
    лейблы «Название», «Username (необязательно)», подсказка «Username канала
    без @», кнопки «Отмена»/«Сохранить» (с «Сохранение…»), ошибки валидации.

12. **`web/src/lib/components/ReplaceLinkForm.svelte`** — заголовок «Замена
    ссылки», labels MODES («Простой»/«Библиотека паттернов»/«Расширенный»),
    «Паттерн (регулярное выражение)» в Advanced mode, «Лимит (последних N
    постов для сканирования)», error-сообщения. Остальные строки (Simple/
    Library mode, radio, кнопки) уже были на русском из PR#58.

13. **`web/src/lib/components/PatternLibrary.svelte`** — error-сообщения
    («Не удалось загрузить/создать/удалить паттерн»), бейдж «встроенный»
    (вместо «built-in»). Остальные строки уже были на русском из PR#58.

14. **`web/src/lib/api.ts`** — `apiErrorMessage` fallback «Ошибка сети»,
    `ApiError(401, null, "Не авторизован")`.

15. **НЕ переведено** (по шагу 15 спеки):
    - «Telegram ID» — технический термин (в channels таблице, ChannelForm,
      channel detail).
    - «Username» — Telegram @username (ChannelForm label, channels таблица,
      channel detail).
    - Placeholder-примеры URL (`https://t.me/bot?start=flow-*`,
      `https://new.example.com`, `https://t.me/channel/140`,
      `-1001234567890`, `mychannel`, `admin`, `••••••••`).
    - Бренд «telesoft» (app.html title, layout шапка, login заголовок).
    - Идентификатор «ID» (колонка таблицы, `#{job.id}`).

16. **Тесты обновлены** (`web/src/tests/*.test.ts`):
    - `login.test.ts` — `Username`→`Имя пользователя`, `Password`→`Пароль`,
      `Sign in`→`Войти`, `Invalid credentials`→`Неверные учётные данные`.
    - `layout.test.ts` — `Channels`→`Каналы`, `Logout`→`Выйти`.
    - `channels.test.ts` — `active`/`inactive`→`активен`/`неактивен`,
      `No channels`→`Нет каналов`, `Delete`→`Удалить`,
      `Add channel`→`Добавить канал`, `Title`→`Название`,
      `Save`→`Сохранить`, `Cancel`→`Отмена`.
    - `jobs.test.ts` — `Job #1`→`Задача #1`, `Running`→`Выполняется`,
      `Progress:`→`Прогресс:`, `Cancel job`→`Отменить задачу`.
    - `replace-link.test.ts` — `Advanced`→`Расширенный`,
      `Pattern (raw regex)`→`Паттерн (регулярное выражение)`,
      `Limit`→`Лимит`, `built-in`→`встроенный`.

## Почему

Интерфейс telesoft был полностью на английском (наследие скелета из PR#24
и media-gen референса). Целевая аудитория — русскоязычные пользователи.
Новые компоненты (PreviewModal, PatternLibrary, ReplaceLinkForm — PR#58)
уже были частично на русском, старые страницы (login, layout, channels,
jobs, ChannelForm) — полностью на английском. Этот PR приводит весь UI
к единому русскому языку.

## Pending

— (backend не затронут, UI-изменения не требуют E2E-проверки)

## Watch out

- **`JOB_STATUS_LABELS` — single source of truth** для статусов задач.
  Все страницы (jobs list, job detail, channel detail) используют
  `JOB_STATUS_LABELS[job.status]` — НЕ хардкодить переводы статусов
  в компонентах. Новые статусы добавлять в `types.ts`.

- **Не переведены технические термины** (шаг 15 спеки): «Telegram ID»,
  «Username», «ID», бренд «telesoft», URL placeholder'ы. При добавлении
  новых user-facing строк — переводить на русский, но сохранять эти
  термины как есть.

- **Backend error-сообщения НЕ переведены** — `api.ts` ловит
  `parsed.detail` из backend response и показывает как есть. Backend
  возвращает английские сообщения (FastAPI/Pydantic defaults + кастомные
  `HTTPException(detail="...")`). Перевод backend error-сообщений —
  отдельная задача (issue не требуется, т.к. большинство errors
  перехватываются и заменяются на русские в `apiErrorMessage` /
  try/catch блоках компонентов).

- **`app.html lang="ru"`** — влияет на SEO/ accessibility (screen readers
  используют lang для произношения). Изменение семантически корректно.

- **2 pre-existing svelte warnings** `state_referenced_locally` в
  `jobs/[id]/+page.svelte:10-11` — НЕ связаны с этим PR (наследие PR#26,
  `let job = $state(data.job)` паттерн «load once, update via events»).
  Advisory, не error.