"""Database session management (async SQLAlchemy)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

raw_db_url: str = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)

# Normalize PostgreSQL driver prefixes for async SQLAlchemy
if raw_db_url.startswith("postgresql://"):
    DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgres://"):
    DATABASE_URL = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = raw_db_url

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

fallback_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
fallback_factory = async_sessionmaker(fallback_engine, expire_on_commit=False)
fallback_initialized = False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session with resilient fallback."""
    global fallback_initialized
    try:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception as e:
        logger.warning(
            "Primary database connection failed (%s) – using SQLite fallback session", e
        )
        if not fallback_initialized:
            async with fallback_engine.begin() as conn:
                from api.models.db_models import Base

                await conn.run_sync(Base.metadata.create_all)
            fallback_initialized = True

        async with fallback_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
