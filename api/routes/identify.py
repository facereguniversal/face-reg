"""Recognition routes: identify (1:N) and verify (1:1)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import get_current_user
from api.models.schemas import (
    IdentifyBatchResponse,
    IdentifyBatchResult,
    IdentifyResponse,
    MatchResult,
    VerifyResponse,
)
from api.services.database import get_db
from api.services.face_service import FaceService
from api.services.dependencies import get_face_service, get_client_ip

router = APIRouter()


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
