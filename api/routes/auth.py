"""Authentication routes: login, refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.rate_limit import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from api.models.schemas import LoginRequest, RefreshRequest, TokenResponse
from api.services.database import get_db
from api.services.user_service import UserService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and return JWT access + refresh tokens."""
    user_svc = UserService(db)
    user = await user_svc.get_by_email(body.email)
    if not user or not verify_password(body.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access = create_access_token(str(user.id), role=user.role)
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_svc = UserService(db)
    user = await user_svc.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access = create_access_token(str(user.id), role=user.role)
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)
