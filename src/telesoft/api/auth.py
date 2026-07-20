"""Session-based authentication for a single admin user.

Credentials are read from environment variables (``ADMIN_USERNAME`` /
``ADMIN_PASSWORD``) via :class:`telesoft.config.Settings`. Session state is
stored in a signed cookie managed by Starlette ``SessionMiddleware``.
"""

import secrets
from typing import Any

from fastapi import HTTPException, Request, status

from telesoft.config import Settings

_SESSION_KEY = "user"


async def verify_credentials(username: str, password: str) -> bool:
    settings = Settings.from_env()
    username_ok = secrets.compare_digest(username, settings.admin_username)
    password_ok = secrets.compare_digest(password, settings.admin_password)
    return username_ok and password_ok


async def login(request: Request, username: str, password: str) -> bool:
    if not await verify_credentials(username, password):
        return False
    request.session[_SESSION_KEY] = username
    return True


async def logout(request: Request) -> None:
    request.session.clear()


async def current_user(request: Request) -> str | None:
    user = request.session.get(_SESSION_KEY)
    if isinstance(user, str):
        return user
    return None


async def require_auth(request: Request) -> str:
    user = await current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def ws_current_user(websocket: Any) -> str | None:
    """Read the current user from a WebSocket's session cookie.

    Works for any ASGI WebSocket exposing ``.scope["session"]`` (set by
    Starlette ``SessionMiddleware``). Returns the username or ``None``.
    """
    session = websocket.scope.get("session", {})
    user = session.get(_SESSION_KEY)
    if isinstance(user, str):
        return user
    return None
