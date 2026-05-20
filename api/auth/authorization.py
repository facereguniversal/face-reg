"""Shared authorization helpers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status


def require_self_or_admin(user_id: uuid.UUID, caller: dict[str, Any]) -> None:
    """Allow access only when caller is the same user or an admin."""
    caller_id = caller.get("sub")
    if caller.get("role") == "admin":
        return
    if caller_id and str(user_id) == str(caller_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this user",
    )
