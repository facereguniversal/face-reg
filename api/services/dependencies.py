"""FastAPI Dependency injection for services and data extraction."""

from fastapi import Request

from api.services.face_service import FaceService


def get_face_service(request: Request) -> FaceService:
    """Retrieve the app-scoped FaceService from FastAPI state."""
    return request.app.state.face_service


def get_client_ip(request: Request) -> str:
    """Extract client IP addressing X-Forwarded-For if available."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"
