"""Pydantic schemas for request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

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


CheckInStatus = Literal[
    "SUCCESS",
    "FAILED",
    "SPOOF_DETECTED",
    "MANUAL_OVERRIDE",
    "ALREADY_CHECKED_IN",
]


class CheckInResponseItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    checkin_time: datetime
    status: str
    device_or_location_id: str
    confidence_score: float | None = None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: EmailStr
    role: str = "user"
    created_at: datetime
    face_count: int = 0
    last_checkin: CheckInResponseItem | None = None

    model_config = {"from_attributes": True}


class UserSearchItem(BaseModel):
    user_id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    last_checkin: CheckInResponseItem | None = None


class UserSearchResponse(BaseModel):
    users: list[UserSearchItem]


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
# Check-ins
# ---------------------------------------------------------------------------


class CheckInUser(BaseModel):
    user_id: uuid.UUID
    name: str
    email: EmailStr
    role: str


class CheckInResponse(BaseModel):
    status: CheckInStatus
    message: str
    user: CheckInUser | None = None
    checkin: CheckInResponseItem | None = None
    confidence_score: float | None = None
    threshold: float | None = None
    cooldown_seconds: int | None = None
    issues: list[str] = Field(default_factory=list)


class CheckInLiveItem(CheckInResponseItem):
    user_name: str | None = None
    user_email: EmailStr | None = None
    user_role: str | None = None


class CheckInLiveResponse(BaseModel):
    checkins: list[CheckInLiveItem]


class ManualCheckInRequest(BaseModel):
    user_id: uuid.UUID
    device_or_location_id: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("device_or_location_id")
    @classmethod
    def normalize_device(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("device_or_location_id cannot be empty")
        return value


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    model_server: str = "ok"
    database: str = "ok"
