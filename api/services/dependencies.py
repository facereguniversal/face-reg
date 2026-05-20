"""FastAPI Dependency injection for services and data extraction."""

from __future__ import annotations

from fastapi import Request

from api.config import get_settings
from api.services.face_service import FaceService


def get_face_service(request: Request) -> FaceService:
    """Retrieve the app-scoped FaceService from FastAPI state."""
    return request.app.state.face_service


def get_client_ip(request: Request) -> str:
    """Extract client IP; honor X-Forwarded-For only from trusted proxies."""
    settings = get_settings()
    client_host = request.client.host if request.client else None
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded and client_host in settings.trusted_proxy_ips:
        return forwarded.split(",")[0].strip()
    if client_host:
        return client_host
    return "0.0.0.0"
