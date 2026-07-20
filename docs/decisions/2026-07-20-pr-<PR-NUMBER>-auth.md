# ADR — PR #<PR-NUMBER>: session-based admin auth

## Статус

Accepted (2026-07-20) — реализован простой session-based auth для одного админ-аккаунта (owner + напарник). Starlette `SessionMiddleware` (signed cookie) + `secrets.compare_digest` для timing-safe сравнения пароля. Без БД-пользователей, без JWT, без OAuth.

## Контекст

Софтом (telesoft — Telegram channel post editor) пользуются два человека: owner и напарник. Достаточно одной пары логин/пароль из `.env` (`ADMIN_USERNAME`/`ADMIN_PASSWORD`). Не нужны:
- БД-слой пользователей (регистрации, роли, profiles).
- OAuth (Google/GitHub) — overkill для 2 пользователей.
- JWT — stateless, но требует refresh token flow, secret rotation.
- Basic auth — браузеры кешируют credentials, нет logout, утечка при каждом запросе.

Нужен:
- Простой auth с logout (session можно завершить).
- Cookie-based session (stateful, server-side state в signed cookie).
- Защита от timing attack при сравнении пароля.
- Минимум зависимостей (itsdangerous уже в deps из PR#2).

Референс паттерна: `/root/workspace/media-gen/src/media_gen/api/auth.py` + `/root/workspace/media-gen/src/media_gen/api/routers/auth.py` — тот же паттерн `verify_credentials`/`login`/`logout`/`current_user`/`require_auth` (Depends).

## Решение

### Starlette `SessionMiddleware` + signed cookie

- `app.add_middleware(SessionMiddleware, secret_key=Settings.from_env().secret_key)` в `main.py`.
- Cookie подписан `SECRET_KEY` через `itsdangerous` (HMAC-SHA256). Данные в cookie — plaintext (base64), но подпись защищает от подделки. НЕ хранить sensitive данные в session (только username).
- `request.session` — dict-like (`__getitem__`/`__setitem__`/`get`/`clear`). Session key `"user"` → username string.
- `logout` = `request.session.clear()` (cookie очищается).

### `secrets.compare_digest` для пароля

- `verify_credentials`: `secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(password, settings.admin_password)`.
- Timing-safe comparison — защита от timing attack (атакующий не может определить длину/содержимое пароля по времени ответа).
- НЕ plaintext `==` — ruff S105/S106 игнорируются в tests, в src не срабатывают (нет строковых литералов пароля).

### FastAPI dependency `require_auth`

- `async def require_auth(request) -> str` — возвращает username или бросает `HTTPException(401, "Not authenticated")`.
- Используется как `user: str = Depends(require_auth)` (для endpoint'ов, использующих username) или `_user: str = Depends(require_auth)` (для endpoint'ов, требующих только auth, без использования username — underscore prefix, ruff ARG001 не срабатывает).
- Паттерн 1-в-1 как в media-gen.

### Endpoints под `/api/auth`

- `POST /api/auth/login` — body `LoginRequest(username, password)`, возвращает `AuthResponse(status="ok", user=username)` или 401.
- `POST /api/auth/logout` — требует auth, возвращает `{"status":"ok"}`.
- `GET /api/auth/me` — требует auth, возвращает `{"user": username}`.
- `GET /health` — public (без auth), для health checks.

## Альтернативы

### JWT (JSON Web Token)

- Pro: stateless (нет server-side state), масштабируется горизонтально без shared session store.
- Con: нет logout (token валиден до expiry), нужен refresh token flow, secret rotation, token leakage risk (хранится в localStorage — XSS, или httpOnly cookie — CSRF).
- Решение: session-based — простой logout (`session.clear()`), server-side state (cookie подписан, но не зашифрован — username в plaintext, что ок для не-sensitive данных). Для 2 пользователей JWT — overkill.

### Basic auth (RFC 7617)

- Pro: простой (header `Authorization: Basic <base64>`), нет server-side state.
- Con: браузеры кешируют credentials (нет logout без закрытия браузера), credentials передаются при каждом запросе (утечка при MITM без HTTPS), нет expiration.
- Решение: session-based — явный logout, cookie только после login (не при каждом запросе).

### OAuth 2.0 (Google/GitHub)

- Pro: нет хранения пароля в `.env`, MFA через provider, аудит.
- Con: overkill для 2 пользователей, требует callback URL, client_id/secret, provider dependency (Google/GitHub downtime = telesoft down).
- Решение: локальная пара логин/пароль — owner и напарник знают credentials, нет внешней зависимости.

### Хранение пароля в БД (hashed)

- Pro: множество пользователей, password reset, roles.
- Con: БД-слой пользователей, хеширование (bcrypt/argon2), salt, миграции. Для 2 пользователей — избыточно.
- Решение: `ADMIN_USERNAME`/`ADMIN_PASSWORD` в `.env` (не в БД). `secrets.compare_digest` для timing-safe сравнения. Для MVP — достаточно. Если пользователей >2 — переход на БД+hash (future issue).

## Ключевые отклонения от спецификации

Зафиксированы в handoff, раздел "Watch out":
1. **`AuthResponse` только для `/login`** — `/logout` и `/me` возвращают `dict[str, str]` (без `response_model`). Спека требует `AuthResponse` только для login; media-gen референс использует `OkResponse`/`MeResponse` (другие имена, тот же паттерн). telesoft использует generic dict для logout/me (консистентно со спекой issue #17).
2. **`current_user` `isinstance(user, str)` check** — media-gen хранит `{"username": name}` (dict) в session; telesoft хранит `username` (str) напрямую. Проверка `isinstance` защищает от подмены типа (cookie подписан, но не зашифрован — тип может быть любым).
3. **`async def` для всех auth helpers** — media-gen `verify_credentials`/`login`/`logout`/`current_user`/`require_auth` sync; telesoft async (по спеке issue #17). `verify_credentials` мог бы быть sync, но async для консистентности.