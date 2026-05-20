"""Tests for check-in service behavior."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.db_models import CheckIn, FaceTemplate, User
from api.services.checkin_service import (
    CHECKIN_ALREADY,
    CHECKIN_FAILED,
    CHECKIN_MANUAL,
    CHECKIN_SPOOF,
    CHECKIN_SUCCESS,
    CheckInService,
)


class FakeFaceService:
    def __init__(self, embed_result, search_results=None):
        self.embed_result = embed_result
        self.search_results = search_results or []

    async def _get_embeddings(self, _images):
        return [self.embed_result]

    async def _search(self, _embedding, top_k=5):
        return self.search_results[:top_k]

    @staticmethod
    def _is_valid_embedding_result(item):
        if not item or not item.get("valid"):
            return False
        return bool(item.get("embedding") and any(item["embedding"]))


async def create_user_with_template(db: AsyncSession) -> tuple[User, FaceTemplate]:
    user = User(
        id=uuid.uuid4(),
        name="Jane Guest",
        email="jane@example.com",
        role="guest",
    )
    template = FaceTemplate(
        id=uuid.uuid4(),
        user_id=user.id,
        embedding=[1.0] + [0.0] * 511,
        quality_score=0.94,
    )
    db.add_all([user, template])
    await db.flush()
    return user, template


def valid_embedding():
    return {
        "embedding": [1.0] + [0.0] * 511,
        "quality": 0.95,
        "valid": True,
        "issues": [],
        "liveness_score": 0.9,
        "liveness_passed": True,
        "liveness_mode": "heuristic",
    }


@pytest.mark.asyncio
async def test_success_then_cooldown_does_not_insert_second_row(db: AsyncSession):
    user, template = await create_user_with_template(db)
    fake = FakeFaceService(
        valid_embedding(),
        [{"face_id": str(template.id), "score": 0.92}],
    )
    service = CheckInService(db, face_svc=fake)

    first = await service.process_image(b"image", "kiosk-1")
    second = await service.process_image(b"image", "kiosk-1")

    assert first.status == CHECKIN_SUCCESS
    assert first.user.user_id == user.id
    assert second.status == CHECKIN_ALREADY

    rows = (await db.execute(select(CheckIn))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == CHECKIN_SUCCESS


@pytest.mark.asyncio
async def test_unknown_face_records_failed_checkin(db: AsyncSession):
    fake = FakeFaceService(valid_embedding(), [])
    service = CheckInService(db, face_svc=fake)

    result = await service.process_image(b"image", "kiosk-1")

    assert result.status == CHECKIN_FAILED
    assert result.checkin.user_id is None
    row = (await db.execute(select(CheckIn))).scalar_one()
    assert row.status == CHECKIN_FAILED
    assert row.confidence_score == 0.0


@pytest.mark.asyncio
async def test_spoof_records_spoof_checkin(db: AsyncSession):
    fake = FakeFaceService(
        {
            "embedding": [0.0] * 512,
            "quality": 0.2,
            "valid": False,
            "issues": ["spoof_detected"],
            "liveness_score": 0.1,
            "liveness_passed": False,
            "liveness_mode": "heuristic",
        }
    )
    service = CheckInService(db, face_svc=fake)

    result = await service.process_image(b"image", "kiosk-1")

    assert result.status == CHECKIN_SPOOF
    row = (await db.execute(select(CheckIn))).scalar_one()
    assert row.status == CHECKIN_SPOOF
    assert row.user_id is None


@pytest.mark.asyncio
async def test_manual_override_records_checkin(db: AsyncSession):
    user, _template = await create_user_with_template(db)
    service = CheckInService(db)

    result = await service.manual_override(
        user_id=user.id,
        device_or_location_id="front-desk",
        reason="mask",
    )

    assert result.status == CHECKIN_MANUAL
    row = (await db.execute(select(CheckIn))).scalar_one()
    assert row.status == CHECKIN_MANUAL
    assert row.user_id == user.id


@pytest.mark.asyncio
async def test_live_feed_includes_user_details(db: AsyncSession):
    user, template = await create_user_with_template(db)
    fake = FakeFaceService(
        valid_embedding(),
        [{"face_id": str(template.id), "score": 0.92}],
    )
    service = CheckInService(db, face_svc=fake)
    await service.process_image(b"image", "kiosk-1")

    items = await service.list_live()

    assert len(items) == 1
    assert items[0].user_id == user.id
    assert items[0].user_name == "Jane Guest"
