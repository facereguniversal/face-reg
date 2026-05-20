"""Prometheus metrics for business operations."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

checkins_total = Counter(
    "face_checkins_total",
    "Check-in attempts by terminal status",
    ["status"],
)

identify_duration_seconds = Histogram(
    "face_identify_duration_seconds",
    "Time spent in identify flow",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

model_server_errors_total = Counter(
    "face_model_server_errors_total",
    "Model server HTTP or transport failures",
)
