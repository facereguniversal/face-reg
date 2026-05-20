"""Pluggable liveness detection for aligned face crops."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

LIVENESS_MODEL_PATH = os.environ.get("LIVENESS_MODEL_PATH", "").strip()
LIVENESS_THRESHOLD = float(os.environ.get("LIVENESS_THRESHOLD", "0.5"))


class LivenessDetector:
    """Run anti-spoofing when a model is configured, otherwise use heuristics."""

    def __init__(self) -> None:
        self._session: Any | None = None
        self._input_name: str | None = None
        self._mode = "heuristic"
        self._load_model()

    @property
    def mode(self) -> str:
        return self._mode

    def _load_model(self) -> None:
        if not LIVENESS_MODEL_PATH:
            return

        path = Path(LIVENESS_MODEL_PATH)
        if not path.exists():
            logger.warning(
                "LIVENESS_MODEL_PATH=%s does not exist; using heuristic fallback",
                path,
            )
            return

        try:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
            self._input_name = self._session.get_inputs()[0].name
            self._mode = "onnx"
            logger.info("Loaded liveness ONNX model from %s", path)
        except Exception as exc:
            logger.warning("Failed to load liveness model: %s", exc)
            self._session = None
            self._input_name = None
            self._mode = "heuristic"

    def analyze(self, aligned_face: np.ndarray) -> dict[str, Any]:
        if self._session is not None and self._input_name is not None:
            try:
                score = self._run_onnx(aligned_face)
                return {
                    "liveness_score": score,
                    "liveness_passed": score >= LIVENESS_THRESHOLD,
                    "liveness_mode": self._mode,
                }
            except Exception as exc:
                logger.warning("Liveness ONNX inference failed: %s", exc)

        score = self._heuristic_score(aligned_face)
        return {
            "liveness_score": score,
            "liveness_passed": score >= LIVENESS_THRESHOLD,
            "liveness_mode": "heuristic",
        }

    def _run_onnx(self, aligned_face: np.ndarray) -> float:
        # MiniFASNet-style exports commonly accept 1x3x80x80 RGB tensors.
        resized = cv2.resize(aligned_face, (80, 80))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
        tensor = (rgb - 127.5) / 128.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, :, :, :]
        outputs = self._session.run(None, {self._input_name: tensor})  # type: ignore[union-attr]
        logits = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        exp = np.exp(logits - np.max(logits))
        probs = exp / np.sum(exp)
        if probs.size >= 2:
            # Silent-Face-Anti-Spoofing labels class 1 as live in common exports.
            return float(probs[1])
        return float(probs[0])

    @staticmethod
    def _heuristic_score(aligned_face: np.ndarray) -> float:
        gray = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        brightness_score = 1.0 if 40.0 <= brightness <= 220.0 else 0.25
        contrast_score = min(contrast / 64.0, 1.0)
        sharpness_score = min(sharpness / 250.0, 1.0)
        score = 0.45 * brightness_score + 0.25 * contrast_score + 0.30 * sharpness_score
        return round(float(max(0.0, min(score, 1.0))), 4)
