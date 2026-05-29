"""User management routes: create, read, delete."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user, require_admin
from api.models.schemas import UserCreate, UserResponse, EnrollResponse
from api.services.database import get_db
from api.services.user_service import UserService
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service, get_client_ip
from fastapi import File, UploadFile

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
    images: list[UploadFile] = File(..., description="4-6 face images"),
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Upload face images to enroll embeddings for a user."""
    if len(images) < 4:
        raise HTTPException(status_code=400, detail="At least 4 images required")
    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed")

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
