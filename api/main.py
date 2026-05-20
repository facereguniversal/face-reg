"""
Face Recognition API - Main application entrypoint.

Initializes the FastAPI app, registers routers, and configures middleware.
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.bootstrap import bootstrap_demo_data
from api.config import get_settings
from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.upload_limit import MaxUploadSizeMiddleware
from api.rate_limit import limiter
from api.routes import auth, checkins, faces, users
from api.services.database import dispose_engine, get_db
from api.services.face_service import FaceService

settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent.parent
COLUMN_CAPTURE_DIR = BASE_DIR / "ingestion" / "capture_ui"
CHECKIN_DIR = BASE_DIR / "ingestion" / "checkin_ui"
ADMIN_DIR = BASE_DIR / "ingestion" / "admin_ui"


def _configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "format": "%(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "loggers": {
                "api.request": {
                    "handlers": ["default"],
                    "level": settings.log_level,
                    "propagate": False,
                },
            },
            "root": {
                "handlers": ["default"],
                "level": settings.log_level,
            },
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    face_service = FaceService()
    await face_service.initialize()
    app.state.face_service = face_service
    await bootstrap_demo_data()
    yield
    await face_service.shutdown()
    await dispose_engine()


app = FastAPI(
    title="Face Recognition API",
    description=(
        "Universal face-recognition web service for enrollment, "
        "identification, and verification."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.openapi_enabled else None,
    redoc_url="/redoc" if settings.openapi_enabled else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(MaxUploadSizeMiddleware, max_bytes=settings.max_upload_bytes)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

_configure_logging()

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics"],
).instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)

if settings.enable_demo_ui:
    app.mount(
        "/demo/capture",
        StaticFiles(directory=COLUMN_CAPTURE_DIR, html=True),
        name="demo-capture",
    )
    app.mount(
        "/demo/checkin",
        StaticFiles(directory=CHECKIN_DIR, html=True),
        name="demo-checkin",
    )
    app.mount(
        "/demo/admin",
        StaticFiles(directory=ADMIN_DIR, html=True),
        name="demo-admin",
    )

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(faces.router, prefix="/api/faces", tags=["Faces"])
app.include_router(checkins.router, prefix="/api", tags=["Check-ins"])

from api.routes import identify  # noqa: E402

app.include_router(identify.router, prefix="/api", tags=["Recognition"])


@app.get("/", include_in_schema=False)
async def root():
    """Return the main entrypoints for operators and demo users."""
    payload = {
        "docs": "/docs" if settings.openapi_enabled else None,
        "health": "/api/health",
    }
    if settings.enable_demo_ui:
        payload.update(
            {
                "demo_capture": "/demo/capture/",
                "demo_checkin": "/demo/checkin/",
                "demo_admin": "/demo/admin/",
            }
        )
    return payload


@app.get("/api/health", tags=["Utility"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Return service health status; 503 when degraded for orchestrator probes."""
    health = {
        "status": "ok",
        "database": "unknown",
        "model_server": "unknown",
        "model_mode": "unknown",
    }

    try:
        await db.execute(text("SELECT 1"))
        health["database"] = "ok"
    except Exception:
        health["database"] = "down"
        health["status"] = "degraded"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{settings.model_server_url}/health")
            if res.status_code == 200:
                health["model_server"] = "ok"
                data = res.json()
                health["model_mode"] = data.get("mode", "unknown")
            else:
                health["model_server"] = "down"
                health["status"] = "degraded"
    except Exception:
        health["model_server"] = "down"
        health["status"] = "degraded"

    status_code = 503 if health["status"] == "degraded" else 200
    return JSONResponse(status_code=status_code, content=health)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
