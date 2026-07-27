"""Recognition routes: identify (1:N) and verify (1:1)."""

from __future__ import annotations

import base64
import gc
import logging
import uuid
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user
from api.models.schemas import (
    IdentifyBatchResponse,
    IdentifyBatchResult,
    IdentifyResponse,
    VerifyResponse,
)
from api.services.database import get_db, async_session_factory, ensure_tables_exist
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service, get_client_ip
from api.services.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/enroll_demo")
async def enroll_demo(
    request: Request,
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Robust demo face enrollment endpoint at /api/enroll_demo."""
    try:
        await ensure_tables_exist()
        async with async_session_factory() as db:
            user_svc = UserService(db)
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            user = await user_svc.get_by_id(str(user_id))
            if not user:
                user = await user_svc.create_with_id(
                    user_id=user_id,
                    name="Demo Guest",
                    email="demo_guest@example.com",
                )
                await db.commit()

            content_type = request.headers.get("content-type", "").lower()
            raw_byte_list: list[bytes] = []

            if "application/json" in content_type:
                body_json = await request.json()
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
                uploaded_files = form.getlist("images")
                for img_file in uploaded_files:
                    if hasattr(img_file, "read"):
                        raw_byte_list.append(await img_file.read())

            if len(raw_byte_list) < 4:
                raise HTTPException(
                    status_code=400, detail="At least 4 valid images required"
                )

            processed_data: list[bytes] = []
            for raw_bytes in raw_byte_list[:6]:
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

        err_msg = f"EXCEPT: {type(e).__name__}: {str(e)}"
        logger.error("Enroll demo exception: %s\n%s", err_msg, traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": err_msg})


@router.post("/identify", response_model=IdentifyResponse)
async def identify(
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Identify the face in the image against all enrolled users (1:N)."""
    data = await image.read()
    result = await face_svc.identify(data, db, client_ip=client_ip)
    return result


@router.post("/identify/batch", response_model=IdentifyBatchResponse)
async def identify_batch(
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Identify faces in multiple images in a single call."""
    results: list[IdentifyBatchResult] = []
    for idx, img in enumerate(images):
        data = await img.read()
        try:
            id_result = await face_svc.identify(data, db, client_ip=client_ip)
            results.append(
                IdentifyBatchResult(image_index=idx, matches=id_result.matches)
            )
        except Exception:
            results.append(IdentifyBatchResult(image_index=idx, matches=[]))
    return IdentifyBatchResponse(results=results)


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    user_id: uuid.UUID = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _caller: dict[str, Any] = Depends(get_current_user),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Verify whether the image matches a specific user (1:1)."""
    data = await image.read()
    result = await face_svc.verify(user_id, data, db, client_ip=client_ip)
    if result is None:
        raise HTTPException(status_code=404, detail="User has no enrolled faces")
    return result
