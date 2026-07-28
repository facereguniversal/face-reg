"""Face quality validation and enrollment sub-routes."""

from __future__ import annotations

import base64
import gc
import logging
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse

from api.models.schemas import ValidateResponse
from api.services.database import async_session_factory, ensure_tables_exist
from api.services.dependencies import get_face_service, get_client_ip
from api.services.face_service import FaceService
from api.services.user_service import UserService

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


@router.post("/enroll", status_code=201)
@router.post("/enroll_demo", status_code=201)
@router.post("/enroll_json", status_code=201)
async def enroll_demo(
    request: Request,
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Enroll the demo user from four to six base64 or multipart images.

    ``/enroll_demo`` and ``/enroll_json`` are retained as compatibility aliases
    so previously cached frontend bundles keep working after an API deployment.
    """
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
