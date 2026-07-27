"""Audit service for logging sensitive actions."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.db_models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service to log security and data-modifying actions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_action(
        self,
        action: str,
        user_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        source_ip: str | None = None,
    ) -> None:
        """Create an append-only audit log entry with safe fallback."""
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                details=details,
                source_ip=source_ip,
            )
            self.db.add(log_entry)
            await self.db.flush()
            logger.info(f"Audit log: action={action} user_id={user_id} ip={source_ip}")
        except Exception as e:
            logger.warning("Audit log write skipped (%s)", e)
