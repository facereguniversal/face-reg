"""Tests for audit logging functionality."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.db_models import AuditLog





@pytest.mark.asyncio
async def test_user_create_logs_audit(db: AsyncSession):
    """Verify USER_CREATE action is logged when creating a user."""
    from api.services.user_service import UserService

    user_svc = UserService(db)
    user = await user_svc.create({"name": "Test User", "email": "test@example.com"}, "password")

    # Check audit log was created
    stmt = select(AuditLog).where(AuditLog.user_id == user.id)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    assert len(logs) == 1
    log = logs[0]
    assert log.action == "USER_CREATE"
    assert log.details["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_user_delete_logs_audit(db: AsyncSession):
    """Verify USER_DELETE action is logged when deleting a user."""
    from api.services.user_service import UserService

    user_svc = UserService(db)
    user = await user_svc.create({"name": "Test User", "email": "test@example.com"}, "password")

    await user_svc.delete(user)

    # Check audit log was created
    stmt = select(AuditLog).where(AuditLog.user_id == user.id)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    assert len(logs) == 2  # CREATE and DELETE
    delete_log = [log for log in logs if log.action == "USER_DELETE"][0]
    assert delete_log.details["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_face_enroll_logs_audit(db: AsyncSession):
    """Verify FACE_ENROLL action is logged when enrolling faces."""
    from api.services.face_service import FaceService
    from api.services.user_service import UserService

    user_svc = UserService(db)
    user = await user_svc.create({"name": "Test User", "email": "test@example.com"}, "password")

    face_svc = FaceService()
    # Mock image data
    image_data = [b"fake_image_data"] * 4
    result = await face_svc.enroll(user.id, image_data, db)

    # Check audit log was created
    stmt = select(AuditLog).where(AuditLog.user_id == user.id, AuditLog.action == "FACE_ENROLL")
    result = await db.execute(stmt)
    logs = result.scalars().all()

    assert len(logs) == 1
    log = logs[0]
    assert log.action == "FACE_ENROLL"
    assert "templates_enrolled" in log.details