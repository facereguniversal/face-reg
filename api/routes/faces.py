"""Face template management routes: enroll, get, delete."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from api.rate_limit import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user
from api.models.schemas import FaceTemplateResponse, ValidateResponse
from api.services.database import get_db
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Validate face image quality
# ---------------------------------------------------------------------------


@router.post("/validate", response_model=ValidateResponse)
@limiter.limit("30/minute")
async def validate_face(
    request: Request,
    image: UploadFile = File(..., description="Face image to validate"),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
):
    """Validate a face image for quality without enrolling."""
    data = await image.read()
    result = await face_svc.validate(data)
    return result


@router.get("/{template_id}", response_model=FaceTemplateResponse)
async def get_face_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
):
    """Get metadata for a specific face template."""
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
    face_svc: FaceService = Depends(get_face_service),
):
    """Delete a specific face template."""
    template = await face_svc.get_template(template_id, db)
    if not template:
        raise HTTPException(status_code=404, detail="Face template not found")
    await face_svc.delete_template(template_id, db)
