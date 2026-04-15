"""User service: business logic for user CRUD."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_handler import hash_password
from api.models.db_models import FaceTemplate, User
from api.models.schemas import UserCreate
from api.services.audit_service import AuditService


class UserService:
    """Encapsulates user-related database operations."""

    def __init__(self, db: AsyncSession, source_ip: str | None = None) -> None:
        self.db = db
        self.source_ip = source_ip
        self.audit_svc = AuditService(db)

    async def create(self, data: UserCreate, password: str | None = None) -> User:
        """Insert a new user."""
        user = User(
            id=uuid.uuid4(),
            name=data.name,
            email=data.email,
            hashed_password=hash_password(password) if password else None,
            extra_metadata=data.metadata,
        )
        self.db.add(user)
        await self.audit_svc.log_action(
            user_id=user.id,
            action="USER_CREATE",
            details={"email": data.email},
            source_ip=self.source_ip,
        )
        await self.db.flush()
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_faces(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(FaceTemplate.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def delete(self, user: User) -> None:
        await self.audit_svc.log_action(
            user_id=user.id,
            action="USER_DELETE",
            details={"email": user.email},
            source_ip=self.source_ip,
        )
        await self.db.delete(user)
        await self.db.flush()
