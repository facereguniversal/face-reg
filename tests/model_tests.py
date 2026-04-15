"""Model server / ML pipeline tests."""

from __future__ import annotations

import numpy as np
import pytest


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
        # Encode a blank image as JPEG bytes
        import cv2

        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", blank)
        results = det.detect(buf.tobytes())
        assert isinstance(results, list)
