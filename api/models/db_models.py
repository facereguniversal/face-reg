"""SQLAlchemy ORM models mapping to PostgreSQL tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Index,
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Registered individuals."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    is_active: Mapped[bool] = mapped_column(default=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    face_templates: Mapped[list[FaceTemplate]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    images: Mapped[list[Image]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
    checkins: Mapped[list[CheckIn]] = relationship(back_populates="user")


class FaceTemplate(Base):
    """Stored face embeddings (one or more per user)."""

    __tablename__ = "face_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Embedding stored as pgvector type.
    embedding: Mapped[list | None] = mapped_column(Vector(512), nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="arcface_r100")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("images.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user: Mapped[User] = relationship(back_populates="face_templates")


class Image(Base):
    """Raw or aligned face images (pointers to file/S3 storage)."""

    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filepath: Mapped[str] = mapped_column(Text, nullable=False)
    capture_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    resolution: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="images")


class CheckIn(Base):
    """Stateful kiosk check-in event."""

    __tablename__ = "checkins"
    __table_args__ = (
        Index("idx_checkins_time", "checkin_time"),
        Index("idx_checkins_user_time", "user_id", "checkin_time"),
        Index("idx_checkins_status_time", "status", "checkin_time"),
        Index("idx_checkins_device_time", "device_or_location_id", "checkin_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    checkin_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    device_or_location_id: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="checkins")


class AuditLog(Base):
    """Append-only operation log for compliance and incident response."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="audit_logs")


class APIToken(Base):
    """JWT refresh tokens / API keys."""

    __tablename__ = "api_tokens"

    token: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    revoked: Mapped[bool] = mapped_column(default=False)
