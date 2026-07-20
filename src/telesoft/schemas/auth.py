"""Pydantic schemas for authentication endpoints."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Credentials submitted by the client."""

    username: str
    password: str


class AuthResponse(BaseModel):
    """Generic authentication response."""

    status: str
    user: str | None = None
