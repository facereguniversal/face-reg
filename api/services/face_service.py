"""Face service: embedding extraction, FAISS indexing, enroll/identify/verify."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx
import cv2
import numpy as np
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.db_models import FaceTemplate, User
from api.models.schemas import (
    EnrollResponse,
    IdentifyResponse,
    MatchResult,
    VerifyResponse,
)
from api.services.audit_service import AuditService
from ingestion.pipeline.preprocessor import assess_quality

logger = logging.getLogger(__name__)

MODEL_SERVER_URL: str = os.environ.get(
    "MODEL_SERVER_URL", "http://localhost:8001"
)
SIMILARITY_THRESHOLD: float = float(os.environ.get("SIMILARITY_THRESHOLD", "0.6"))


class FaceService:
    """Orchestrates face enrollment, identification, and verification.

    Delegates heavy ML work (detection, alignment, embedding) to the
    external model server via HTTP.
    """

    async def initialize(self) -> None:
        """Called on app startup to warm up connections."""
        logger.info("FaceService initialising – checking model server at %s", MODEL_SERVER_URL)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{MODEL_SERVER_URL}/health")
                res.raise_for_status()
                logger.info("Model server connected: %s", res.json())
        except Exception as e:
            logger.warning("Failed to connect to model server during initialization: %s", e)

    async def shutdown(self) -> None:
        """Called on app shutdown."""
        logger.info("FaceService shutting down")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_embeddings(self, image_data: list[bytes]) -> list[dict[str, Any]]:
        """Send images to model server, receive embeddings + quality scores."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = [
                ("images", (f"face_{i}.jpg", data, "image/jpeg"))
                for i, data in enumerate(image_data)
            ]
            resp = await client.post(f"{MODEL_SERVER_URL}/embed", files=files)
            resp.raise_for_status()
            return resp.json()["results"]  # [{embedding: [...], quality: 0.9}, ...]

    async def _search(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Query model server FAISS index for nearest neighbours."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{MODEL_SERVER_URL}/search",
                json={"embedding": embedding, "top_k": top_k},
            )
            resp.raise_for_status()
            return resp.json()["results"]  # [{face_id, score}, ...]

    # ------------------------------------------------------------------
    # Enroll
    # ------------------------------------------------------------------

    async def enroll(
        self,
        user_id: uuid.UUID,
        image_data: list[bytes],
        db: AsyncSession,
        client_ip: str | None = None,
    ) -> EnrollResponse:
        """Run the full enrollment pipeline for a user's face images."""
        audit_svc = AuditService(db)
        
        # 1. Preprocess and quality check images
        valid_images = []
        for i, data in enumerate(image_data):
            # Decode bytes to numpy array
            np_arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            
            report = assess_quality(img)
            if report.passed:
                valid_images.append(data)
            else:
                logger.warning(f"Image {i} for user {user_id} failed quality check: {report}")

        if len(valid_images) < 4:
            raise HTTPException(status_code=400, detail=f"Only {len(valid_images)} images passed quality checks. Minimum 4 required.")

        # 2. Extract embeddings
        embeddings_resp = await self._get_embeddings(valid_images)

        template_ids: list[uuid.UUID] = []
        quality_scores: list[float] = []

        for item in embeddings_resp:
            tid = uuid.uuid4()
            template = FaceTemplate(
                id=tid,
                user_id=user_id,
                embedding=item["embedding"],
                quality_score=item.get("quality"),
            )
            db.add(template)
            template_ids.append(tid)
            quality_scores.append(item.get("quality", 0.0))

        await db.flush()

        # Ask model server to index the new embeddings
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tid, item in zip(template_ids, embeddings_resp):
                await client.post(
                    f"{MODEL_SERVER_URL}/index",
                    json={
                        "face_id": str(tid),
                        "embedding": item["embedding"],
                    },
                )
        
        await audit_svc.log_action(
            user_id=user_id,
            action="FACE_ENROLL",
            details={"templates_enrolled": len(template_ids), "quality_scores": quality_scores},
            source_ip=client_ip,
        )

        return EnrollResponse(
            template_ids=template_ids,
            quality_scores=quality_scores,
        )

    # ------------------------------------------------------------------
    # Identify (1:N)
    # ------------------------------------------------------------------

    async def identify(
        self,
        image_data: bytes,
        db: AsyncSession,
        client_ip: str | None = None,
    ) -> IdentifyResponse:
        """Identify a face from a single image against all enrolled faces."""
        t0 = time.perf_counter()

        embed_resp = await self._get_embeddings([image_data])
        if not embed_resp:
            return IdentifyResponse(matches=[], latency_ms=0)

        embedding = embed_resp[0]["embedding"]
        search_results = await self._search(embedding)

        matches: list[MatchResult] = []
        for hit in search_results:
            if hit["score"] < SIMILARITY_THRESHOLD:
                continue
            # Resolve user from face template
            stmt = (
                select(FaceTemplate, User)
                .join(User, FaceTemplate.user_id == User.id)
                .where(FaceTemplate.id == uuid.UUID(hit["face_id"]))
            )
            row = (await db.execute(stmt)).first()
            if row:
                tpl, user = row
                matches.append(
                    MatchResult(
                        user_id=user.id,
                        name=user.name,
                        score=round(hit["score"], 4),
                    )
                )
        
        audit_svc = AuditService(db)
        await audit_svc.log_action(
            user_id=None,
            action="FACE_IDENTIFY",
            details={
                "matches": [{"user_id": str(m.user_id), "score": m.score} for m in matches],
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
            },
            source_ip=client_ip,
        )

        latency = (time.perf_counter() - t0) * 1000
        return IdentifyResponse(matches=matches, latency_ms=round(latency, 1))

    # ------------------------------------------------------------------
    # Verify (1:1)
    # ------------------------------------------------------------------

    async def verify(
        self,
        user_id: uuid.UUID,
        image_data: bytes,
        db: AsyncSession,
        client_ip: str | None = None,
    ) -> VerifyResponse | None:
        """Verify a face against a specific user's enrolled templates."""
        embed_resp = await self._get_embeddings([image_data])
        if not embed_resp:
            return VerifyResponse(verified=False, score=0.0, threshold=SIMILARITY_THRESHOLD)

        query_embedding = embed_resp[0]["embedding"]

        stmt = select(FaceTemplate).where(FaceTemplate.user_id == user_id)
        result = await db.execute(stmt)
        templates = result.scalars().all()
        if not templates:
            return None

        # Compare against each stored template, take best score
        best_score = 0.0
        for tpl in templates:
            if tpl.embedding:
                score = self._cosine_similarity(query_embedding, tpl.embedding)
                best_score = max(best_score, score)
                
        verified = best_score >= SIMILARITY_THRESHOLD
        
        audit_svc = AuditService(db)
        await audit_svc.log_action(
            user_id=user_id,
            action="FACE_VERIFY",
            details={"verified": verified, "score": round(best_score, 4)},
            source_ip=client_ip,
        )

        return VerifyResponse(
            verified=verified,
            score=round(best_score, 4),
            threshold=SIMILARITY_THRESHOLD,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, image_data: bytes) -> ValidateResponse:
        """Validate a single image for quality without enrolling."""
        # 1. Local quality check
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return ValidateResponse(passed=False, quality_score=None, issues=["invalid_image"])
        
        report = assess_quality(img)
        issues = []
        if not report.passed:
            issues.extend(report.issues)

        # 2. Model server check (face presence)
        embed_resp = await self._get_embeddings([image_data])
        if not embed_resp:
            issues.append("no_face_detected")
            return ValidateResponse(passed=False, quality_score=None, issues=issues)
        
        quality = embed_resp[0].get("quality", 0.0)
        if quality <= 0.5:
            issues.append("low_quality")
            
        passed = len(issues) == 0
        return ValidateResponse(passed=passed, quality_score=quality, issues=issues)

    # ------------------------------------------------------------------
    # Template CRUD helpers
    # ------------------------------------------------------------------

    async def get_template(
        self, template_id: uuid.UUID, db: AsyncSession
    ) -> FaceTemplate | None:
        stmt = select(FaceTemplate).where(FaceTemplate.id == template_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_template(
        self, template_id: uuid.UUID, db: AsyncSession
    ) -> None:
        template = await self.get_template(template_id, db)
        if template:
            await db.delete(template)
            await db.flush()

    # ------------------------------------------------------------------
    # Math
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
