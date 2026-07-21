"""Patterns API: list, create and delete link patterns from the library.

All endpoints are mounted under ``/api/patterns`` (see ``main.py``) and
require an authenticated session via ``require_auth`` applied to the whole
router via ``dependencies=[Depends(require_auth)]``.

Custom patterns are always created with ``is_builtin=0`` — built-in
patterns are seeded separately (PR#3 per issue #55) and cannot be deleted
through this router (HTTP 403).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from telesoft.api.auth import require_auth
from telesoft.core.link_replacer import validate_pattern
from telesoft.db.connection import get_db
from telesoft.db.models import pattern as pattern_model
from telesoft.schemas.job import (
    PatternCreateRequest,
    PatternListResponse,
    PatternResponse,
    now_iso,
)

router = APIRouter(
    prefix="/api/patterns",
    tags=["patterns"],
    dependencies=[Depends(require_auth)],
)


@router.get("", response_model=PatternListResponse)
async def list_patterns_endpoint() -> PatternListResponse:
    """List every pattern in the library (built-in + custom)."""
    async with get_db() as db:
        rows = await pattern_model.list_patterns(db)
    patterns = [PatternResponse.from_row(row) for row in rows]
    return PatternListResponse(patterns=patterns, total=len(patterns))


@router.post("", response_model=PatternResponse, status_code=status.HTTP_201_CREATED)
async def create_pattern_endpoint(payload: PatternCreateRequest) -> PatternResponse:
    """Create a custom pattern (``is_builtin=0`` always).

    The *pattern* is validated as a regex first (422 on invalid syntax).
    """
    try:
        validate_pattern(payload.pattern)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pattern: {exc}",
        ) from exc
    async with get_db() as db:
        row = await pattern_model.create_pattern(
            db,
            name=payload.name,
            pattern=payload.pattern,
            description=payload.description,
            is_builtin=0,
            created_at=now_iso(),
        )
    return PatternResponse.from_row(row)


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pattern_endpoint(pattern_id: int) -> None:
    """Delete a custom pattern. Returns 403 for built-in patterns, 404 if absent."""
    async with get_db() as db:
        existing = await pattern_model.get_pattern(db, pattern_id=pattern_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pattern {pattern_id} not found",
            )
        try:
            deleted = await pattern_model.delete_pattern(db, pattern_id=pattern_id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern {pattern_id} not found",
        )
