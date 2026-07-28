"""User management routes: create, read, delete."""

from __future__ import annotations

import base64
import gc
import logging
import uuid
from typing import Any

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user, require_admin
from api.models.schemas import UserCreate, UserResponse
from api.services.database import get_db, async_session_factory, ensure_tables_exist
from api.services.user_service import UserService
from api.services.face_service import FaceService

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


@router.post(
    "/{user_id}/faces",
    status_code=status.HTTP_201_CREATED,
)
async def enroll_faces(
    user_id: uuid.UUID,
    request: Request,
    images: list[UploadFile] = File(default=[]),
):
    """Upload face images to enroll embeddings for a user."""
    try:
        face_svc = getattr(request.app.state, "face_service", None)
        if face_svc is None:
            face_svc = FaceService()
            request.app.state.face_service = face_svc

        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else "0.0.0.0"

        await ensure_tables_exist()
        async with async_session_factory() as db:
            user_svc = UserService(db)

            # Extract student details from query params, json, or form
            req_params = request.query_params
            st_name = req_params.get("name") or req_params.get("student_name")
            st_class = req_params.get("student_class") or req_params.get("class")

            content_type = request.headers.get("content-type", "").lower()
            body_json = {}
            if "application/json" in content_type:
                try:
                    body_json = await request.json()
                    if not st_name:
                        st_name = body_json.get("name") or body_json.get("student_name")
                    if not st_class:
                        st_class = body_json.get("student_class") or body_json.get(
                            "class"
                        )
                except Exception:
                    pass

            user = await user_svc.get_by_id(str(user_id))
            meta = {"student_class": st_class or "Class 10-A"}
            if not user:
                email = f"student_{str(user_id).replace('-', '')[:12]}@school.edu"
                user = await user_svc.create_with_id(
                    user_id=user_id,
                    name=st_name or "Demo Student",
                    email=email,
                    extra_metadata=meta,
                )
            else:
                if st_name:
                    user.name = st_name
                curr_meta = dict(user.extra_metadata or {})
                if st_class:
                    curr_meta["student_class"] = st_class
                user.extra_metadata = curr_meta
            await db.commit()

            raw_byte_list: list[bytes] = []
            if images:
                for img_file in images:
                    raw_byte_list.append(await img_file.read())
            else:
                if "application/json" in content_type:
                    raw_images = body_json.get("images", [])
                    for item in raw_images:
                        if isinstance(item, str):
                            b64_str = item.split(",", 1)[1] if "," in item else item
                            try:
                                raw_byte_list.append(base64.b64decode(b64_str))
                            except Exception:
                                continue
                else:
                    form = await request.form()
                    if not st_name:
                        st_name = form.get("name") or form.get("student_name")
                        if st_name and user:
                            user.name = st_name
                    if not st_class:
                        st_class = form.get("student_class") or form.get("class")
                        if st_class and user:
                            curr_meta = dict(user.extra_metadata or {})
                            curr_meta["student_class"] = st_class
                            user.extra_metadata = curr_meta
                    uploaded_files = form.getlist("images")
                    for img_file in uploaded_files:
                        if hasattr(img_file, "read"):
                            raw_byte_list.append(await img_file.read())

            if len(raw_byte_list) < 4:
                raise HTTPException(
                    status_code=400, detail="At least 4 valid images required"
                )
            if len(raw_byte_list) > 6:
                raw_byte_list = raw_byte_list[:6]

            # Sequential downscaling to 320px with immediate cleanup to keep RAM < 35MB
            processed_data: list[bytes] = []
            for raw_bytes in raw_byte_list:
                try:
                    np_arr = np.frombuffer(raw_bytes, np.uint8)
                    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    del np_arr
                    if img is not None:
                        h, w = img.shape[:2]
                        if max(h, w) > 320:
                            scale = 320.0 / max(h, w)
                            img = cv2.resize(img, (int(w * scale), int(h * scale)))
                        _, reencoded = cv2.imencode(
                            ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75]
                        )
                        processed_data.append(reencoded.tobytes())
                        del img
                    else:
                        processed_data.append(raw_bytes)
                except Exception:
                    processed_data.append(raw_bytes)

            del raw_byte_list
            gc.collect()

            result = await face_svc.enroll(
                user_id=user.id, image_data=processed_data, db=db, client_ip=client_ip
            )
            await db.commit()
            gc.collect()

            return JSONResponse(
                status_code=201,
                content={
                    "template_ids": [str(tid) for tid in result.template_ids],
                    "status": "enrolled",
                    "quality_scores": [
                        float(qs) if qs is not None else 0.95
                        for qs in result.quality_scores
                    ],
                },
            )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        import traceback

        error_msg = f"EXCEPT: {type(e).__name__}: {str(e)}"
        logger.error("Enrollment exception: %s\n%s", error_msg, traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": error_msg})
