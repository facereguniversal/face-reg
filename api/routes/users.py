"""User management routes: create, read, delete."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.authorization import require_self_or_admin
from api.auth.jwt_handler import get_current_user, require_admin
from api.models.db_models import User
from api.models.schemas import (
    EnrollResponse,
    UserCreate,
    UserResponse,
    UserSearchResponse,
)
from api.services.checkin_service import CheckInService, checkin_item_from_model
from api.services.database import get_db
from api.services.user_service import UserService
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service, get_client_ip
from fastapi import File, UploadFile

router = APIRouter()


async def build_user_response(
    user: User,
    user_svc: UserService,
    checkin_svc: CheckInService,
) -> UserResponse:
    """Build user response without relying on async lazy relationships."""
    face_count = await user_svc.count_faces(user.id)
    last_checkins = await checkin_svc.last_checkins_for_users([user.id])
    last_checkin = last_checkins.get(user.id)
    return UserResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        face_count=face_count,
        last_checkin=checkin_item_from_model(last_checkin) if last_checkin else None,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
    client_ip: str = Depends(get_client_ip),
):
    """Create a new user. Admin only."""
    svc = UserService(db, source_ip=client_ip)
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
        role=user.role,
        created_at=user.created_at,
        face_count=0,
        last_checkin=None,
    )


@router.get("", response_model=UserSearchResponse)
async def search_users(
    query: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Search users for admin dashboard manual override workflows."""
    checkin_svc = CheckInService(db)
    users = await checkin_svc.search_users(query=query, limit=limit)
    return UserSearchResponse(users=users)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve user metadata."""
    require_self_or_admin(user_id, caller)
    svc = UserService(db)
    user = await svc.get_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await build_user_response(user, svc, CheckInService(db))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
    client_ip: str = Depends(get_client_ip),
):
    """Delete a user and all associated face templates. Admin only."""
    svc = UserService(db, source_ip=client_ip)
    user = await svc.get_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await svc.delete(user)


@router.post(
    "/{user_id}/faces",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_faces(
    user_id: uuid.UUID,
    images: list[UploadFile] = File(..., description="3-5 face images"),
    db: AsyncSession = Depends(get_db),
    caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Upload face images to enroll embeddings for a user."""
    require_self_or_admin(user_id, caller)
    if len(images) < 3:
        raise HTTPException(status_code=400, detail="At least 3 images required")
    if len(images) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed")

    user_svc = UserService(db)
    user = await user_svc.get_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Read image bytes
    image_data: list[bytes] = []
    for img in images:
        data = await img.read()
        image_data.append(data)

    # Delegate to face service (detection → alignment → embedding → store)
    result = await face_svc.enroll(
        user_id=user.id, image_data=image_data, db=db, client_ip=client_ip
    )
    return result
