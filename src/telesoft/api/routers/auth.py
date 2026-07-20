"""Authentication endpoints: login, logout, and current user."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from telesoft.api.auth import login, logout, require_auth
from telesoft.schemas.auth import AuthResponse, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login_endpoint(payload: LoginRequest, request: Request) -> AuthResponse:
    ok = await login(request, payload.username, payload.password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return AuthResponse(status="ok", user=payload.username)


@router.post("/logout")
async def logout_endpoint(
    request: Request,
    _user: str = Depends(require_auth),
) -> dict[str, str]:
    await logout(request)
    return {"status": "ok"}


@router.get("/me")
async def me_endpoint(user: str = Depends(require_auth)) -> dict[str, str]:
    return {"user": user}
