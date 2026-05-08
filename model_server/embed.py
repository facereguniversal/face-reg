"""
Embedding Extraction & FAISS Index Service.

Provides a lightweight FastAPI server that:
  1. Accepts images → detects/aligns → returns 512-d ArcFace embeddings
  2. Manages a FAISS index for ANN similarity search
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from detect import FaceDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FAISS_INDEX_PATH = os.environ.get("FAISS_INDEX_PATH", "./data/faiss.index")
FAISS_MAP_PATH = os.environ.get("FAISS_MAP_PATH", "./data/faiss_id_map.json")
EMBEDDING_DIM = 512

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Model Server", version="0.1.0")

detector = FaceDetector()
embedding_model: Any = None
faiss_index: Any = None
id_map: dict[int, str] = {}  # FAISS internal id → face_template UUID


# ---------------------------------------------------------------------------
# InsightFace embedding model loader
# ---------------------------------------------------------------------------


def _load_embedding_model() -> Any:
    """Lazy-load ArcFace embedding model."""
    global embedding_model
    if embedding_model is not None:
        return embedding_model

    try:
        from insightface.app import FaceAnalysis

        model = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        model.prepare(ctx_id=0, det_size=(640, 640))
        embedding_model = model
        logger.info("ArcFace embedding model loaded")
    except Exception as e:
        logger.warning(
            "insightface not available (%s) – embeddings will be random placeholders", e
        )
        embedding_model = "placeholder"
    return embedding_model


def _is_zero_vector(vector: np.ndarray) -> bool:
    return bool(np.linalg.norm(vector) <= 1e-6)


def _extract_embedding(aligned_face: np.ndarray) -> list[float] | None:
    """Extract a 512-d embedding from an aligned face crop."""
    model = _load_embedding_model()

    if model == "placeholder":
        # Return deterministic pseudo-random embedding for testing
        rng = np.random.RandomState(
            int.from_bytes(aligned_face[:4].tobytes(), "big") % (2**31)
        )
        vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return vec.tolist()

    recognition_model = model.models.get("recognition")
    if recognition_model is None:
        logger.error("InsightFace recognition model is unavailable")
        return None

    embedding = np.array(recognition_model.get_feat(aligned_face)[0], dtype=np.float32)
    if _is_zero_vector(embedding):
        return None
    embedding /= np.linalg.norm(embedding)
    return embedding.tolist()


# ---------------------------------------------------------------------------
# FAISS helpers
# ---------------------------------------------------------------------------


def _load_faiss_index():
    """Load or create FAISS index."""
    global faiss_index, id_map
    try:
        import faiss
    except ImportError:
        logger.warning("faiss not installed – search endpoints will not work")
        return

    index_path = Path(FAISS_INDEX_PATH)
    map_path = Path(FAISS_MAP_PATH)

    if index_path.exists():
        faiss_index = faiss.read_index(str(index_path))
        logger.info("Loaded FAISS index with %d vectors", faiss_index.ntotal)
        if map_path.exists():
            id_map = {int(k): v for k, v in json.loads(map_path.read_text()).items()}
    else:
        faiss_index = faiss.IndexFlatIP(
            EMBEDDING_DIM
        )  # Inner product (cosine on L2-normed vecs)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Created new FAISS FlatIP index (dim=%d)", EMBEDDING_DIM)


def _save_faiss_index():
    """Persist FAISS index and ID map to disk."""
    if faiss_index is None:
        return
    import faiss

    Path(FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss_index, FAISS_INDEX_PATH)
    Path(FAISS_MAP_PATH).write_text(json.dumps(id_map))
    logger.info("Saved FAISS index (%d vectors)", faiss_index.ntotal)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    _load_faiss_index()


@app.on_event("shutdown")
async def shutdown():
    _save_faiss_index()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class EmbedResult(BaseModel):
    embedding: list[float]
    quality: float
    valid: bool
    issues: list[str] = []


class SearchRequest(BaseModel):
    embedding: list[float]
    top_k: int = 5


class SearchHit(BaseModel):
    face_id: str
    score: float


class IndexRequest(BaseModel):
    face_id: str
    embedding: list[float]


# ---------------------------------------------------------------------------
# Quality assessment
# ---------------------------------------------------------------------------


def _compute_quality(aligned: np.ndarray) -> float:
    """Simple quality score based on Laplacian variance (sharpness)."""
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Normalise to 0–1 range (empirical: 0–500 → 0–1)
    return float(min(variance / 500.0, 1.0))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/embed")
async def embed(images: list[UploadFile] = File(...)):
    """Detect, align, and extract embeddings from uploaded images."""
    results: list[dict[str, Any]] = []
    for img_file in images:
        data = await img_file.read()
        detections = detector.detect(data)
        if not detections:
            results.append(
                {
                    "embedding": [0.0] * EMBEDDING_DIM,
                    "quality": 0.0,
                    "valid": False,
                    "issues": ["no_face_detected"],
                }
            )
            continue
        # Use the first (highest-confidence) face
        face = detections[0]
        aligned = face["aligned"]
        quality = _compute_quality(aligned)
        emb = _extract_embedding(aligned)
        if emb is None:
            results.append(
                {
                    "embedding": [0.0] * EMBEDDING_DIM,
                    "quality": quality,
                    "valid": False,
                    "issues": ["invalid_embedding"],
                }
            )
            continue
        results.append(
            {"embedding": emb, "quality": quality, "valid": True, "issues": []}
        )
    return {"results": results}


@app.post("/search")
async def search(req: SearchRequest):
    """ANN search against the FAISS index."""
    if faiss_index is None or faiss_index.ntotal == 0:
        return {"results": []}

    query = np.array([req.embedding], dtype=np.float32)
    # L2-normalise for cosine similarity via inner product
    norm = np.linalg.norm(query)
    if norm <= 1e-6:
        return {"results": []}
    query /= norm

    k = min(req.top_k, faiss_index.ntotal)
    scores, indices = faiss_index.search(query, k)

    hits: list[dict[str, Any]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        face_id = id_map.get(int(idx), str(idx))
        hits.append({"face_id": face_id, "score": float(score)})
    return {"results": hits}


@app.post("/index")
async def index_embedding(req: IndexRequest):
    """Add an embedding to the FAISS index."""
    if faiss_index is None:
        return {"status": "faiss not available"}

    vec = np.array([req.embedding], dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm <= 1e-6:
        return {"status": "invalid_embedding"}
    vec /= norm

    idx = faiss_index.ntotal  # next sequential id
    faiss_index.add(vec)
    id_map[idx] = req.face_id
    return {"status": "indexed", "internal_id": idx}


@app.get("/health")
async def health():
    total = faiss_index.ntotal if faiss_index else 0
    mode = (
        "insightface"
        if embedding_model and embedding_model != "placeholder"
        else "fallback"
    )
    return {"status": "ok", "index_size": total, "mode": mode}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("embed:app", host="0.0.0.0", port=8001, reload=True)
