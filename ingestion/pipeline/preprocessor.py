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
    face_crop: np.ndarray,
    bbox: tuple[int, int, int, int] | None = None,
) -> QualityReport:
    """Run quality checks on an aligned face crop (BGR numpy array).

    Parameters
    ----------
    face_crop : np.ndarray
        The (aligned) face image, shape (H, W, 3), BGR.
    bbox : tuple, optional
        Original bounding box (x1, y1, x2, y2) used to compute pixel area.
        If *None*, the crop dimensions are used.

    Returns
    -------
    QualityReport
    """
    issues: list[str] = []
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    # Blur
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < MIN_BLUR_SCORE:
        issues.append("blurry")

    # Brightness
    brightness = float(gray.mean())
    if brightness < MIN_BRIGHTNESS:
        issues.append("too_dark")
    elif brightness > MAX_BRIGHTNESS:
        issues.append("too_bright")

    # Resolution
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


# ---------------------------------------------------------------------------
# Optional augmentations
# ---------------------------------------------------------------------------


def augment_face(face_crop: np.ndarray) -> list[np.ndarray]:
    """Generate augmented versions of a face crop for robustness.

    Returns the original plus augmented variants.
    """
    variants = [face_crop]

    # Horizontal flip
    variants.append(cv2.flip(face_crop, 1))

    # Slight brightness change
    bright = cv2.convertScaleAbs(face_crop, alpha=1.0, beta=20)
    variants.append(bright)

    dark = cv2.convertScaleAbs(face_crop, alpha=1.0, beta=-20)
    variants.append(dark)

    return variants
