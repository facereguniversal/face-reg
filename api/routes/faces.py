"""Face quality validation and enrollment sub-routes."""

from __future__ import annotations

import base64
import gc
import logging
import uuid
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import ValidateResponse, EnrollResponse
from api.services.database import get_db
from api.services.dependencies import get_face_service, get_client_ip
from api.services.face_service import FaceService
from api.services.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()


class EnrollJsonRequest(BaseModel):
    user_id: uuid.UUID
    images: list[str]  # List of base64 data URLs or raw base64 strings


@router.post("/validate", response_model=ValidateResponse)
async def validate_face(
    image: UploadFile = File(..., description="Single face image"),
    face_svc: FaceService = Depends(get_face_service),
):
    """Run real-time quality check on a single face frame."""
    data = await image.read()
    return await face_svc.validate(data)


@router.post("/enroll_json", response_model=EnrollResponse)
async def enroll_json(
    body: EnrollJsonRequest,
    db: AsyncSession = Depends(get_db),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Enroll faces via JSON base64 images."""
    if len(body.images) < 4:
        raise HTTPException(status_code=400, detail="At least 4 images required")
    if len(body.images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed")

    user_svc = UserService(db)
    user = await user_svc.get_by_id(str(body.user_id))
    if not user:
        email = f"user_{str(body.user_id).replace('-', '')[:12]}@example.com"
        user = await user_svc.create_with_id(
            user_id=body.user_id,
            name="Demo Guest",
            email=email,
        )
        await db.commit()

    image_data: list[bytes] = []
    for b64_str in body.images:
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            raw_data = base64.b64decode(b64_str)

            np_arr = np.frombuffer(raw_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                if max(h, w) > 480:
                    scale = 480.0 / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)))
                _, reencoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                image_data.append(reencoded.tobytes())
            else:
                image_data.append(raw_data)
        except Exception as e:
            logger.warning("Base64 decode warning: %s", e)

    res = await face_svc.enroll(
        user_id=user.id, image_data=image_data, db=db, client_ip=client_ip
    )
    await db.commit()
    gc.collect()
    return res
