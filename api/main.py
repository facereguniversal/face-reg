"""
Face Recognition API - Main application entrypoint.

Initializes the FastAPI app, registers routers, and configures middleware.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.bootstrap import bootstrap_demo_data
from api.routes import auth, faces, users
from api.services.database import get_db, engine
from api.services.face_service import FaceService
from api.models.db_models import Base

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: auto-create database schema if connected
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.warning("Could not auto-create database tables on startup: %s", e)

    # Initialize FAISS index and model server connection
    face_service = FaceService()
    await face_service.initialize()
    app.state.face_service = face_service
    await bootstrap_demo_data()
    yield
    # Shutdown: persist FAISS index to disk
    await face_service.shutdown()


app = FastAPI(
    title="Face Recognition API",
    description=(
        "Universal face-recognition web service for enrollment, "
        "identification, and verification."
    ),
    version="0.1.0",
    debug=True,
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Preserve status codes and details for standard HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global catch-all exception handler returning JSON error responses for unexpected errors."""
    import traceback

    error_detail = f"{type(exc).__name__}: {str(exc)}"
    logger.error(
        "Unhandled Exception on %s: %s\n%s",
        request.url.path,
        error_detail,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail, "path": request.url.path},
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(faces.router, prefix="/api/faces", tags=["Faces"])

# Identification and verification routes live on the faces router but are
# mounted at the /api level for cleaner URLs.
from api.routes import identify  # noqa: E402

app.include_router(identify.router, prefix="/api", tags=["Recognition"])


@app.get("/", include_in_schema=False)
async def root():
    """Return the main entrypoints for operators and demo users."""
    return {
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health", tags=["Utility"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Return service health status."""
    health = {
        "status": "ok",
        "database": "unknown",
        "model_server": "unknown",
        "model_mode": "unknown",
    }

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        health["database"] = "ok"
    except Exception:
        health["database"] = "down"
        health["status"] = "degraded"

    # Check Model Server
    try:
        import os
        import httpx

        model_server_url = os.environ.get("MODEL_SERVER_URL", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{model_server_url}/health")
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

    return health


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
