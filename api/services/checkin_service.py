"""Check-in orchestration and query helpers."""

from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.db_models import CheckIn, FaceTemplate, User
from api.models.schemas import (
    CheckInLiveItem,
    CheckInResponse,
    CheckInResponseItem,
    CheckInUser,
    UserSearchItem,
)
from api.config import get_settings
from api.services.audit_service import AuditService
from api.services.face_service import FaceService

_settings = get_settings()
CHECKIN_SIMILARITY_THRESHOLD: float = _settings.effective_checkin_similarity_threshold
CHECKIN_COOLDOWN_SECONDS: int = _settings.checkin_cooldown_seconds

CHECKIN_SUCCESS = "SUCCESS"
CHECKIN_FAILED = "FAILED"
CHECKIN_SPOOF = "SPOOF_DETECTED"
CHECKIN_MANUAL = "MANUAL_OVERRIDE"
CHECKIN_ALREADY = "ALREADY_CHECKED_IN"

TERMINAL_STATUSES = {CHECKIN_SUCCESS, CHECKIN_FAILED, CHECKIN_SPOOF, CHECKIN_MANUAL}
COOLDOWN_STATUSES = {CHECKIN_SUCCESS, CHECKIN_MANUAL}


@dataclass(frozen=True)
class MatchCandidate:
    user: User
    score: float


def decode_base64_image(value: str) -> bytes:
    """Decode plain base64 or a data URL image payload."""
    if "," in value and value.lower().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image payload",
        ) from exc


def parse_device_tokens(raw: str | None = None) -> dict[str, str]:
    """Parse CHECKIN_DEVICE_TOKENS as comma-separated device:token pairs."""
    if raw is None:
        raw = os.environ.get(
            "CHECKIN_DEVICE_TOKENS", get_settings().checkin_device_tokens
        )
    tokens: dict[str, str] = {}
    for part in raw.split(","):
        if not part.strip() or ":" not in part:
            continue
        device_id, token = part.split(":", 1)
        device_id = device_id.strip()
        token = token.strip()
        if device_id and token:
            tokens[device_id] = token
    return tokens


def checkin_item_from_model(checkin: CheckIn) -> CheckInResponseItem:
    return CheckInResponseItem(
        id=checkin.id,
        user_id=checkin.user_id,
        checkin_time=checkin.checkin_time,
        status=checkin.status,
        device_or_location_id=checkin.device_or_location_id,
        confidence_score=checkin.confidence_score,
    )


def checkin_user_from_model(user: User) -> CheckInUser:
    return CheckInUser(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
    )


class CheckInService:
    """Business logic for kiosk check-ins and admin live views."""

    def __init__(self, db: AsyncSession, face_svc: FaceService | None = None) -> None:
        self.db = db
        self.face_svc = face_svc
        self.audit_svc = AuditService(db)

    async def process_image(
        self,
        image_data: bytes,
        device_or_location_id: str,
        client_ip: str | None = None,
    ) -> CheckInResponse:
        if self.face_svc is None:
            raise RuntimeError("FaceService is required for image check-ins")

        embed_resp = await self.face_svc._get_embeddings([image_data])
        first = embed_resp[0] if embed_resp else None
        issues = list((first or {}).get("issues") or [])

        if first and first.get("liveness_passed") is False:
            checkin = await self._record_checkin(
                status=CHECKIN_SPOOF,
                user_id=None,
                device_or_location_id=device_or_location_id,
                confidence_score=first.get("liveness_score"),
            )
            await self.audit_svc.log_action(
                user_id=None,
                action="CHECKIN_SPOOF_DETECTED",
                details={
                    "device_or_location_id": device_or_location_id,
                    "liveness_score": first.get("liveness_score"),
                    "liveness_mode": first.get("liveness_mode"),
                    "issues": issues,
                },
                source_ip=client_ip,
            )
            return CheckInResponse(
                status=CHECKIN_SPOOF,
                message="Spoof detected. Please check in with reception.",
                checkin=checkin_item_from_model(checkin),
                confidence_score=first.get("liveness_score"),
                threshold=CHECKIN_SIMILARITY_THRESHOLD,
                issues=issues or ["spoof_detected"],
            )

        if not self.face_svc._is_valid_embedding_result(first):
            checkin = await self._record_checkin(
                status=CHECKIN_FAILED,
                user_id=None,
                device_or_location_id=device_or_location_id,
                confidence_score=0.0,
            )
            await self.audit_svc.log_action(
                user_id=None,
                action="CHECKIN_FAILED",
                details={
                    "device_or_location_id": device_or_location_id,
                    "reason": "invalid_embedding",
                    "issues": issues,
                },
                source_ip=client_ip,
            )
            return CheckInResponse(
                status=CHECKIN_FAILED,
                message="Face not recognized. Please visit reception.",
                checkin=checkin_item_from_model(checkin),
                confidence_score=0.0,
                threshold=CHECKIN_SIMILARITY_THRESHOLD,
                issues=issues or ["invalid_embedding"],
            )

        candidate = await self._best_match(first["embedding"])
        if candidate is None or candidate.score < CHECKIN_SIMILARITY_THRESHOLD:
            score = candidate.score if candidate else 0.0
            checkin = await self._record_checkin(
                status=CHECKIN_FAILED,
                user_id=None,
                device_or_location_id=device_or_location_id,
                confidence_score=score,
            )
            await self.audit_svc.log_action(
                user_id=None,
                action="CHECKIN_FAILED",
                details={
                    "device_or_location_id": device_or_location_id,
                    "reason": "unknown_face",
                    "score": round(score, 4),
                    "threshold": CHECKIN_SIMILARITY_THRESHOLD,
                },
                source_ip=client_ip,
            )
            return CheckInResponse(
                status=CHECKIN_FAILED,
                message="Face not recognized. Please visit reception.",
                checkin=checkin_item_from_model(checkin),
                confidence_score=round(score, 4),
                threshold=CHECKIN_SIMILARITY_THRESHOLD,
                issues=["unknown_face"],
            )

        recent = await self._recent_checkin(candidate.user.id)
        if recent is not None:
            return CheckInResponse(
                status=CHECKIN_ALREADY,
                message="Already checked in.",
                user=checkin_user_from_model(candidate.user),
                checkin=checkin_item_from_model(recent),
                confidence_score=round(candidate.score, 4),
                threshold=CHECKIN_SIMILARITY_THRESHOLD,
                cooldown_seconds=CHECKIN_COOLDOWN_SECONDS,
            )

        checkin = await self._record_checkin(
            status=CHECKIN_SUCCESS,
            user_id=candidate.user.id,
            device_or_location_id=device_or_location_id,
            confidence_score=candidate.score,
        )
        await self.audit_svc.log_action(
            user_id=candidate.user.id,
            action="CHECKIN_SUCCESS",
            details={
                "device_or_location_id": device_or_location_id,
                "score": round(candidate.score, 4),
                "threshold": CHECKIN_SIMILARITY_THRESHOLD,
            },
            source_ip=client_ip,
        )
        return CheckInResponse(
            status=CHECKIN_SUCCESS,
            message=f"Welcome, {candidate.user.name}.",
            user=checkin_user_from_model(candidate.user),
            checkin=checkin_item_from_model(checkin),
            confidence_score=round(candidate.score, 4),
            threshold=CHECKIN_SIMILARITY_THRESHOLD,
        )

    async def manual_override(
        self,
        user_id: uuid.UUID,
        device_or_location_id: str,
        reason: str | None = None,
        client_ip: str | None = None,
    ) -> CheckInResponse:
        user = await self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        checkin = await self._record_checkin(
            status=CHECKIN_MANUAL,
            user_id=user.id,
            device_or_location_id=device_or_location_id,
            confidence_score=None,
        )
        await self.audit_svc.log_action(
            user_id=user.id,
            action="CHECKIN_MANUAL_OVERRIDE",
            details={
                "device_or_location_id": device_or_location_id,
                "reason": reason,
            },
            source_ip=client_ip,
        )
        return CheckInResponse(
            status=CHECKIN_MANUAL,
            message=f"Manual check-in recorded for {user.name}.",
            user=checkin_user_from_model(user),
            checkin=checkin_item_from_model(checkin),
        )

    async def get_live_item(self, checkin_id: uuid.UUID) -> CheckInLiveItem | None:
        stmt = (
            select(CheckIn, User)
            .outerjoin(User, CheckIn.user_id == User.id)
            .where(CheckIn.id == checkin_id)
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            return None
        checkin, user = row
        return self._live_item(checkin, user)

    async def list_live(
        self,
        limit: int = 30,
        since: datetime | None = None,
        include_failed: bool = True,
    ) -> list[CheckInLiveItem]:
        limit = max(1, min(limit, 100))
        stmt = select(CheckIn, User).outerjoin(User, CheckIn.user_id == User.id)
        conditions = []
        if since is not None:
            conditions.append(CheckIn.checkin_time > since)
        if not include_failed:
            conditions.append(CheckIn.status.in_([CHECKIN_SUCCESS, CHECKIN_MANUAL]))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(CheckIn.checkin_time)).limit(limit)
        rows = (await self.db.execute(stmt)).all()
        return [self._live_item(checkin, user) for checkin, user in rows]

    async def search_users(
        self, query: str | None = None, limit: int = 20
    ) -> list[UserSearchItem]:
        limit = max(1, min(limit, 50))
        stmt = select(User)
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
        stmt = stmt.order_by(User.name).limit(limit)
        users = (await self.db.execute(stmt)).scalars().all()
        last_checkins = await self.last_checkins_for_users([user.id for user in users])
        return [
            UserSearchItem(
                user_id=user.id,
                name=user.name,
                email=user.email,
                role=user.role,
                last_checkin=(
                    checkin_item_from_model(last_checkins[user.id])
                    if user.id in last_checkins
                    else None
                ),
            )
            for user in users
        ]

    async def last_checkins_for_users(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, CheckIn]:
        if not user_ids:
            return {}

        stmt = (
            select(CheckIn)
            .where(CheckIn.user_id.in_(user_ids))
            .order_by(CheckIn.user_id, desc(CheckIn.checkin_time))
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        latest: dict[uuid.UUID, CheckIn] = {}
        for row in rows:
            if row.user_id is not None and row.user_id not in latest:
                latest[row.user_id] = row
        return latest

    async def _best_match(self, embedding: list[float]) -> MatchCandidate | None:
        # SQLite in-memory fallback for local CI/CD and unit tests
        is_sqlite = "sqlite" in str(self.db.bind.url) if self.db.bind else False
        if is_sqlite:
            stmt = select(FaceTemplate, User).join(User, FaceTemplate.user_id == User.id)
            rows = (await self.db.execute(stmt)).all()
            if not rows:
                return None
            best_candidate = None
            best_score = -1.0
            for tpl, user in rows:
                if tpl.embedding:
                    score = FaceService._cosine_similarity(embedding, tpl.embedding)
                    if score > best_score:
                        best_score = score
                        best_candidate = MatchCandidate(user=user, score=score)
            return best_candidate

        stmt = (
            select(FaceTemplate, User, FaceTemplate.embedding.cosine_distance(embedding).label("distance"))
            .join(User, FaceTemplate.user_id == User.id)
            .order_by("distance")
            .limit(1)
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            return None
        tpl, user, distance = row
        score = 1.0 - float(distance)
        return MatchCandidate(user=user, score=score)

    async def _recent_checkin(self, user_id: uuid.UUID) -> CheckIn | None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=CHECKIN_COOLDOWN_SECONDS
        )
        stmt = (
            select(CheckIn)
            .where(
                CheckIn.user_id == user_id,
                CheckIn.status.in_(list(COOLDOWN_STATUSES)),
                CheckIn.checkin_time >= cutoff,
            )
            .order_by(desc(CheckIn.checkin_time))
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _record_checkin(
        self,
        status: str,
        user_id: uuid.UUID | None,
        device_or_location_id: str,
        confidence_score: float | None,
    ) -> CheckIn:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Unsupported check-in status: {status}")
        checkin = CheckIn(
            id=uuid.uuid4(),
            user_id=user_id,
            status=status,
            device_or_location_id=device_or_location_id,
            confidence_score=(
                round(float(confidence_score), 4)
                if confidence_score is not None
                else None
            ),
        )
        self.db.add(checkin)
        await self.db.flush()
        return checkin

    @staticmethod
    def _live_item(checkin: CheckIn, user: User | None) -> CheckInLiveItem:
        return CheckInLiveItem(
            id=checkin.id,
            user_id=checkin.user_id,
            checkin_time=checkin.checkin_time,
            status=checkin.status,
            device_or_location_id=checkin.device_or_location_id,
            confidence_score=checkin.confidence_score,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            user_role=user.role if user else None,
        )
