"""Face template management routes: enroll, get, delete."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user
from api.models.schemas import EnrollResponse, FaceTemplateResponse
from api.services.database import get_db
from api.services.face_service import FaceService
from api.services.user_service import UserService

router = APIRouter()


# ---------------------------------------------------------------------------
# Enroll faces for a user  (mounted at /api/users/{user_id}/faces via main)
# ---------------------------------------------------------------------------
# NOTE: Because this is mounted under the /api/users prefix in main.py, the
# full path for enrollment is  POST /api/users/{user_id}/faces  as specified
# in the API reference.  We also include it on the faces router so it gets
# the "Faces" tag in the OpenAPI docs.


@router.post(
    "/users/{user_id}/faces",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_faces(
    user_id: uuid.UUID,
    images: list[UploadFile] = File(..., description="4-6 face images"),
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
):
    """Upload face images to enroll embeddings for a user."""
    if len(images) < 1:
        raise HTTPException(status_code=400, detail="At least 1 image required")
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
    face_svc = FaceService()
    result = await face_svc.enroll(user_id=user.id, image_data=image_data, db=db)
    return result


# ---------------------------------------------------------------------------
# Face template CRUD
# ---------------------------------------------------------------------------


@router.get("/{template_id}", response_model=FaceTemplateResponse)
async def get_face_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
):
    """Get metadata for a specific face template."""
    face_svc = FaceService()
    template = await face_svc.get_template(template_id, db)
    if not template:
        raise HTTPException(status_code=404, detail="Face template not found")
    return FaceTemplateResponse(
        face_id=template.id,
        user_id=template.user_id,
        model=template.model,
        quality_score=template.quality_score,
        created_at=template.created_at,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_face_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
):
    """Delete a specific face template."""
    face_svc = FaceService()
    template = await face_svc.get_template(template_id, db)
    if not template:
        raise HTTPException(status_code=404, detail="Face template not found")
    await face_svc.delete_template(template_id, db)
