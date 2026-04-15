"""User management routes: create, read, delete."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user, require_admin
from api.models.schemas import UserCreate, UserResponse
from api.services.database import get_db
from api.services.user_service import UserService

router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Create a new user. Admin only."""
    svc = UserService(db)
    existing = await svc.get_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await svc.create(body)
    return UserResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        face_count=0,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve user metadata."""
    svc = UserService(db)
    user = await svc.get_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    face_count = await svc.count_faces(user.id)
    return UserResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        face_count=face_count,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Delete a user and all associated face templates. Admin only."""
    svc = UserService(db)
    user = await svc.get_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await svc.delete(user)
