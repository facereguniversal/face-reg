"""User management routes: create, read, delete."""

from __future__ import annotations

import gc
import logging
import uuid
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user, require_admin
from api.models.schemas import UserCreate, UserResponse, EnrollResponse
from api.services.database import get_db
from api.services.user_service import UserService
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service, get_client_ip

logger = logging.getLogger(__name__)
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Upload face images to enroll embeddings for a user."""
    try:
        form = await request.form()
        uploaded_files = form.getlist("images")

        if not uploaded_files or len(uploaded_files) < 4:
            raise HTTPException(status_code=400, detail="At least 4 images required")
        if len(uploaded_files) > 6:
            raise HTTPException(status_code=400, detail="Maximum 6 images allowed")

        user_svc = UserService(db)
        user = await user_svc.get_by_id(str(user_id))
        if not user:
            email = f"user_{str(user_id).replace('-', '')[:12]}@example.com"
            user = await user_svc.create_with_id(
                user_id=user_id,
                name="Demo Guest",
                email=email,
            )
            await db.commit()

        # Read, downscale to max 480px, and compress images to protect RAM
        image_data: list[bytes] = []
        for img_file in uploaded_files:
            if hasattr(img_file, "read"):
                raw_data = await img_file.read()
            elif isinstance(img_file, bytes):
                raw_data = img_file
            else:
                continue

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

        # Delegate to face service (detection → alignment → embedding → store)
        result = await face_svc.enroll(
            user_id=user.id, image_data=image_data, db=db, client_ip=client_ip
        )
        gc.collect()
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_msg = f"EXCEPT: {type(e).__name__}: {str(e)}"
        logger.error("Enrollment exception: %s\n%s", error_msg, traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": error_msg})
