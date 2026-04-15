"""
Face Recognition API - Main application entrypoint.

Initializes the FastAPI app, registers routers, and configures middleware.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, faces, users
from api.services.face_service import FaceService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: initialize FAISS index and model server connection
    face_service = FaceService()
    await face_service.initialize()
    app.state.face_service = face_service
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
    lifespan=lifespan,
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


@app.get("/api/health", tags=["Utility"])
async def health_check():
    """Return service health status."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
