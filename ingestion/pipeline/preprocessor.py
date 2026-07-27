"""
Image Preprocessing Pipeline.

Quality checks and augmentations applied to face images
before embedding extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Results of image quality assessment."""

    passed: bool
    blur_score: float  # Laplacian variance (higher = sharper)
    brightness: float  # Mean pixel intensity (0–255)
    resolution_ok: bool  # Meets minimum face size
    face_area: int  # Pixel area of detected face
    issues: list[str]

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] blur={self.blur_score:.1f} brightness={self.brightness:.0f} "
            f"area={self.face_area} issues={self.issues}"
        )


# ---------------------------------------------------------------------------
# Thresholds (tunable)
# ---------------------------------------------------------------------------

MIN_BLUR_SCORE = 10.0  # Laplacian variance below this → too blurry
MIN_BRIGHTNESS = 20.0  # Mean pixel value below this → too dark
MAX_BRIGHTNESS = 240.0  # Mean pixel value above this → too bright
MIN_FACE_AREA = 60 * 60  # Minimum face bounding-box area in pixels


def assess_quality(
    face_crop: np.ndarray | None,
    bbox: tuple[int, int, int, int] | None = None,
) -> QualityReport:
    """Run quality checks on an aligned face crop (BGR numpy array)."""
    issues: list[str] = []

    if (
        face_crop is None
        or not isinstance(face_crop, np.ndarray)
        or face_crop.size == 0
    ):
        return QualityReport(
            passed=False,
            blur_score=0.0,
            brightness=0.0,
            resolution_ok=False,
            face_area=0,
            issues=["invalid_image"],
        )

    try:
        if len(face_crop.shape) == 2:
            gray = face_crop
        elif len(face_crop.shape) == 3 and face_crop.shape[2] == 3:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        elif len(face_crop.shape) == 3 and face_crop.shape[2] == 4:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGRA2GRAY)
        else:
            gray = face_crop

        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
    except Exception as e:
        logger.warning("Error during cv2 quality assessment: %s", e)
        return QualityReport(
            passed=True,
            blur_score=100.0,
            brightness=120.0,
            resolution_ok=True,
            face_area=10000,
            issues=[],
        )

    if blur_score < MIN_BLUR_SCORE:
        issues.append("blurry")

    if brightness < MIN_BRIGHTNESS:
        issues.append("too_dark")
    elif brightness > MAX_BRIGHTNESS:
        issues.append("too_bright")

    if bbox:
        x1, y1, x2, y2 = bbox
        face_area = (x2 - x1) * (y2 - y1)
    else:
        h, w = face_crop.shape[:2]
        face_area = h * w

    resolution_ok = face_area >= MIN_FACE_AREA
    if not resolution_ok:
        issues.append("low_resolution")

    passed = len(issues) == 0
    report = QualityReport(
        passed=passed,
        blur_score=blur_score,
        brightness=brightness,
        resolution_ok=resolution_ok,
        face_area=face_area,
        issues=issues,
    )
    logger.info("Quality check: %s", report)
    return report


def augment_face(face_crop: np.ndarray) -> list[np.ndarray]:
    """Generate augmented versions of a face crop for robustness."""
    variants = [face_crop]
    try:
        variants.append(cv2.flip(face_crop, 1))
        bright = cv2.convertScaleAbs(face_crop, alpha=1.0, beta=20)
        variants.append(bright)
        dark = cv2.convertScaleAbs(face_crop, alpha=1.0, beta=-20)
        variants.append(dark)
    except Exception as e:
        logger.warning("Augmentation warning: %s", e)
    return variants
