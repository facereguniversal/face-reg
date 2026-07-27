"""Database session management (async SQLAlchemy)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

# Ensure fallback data directory exists
data_dir = Path("/tmp")
data_dir.mkdir(parents=True, exist_ok=True)

raw_db_url: str = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:////tmp/app.db",
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

_tables_created = False


async def ensure_tables_exist() -> None:
    """Ensure database tables are auto-created if not already present."""
    global _tables_created
    if not _tables_created:
        try:
            async with engine.begin() as conn:
                from api.models.db_models import Base

                await conn.run_sync(Base.metadata.create_all)
            _tables_created = True
        except Exception as e:
            logger.warning("Could not auto-create database tables: %s", e)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session safely."""
    await ensure_tables_exist()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                await session.close()
            except Exception:
                pass
