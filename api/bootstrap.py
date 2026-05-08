"""Demo bootstrap helpers for local and VM-based deployments."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from api.auth.jwt_handler import hash_password
from api.models.schemas import UserCreate
from api.services.database import async_session_factory
from api.services.user_service import UserService

logger = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_enabled() -> bool:
    return _truthy(os.environ.get("BOOTSTRAP_ON_STARTUP"))


def _load_seed_users(path_str: str | None) -> list[dict[str, Any]]:
    if not path_str:
        return []

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Bootstrap users file not found: {path}")

    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        payload = payload.get("users", [])
    if not isinstance(payload, list):
        raise ValueError(
            "Bootstrap users file must contain a list or a {'users': [...]} object"
        )
    return [item for item in payload if isinstance(item, dict)]


async def _seed_user(user_data: dict[str, Any]) -> None:
    email = user_data.get("email")
    name = user_data.get("name")
    password = user_data.get("password")
    role = user_data.get("role", "user")
    metadata = dict(user_data.get("metadata") or {})
    metadata.setdefault("seeded", True)

    if not email or not name:
        raise ValueError("Bootstrapped users require both 'name' and 'email'")

    async with async_session_factory() as session:
        service = UserService(session, source_ip="bootstrap")
        existing = await service.get_by_email(email)
        if existing:
            changed = False
            if password and not existing.hashed_password:
                existing.hashed_password = hash_password(password)
                changed = True
            if existing.role != role:
                existing.role = role
                changed = True
            if metadata and existing.extra_metadata != metadata:
                existing.extra_metadata = metadata
                changed = True
            if changed:
                await session.commit()
                logger.info("Updated bootstrapped user %s", email)
            return

        await service.create(
            UserCreate(name=name, email=email, metadata=metadata),
            password=password,
            role=role,
        )
        await session.commit()
        logger.info("Created bootstrapped user %s", email)


async def bootstrap_demo_data() -> None:
    """Create the demo admin account and optional seed users on startup."""
    if not _bootstrap_enabled():
        return

    users_to_seed: list[dict[str, Any]] = []
    admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    admin_password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    admin_name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Demo Admin")

    if admin_email and admin_password:
        users_to_seed.append(
            {
                "name": admin_name,
                "email": admin_email,
                "password": admin_password,
                "role": "admin",
                "metadata": {"seeded_admin": True},
            }
        )

    users_to_seed.extend(_load_seed_users(os.environ.get("BOOTSTRAP_USERS_FILE")))
    if not users_to_seed:
        logger.info("Bootstrap was enabled but no users were configured")
        return

    for user in users_to_seed:
        await _seed_user(user)
