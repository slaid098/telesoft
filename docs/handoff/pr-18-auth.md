---
pr: 18
issue: 17
branch: feat/auth/session-middleware
status: ready
created: 2026-07-20
---

# Handoff — PR #18: session-based admin auth

## Что сделано

Реализован issue #17 — простой session-based auth для одного админ-аккаунта (owner + напарник используют одну пару логин/пароль из `.env`). Auth построен на Starlette `SessionMiddleware` (signed cookie через `itsdangerous`, уже в deps из PR#2). Без БД-пользователей, без регистраций, без OAuth.

### Шаг 1: Auth helpers (`src/telesoft/api/auth.py`)

- `async def verify_credentials(username, password) -> bool` — `Settings.from_env()` + `secrets.compare_digest` для username и password (НЕ plaintext `==` — защита от timing attack; ruff S105/S106 игнорируются глобально для tests, в src не срабатывает т.к. нет строковых литералов пароля).
- `async def login(request, username, password) -> bool` — если `verify_credentials` OK: `request.session["user"] = username`, вернуть True. Иначе False (без раскрытия причины — generic 401 в роутере).
- `async def logout(request) -> None` — `request.session.clear()`.
- `async def current_user(request) -> str | None` — `request.session.get("user")` с проверкой `isinstance(user, str)` (защита от подмены типа в cookie).
- `async def require_auth(request) -> str` — FastAPI dependency: `user = await current_user(request)`. Если None → `HTTPException(status_code=401, detail="Not authenticated")`. Иначе возвращает username (используется как `Depends(require_auth)`).
- Импорты: `from fastapi import HTTPException, Request, status`, `from telesoft.config import Settings`, `import secrets`.

### Шаг 2: Schemas (`src/telesoft/schemas/auth.py`)

- `class LoginRequest(BaseModel): username: str; password: str`.
- `class AuthResponse(BaseModel): status: str; user: str | None = None`.

### Шаг 3: Auth router (`src/telesoft/api/routers/auth.py`)

- `router = APIRouter(prefix="/api/auth", tags=["auth"])`.
- `POST /login` — body: `LoginRequest`. Вызывает `login(request, ...)`. Если OK: `AuthResponse(status="ok", user=username)`. Если нет: `HTTPException(401, "Invalid credentials")`.
- `POST /logout` — требует `Depends(require_auth)` (unused param `_user: str = Depends(...)` — underscore-prefixed, ruff ARG001 не срабатывает). Вызывает `await logout(request)`. Возвращает `{"status": "ok"}`.
- `GET /me` — требует `user: str = Depends(require_auth)`. Возвращает `{"user": user}`.

### Шаг 4: Интеграция в main.py

- `from starlette.middleware.sessions import SessionMiddleware`.
- `app.add_middleware(SessionMiddleware, secret_key=Settings.from_env().secret_key)`.
- `from telesoft.api.routers.auth import router as auth_router`.
- `app.include_router(auth_router)`.
- `GET /health` остаётся public (без auth).

### Шаг 5: Тесты (`tests/test_auth.py`, 8 тестов)

- `client` fixture: monkeypatch `SECRET_KEY` (32+ chars — itsdangerous требует), `ADMIN_USERNAME=admin`, `ADMIN_PASSWORD=secret`, `DB_PATH=tmp`, `TestClient(app)` as context manager (trigger lifespan).
- `test_login_success` — POST /api/auth/login с правильными кредами → 200, `{"status":"ok","user":"admin"}`, `session` cookie set.
- `test_login_invalid_credentials` — неправильный пароль → 401, `detail="Invalid credentials"`.
- `test_logout_requires_auth` — POST /api/auth/logout без сессии → 401.
- `test_logout_success` — логин, logout → 200 `{"status":"ok"}`, последующий /me → 401.
- `test_me_requires_auth` — GET /api/auth/me без сессии → 401.
- `test_me_after_login` — логин, /me → 200 `{"user":"admin"}`.
- `test_session_persists_across_requests` — логин в одном request, /me в другом (тот же TestClient) → 200.
- `test_concurrent_sessions_independent` — два TestClient'а (отдельные session cookies), каждый логинится independently, logout одного не влияет на другого.

### Шаг 6: conftest.py

- `mock_settings` обновлён: `SECRET_KEY="test-secret-key-at-least-32-chars-long-for-testing"` (32+ chars), `ADMIN_PASSWORD="secret"` (по спеке issue #17). Остальные env vars без изменений.

## Почему

Софтом пользуются два человека (owner + напарник) — достаточно одной пары логин/пароль из `.env`. Не нужен БД-слой пользователей, регистрации, OAuth, JWT. Starlette `SessionMiddleware` (signed cookie через `itsdangerous`) — простой, без внешних зависимостей, cookie подписан `SECRET_KEY` (защита от подделки). `secrets.compare_digest` для сравнения пароля — защита от timing attack (не plaintext `==`). Паттерн 1-в-1 как в media-gen (`/root/workspace/media-gen/src/media_gen/api/auth.py`).

## Pending

- **Endpoint'ы для замены ссылок** — этот PR реализует только auth (login/logout/me). Endpoint'ы channels CRUD, replace-link, edit_logs — отдельные issues.
- **Frontend auth UI** — login form в SvelteKit, защищённые роуты, logout button — отдельный issue (frontend).
- **Rate limiting на /login** — нет brute-force защиты. Для 2 пользователей не критично, но можно добавить slowapi в будущем.
- **CSRF** — SessionMiddleware использует signed cookie, но CSRF токен не передаётся. Для API-only (без form POST из browser) достаточно. Если будет form-based UI — добавить CSRF токен.

## Watch out

- **`secrets.compare_digest` vs plaintext `==`** — спека явно требует `secrets.compare_digest` (timing-safe comparison). НЕ использовать `==` — ruff S105/S106 могут сработать, но главное — security. `compare_digest` работает с `str` (приводит к bytes внутри).
- **`SECRET_KEY` должен быть 32+ chars** — `itsdangerous` требует ключ ≥32 bytes для HMAC-SHA256. В tests `mock_settings` использует `"test-secret-key-at-least-32-chars-long-for-testing"` (52 chars). Production — `SECRET_KEY` env var (default `""` в `Settings.from_env()` — НЕ подходит для SessionMiddleware, нужен явный secret в `.env`).
- **`request.session` — это dict-like** — Starlette `SessionMiddleware` добавляет `request.session` (SessionStore), поддерживает `__getitem__`/`__setitem__`/`get`/`clear`. Cookie подписан `SECRET_KEY`, данные в plaintext (base64) — НЕ хранить sensitive данные в session (только username).
- **`Depends(require_auth)` паттерн** — `require_auth` возвращает `str` (username), используется как `user: str = Depends(require_auth)`. Для endpoint'ов которые не используют username, но требуют auth — `_user: str = Depends(require_auth)` (underscore prefix, ruff ARG001 не срабатывает).
- **`TestClient(app)` as context manager** — trigger lifespan (init_db, start_client). Без context manager lifespan не запускается → DB не init → 500 на endpoints. Паттерн из `test_health.py`.
- **`isinstance(user, str)` check в `current_user`** — `request.session.get("user")` может вернуть любой тип (cookie может быть подделан, хотя и подписан — но не зашифрован). Проверка `isinstance` защищает от подмены типа (напр. если кто-то положит dict вместо str в session — хотя это маловероятно).
- **`async def` для auth helpers** — `verify_credentials`/`login`/`logout`/`current_user`/`require_auth` все async (спека требует). `verify_credentials` мог бы быть sync (нет I/O), но async для консистентности и будущего расширения (напр. БД-lookup).
- **`Settings.from_env()` в `verify_credentials`** — вызывается при каждом login (не cached). Тесты `monkeypatch.setenv` до `TestClient(app)` работают. Production — статичные env vars.
- **Coverage 95.90%** — `api/auth.py` 100%, `api/routers/auth.py` 100%, `schemas/auth.py` 100%, `main.py` 85% (uncovered: defensive branches в lifespan try/except). Общее покрытие ≥80% — gate пройден.
- **mypy strict** — `from fastapi import status` (не `from starlette.status import HTTP_401_UNAUTHORIZED`) — `fastapi.status` реэкспортирует starlette status codes, mypy проходит.
- **ruff** — `import secrets` в начале, `from fastapi import HTTPException, Request, status` (alphabetical, isort). `ARG001` для `_user` в logout — не срабатывает (underscore prefix). `S105`/`S106` — нет строковых литералов пароля в `src/`.
- **`AuthResponse` vs `dict[str, str]`** — `/login` возвращает `AuthResponse` (Pydantic, `response_model=AuthResponse`), `/logout` и `/me` — `dict[str, str]` (без `response_model`). Спека требует `AuthResponse` только для login; logout/me — generic dict. Консистентно с media-gen референсом.