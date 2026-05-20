"""Model server / ML pipeline tests."""

from __future__ import annotations

import cv2
import numpy as np
import pytest


def make_face_bytes() -> bytes:
    img = np.random.randint(80, 180, (160, 160, 3), dtype=np.uint8)
    img[40:120, 40:120] = 255
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestPreprocessor:
    """Quality assessment and augmentation tests."""

    def test_quality_good_image(self):
        """A sharp, well-lit face crop should pass quality checks."""
        from ingestion.pipeline.preprocessor import assess_quality

        # Create a synthetic sharp face-like image (112×112 with texture)
        img = np.random.randint(80, 180, (112, 112, 3), dtype=np.uint8)
        # Add edges to increase Laplacian variance
        img[40:70, 40:70] = 255
        report = assess_quality(img)
        assert report.blur_score > 0, "Should compute a blur score"
        assert report.brightness > 0, "Should compute brightness"

    def test_quality_dark_image(self):
        """A very dark image should be flagged."""
        from ingestion.pipeline.preprocessor import assess_quality

        dark = np.zeros((112, 112, 3), dtype=np.uint8)
        report = assess_quality(dark)
        assert not report.passed
        assert "too_dark" in report.issues

    def test_augment_produces_variants(self):
        """Augmentation should produce >1 variant."""
        from ingestion.pipeline.preprocessor import augment_face

        img = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        variants = augment_face(img)
        assert len(variants) >= 2


class TestDetector:
    """Face detector smoke tests (uses OpenCV fallback)."""

    def test_detect_returns_list(self):
        """Detector should return a list (possibly empty) without crashing."""
        from model_server.detect import FaceDetector

        det = FaceDetector()
        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", blank)
        results = det.detect(buf.tobytes())
        assert isinstance(results, list)


class TestFaceServiceValidation:
    """Face service validation rules around embeddings."""

    @pytest.mark.asyncio
    async def test_validate_rejects_invalid_embedding(self, monkeypatch):
        from api.services.face_service import FaceService

        face_svc = FaceService()

        async def fake_get_embeddings(_images):
            return [
                {
                    "embedding": [0.0] * 512,
                    "quality": 1.0,
                    "valid": False,
                    "issues": ["invalid_embedding"],
                }
            ]

        monkeypatch.setattr(face_svc, "_get_embeddings", fake_get_embeddings)

        result = await face_svc.validate(make_face_bytes())

        assert not result.passed
        assert "invalid_embedding" in result.issues

    @pytest.mark.asyncio
    async def test_non_zero_embedding_check(self):
        from api.services.face_service import FaceService

        face_svc = FaceService()
        assert face_svc._is_non_zero_embedding([1.0] + [0.0] * 511)
        assert not face_svc._is_non_zero_embedding([0.0] * 512)


class TestLiveness:
    """Liveness fallback behavior."""

    def test_heuristic_liveness_returns_fields(self):
        from model_server.liveness import LivenessDetector

        detector = LivenessDetector()
        img = np.random.randint(70, 190, (112, 112, 3), dtype=np.uint8)
        result = detector.analyze(img)

        assert result["liveness_mode"] in {"heuristic", "onnx"}
        assert 0.0 <= result["liveness_score"] <= 1.0
        assert isinstance(result["liveness_passed"], bool)
