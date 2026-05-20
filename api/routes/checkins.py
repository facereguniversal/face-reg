"""Kiosk check-in and live admin routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.auth.jwt_handler import decode_token, require_admin
from api.metrics import checkins_total
from api.rate_limit import limiter
from api.models.schemas import (
    CheckInLiveResponse,
    CheckInResponse,
    ManualCheckInRequest,
)
from api.services.checkin_service import (
    CHECKIN_FAILED,
    CHECKIN_SPOOF,
    CheckInService,
    decode_base64_image,
    parse_device_tokens,
)
from api.services.database import get_db
from api.services.dependencies import get_client_ip, get_face_service
from api.services.face_service import FaceService

router = APIRouter()


class LiveCheckInBroadcaster:
    """In-memory WebSocket broadcaster for live dashboard updates."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in self._connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


broadcaster = LiveCheckInBroadcaster()


def validate_device_headers(request: Request) -> str:
    device_id = request.headers.get("X-Device-Id", "").strip()
    device_token = request.headers.get("X-Device-Token", "").strip()
    if not device_id or not device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing kiosk device credentials",
        )

    configured = parse_device_tokens()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No kiosk devices are configured",
        )
    if configured.get(device_id) != device_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid kiosk device credentials",
        )
    return device_id


async def read_checkin_image(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("image")
        if not isinstance(upload, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Missing image upload")
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail="Image upload is empty")
        return data

    if "application/json" in content_type:
        body = await request.json()
        image_base64 = body.get("image_base64") if isinstance(body, dict) else None
        if not image_base64:
            raise HTTPException(status_code=400, detail="Missing image_base64")
        return decode_base64_image(str(image_base64))

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Use multipart image or JSON image_base64",
    )


async def broadcast_result(db: AsyncSession, result: CheckInResponse) -> None:
    if result.checkin is None:
        return
    item = await CheckInService(db).get_live_item(result.checkin.id)
    if item is None:
        return
    await broadcaster.broadcast({"type": "checkin", "checkin": jsonable_encoder(item)})


@router.post("/checkin", response_model=CheckInResponse)
@limiter.limit("30/minute")
async def checkin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    face_svc: FaceService = Depends(get_face_service),
    client_ip: str = Depends(get_client_ip),
):
    """Process one kiosk check-in image."""
    device_id = validate_device_headers(request)
    image_data = await read_checkin_image(request)
    service = CheckInService(db, face_svc=face_svc)
    result = await service.process_image(
        image_data=image_data,
        device_or_location_id=device_id,
        client_ip=client_ip,
    )
    checkins_total.labels(status=result.status).inc()
    await broadcast_result(db, result)

    if result.status == CHECKIN_FAILED:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=jsonable_encoder(result),
        )
    if result.status == CHECKIN_SPOOF:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=jsonable_encoder(result),
        )
    return result


@router.get("/checkins/live", response_model=CheckInLiveResponse)
async def live_checkins(
    limit: int = Query(default=30, ge=1, le=100),
    since: datetime | None = None,
    include_failed: bool = True,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Return recent check-ins for admin dashboard polling."""
    service = CheckInService(db)
    return CheckInLiveResponse(
        checkins=await service.list_live(
            limit=limit,
            since=since,
            include_failed=include_failed,
        )
    )


@router.post("/checkins/manual", response_model=CheckInResponse)
async def manual_checkin(
    body: ManualCheckInRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
    client_ip: str = Depends(get_client_ip),
):
    """Record an admin manual override check-in."""
    service = CheckInService(db)
    result = await service.manual_override(
        user_id=body.user_id,
        device_or_location_id=body.device_or_location_id,
        reason=body.reason,
        client_ip=client_ip,
    )
    await broadcast_result(db, result)
    return result


def _validate_ws_admin(token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(token)
    if payload.get("type") != "access" or payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")


@router.websocket("/checkins/live/ws")
async def live_checkins_ws(websocket: WebSocket, token: str | None = Query(None)):
    """Broadcast check-in events to an authenticated admin dashboard."""
    try:
        _validate_ws_admin(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await broadcaster.connect(websocket)
    await websocket.send_json({"type": "ready"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
