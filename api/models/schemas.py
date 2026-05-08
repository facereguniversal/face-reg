"""Pydantic schemas for request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    metadata: dict[str, Any] | None = None


class UserResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: EmailStr
    created_at: datetime
    face_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Face Templates
# ---------------------------------------------------------------------------


class FaceTemplateResponse(BaseModel):
    face_id: uuid.UUID
    user_id: uuid.UUID
    model: str
    quality_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollResponse(BaseModel):
    template_ids: list[uuid.UUID]
    status: str = "enrolled"
    quality_scores: list[float]


# ---------------------------------------------------------------------------
# Recognition
# ---------------------------------------------------------------------------


class MatchResult(BaseModel):
    user_id: uuid.UUID
    name: str
    score: float


class IdentifyResponse(BaseModel):
    matches: list[MatchResult]
    latency_ms: float


class IdentifyBatchResult(BaseModel):
    image_index: int
    matches: list[MatchResult]


class IdentifyBatchResponse(BaseModel):
    results: list[IdentifyBatchResult]


class VerifyResponse(BaseModel):
    verified: bool
    score: float
    threshold: float


class ValidateResponse(BaseModel):
    passed: bool
    quality_score: float | None
    issues: list[str]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    model_server: str = "ok"
    database: str = "ok"
