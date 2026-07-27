"""Face quality validation and enrollment sub-routes."""

from __future__ import annotations

import logging
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import ValidateResponse
from api.services.database import get_db
from api.services.dependencies import get_face_service, get_client_ip
from api.services.face_service import FaceService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/validate", response_model=ValidateResponse)
async def validate_face(
    image: UploadFile = File(..., description="Single face image"),
    face_svc: FaceService = Depends(get_face_service),
):
    """Run real-time quality check on a single face frame."""
    data = await image.read()
    return await face_svc.validate(data)


@router.post("/enroll_demo")
async def enroll_demo(
    request: Request,
    db: AsyncSession = Depends(get_db),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Enroll demo endpoint for verification."""
    form = await request.form()
    files = form.getlist("images")
    image_data = []
    for f in files:
        if hasattr(f, "read"):
            image_data.append(await f.read())

    demo_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    from api.services.user_service import UserService

    user_svc = UserService(db)
    user = await user_svc.create_with_id(
        demo_id, "Demo Guest", "demo_guest@example.com"
    )
    await db.commit()

    res = await face_svc.enroll(
        user_id=user.id, image_data=image_data, db=db, client_ip=client_ip
    )
    return res
