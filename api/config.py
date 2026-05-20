"""Centralized application settings (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "CHANGE_ME_IN_PRODUCTION"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    secret_key: str = Field(default=DEFAULT_SECRET_KEY, alias="SECRET_KEY")
    database_url: str = Field(
        default="postgresql+asyncpg://faceuser:facepass@localhost:5432/facedb",
        alias="DATABASE_URL",
    )
    access_token_expire_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        alias="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=False, alias="CORS_ALLOW_CREDENTIALS")

    model_server_url: str = Field(
        default="http://localhost:8001", alias="MODEL_SERVER_URL"
    )
    similarity_threshold: float = Field(default=0.6, alias="SIMILARITY_THRESHOLD")
    checkin_similarity_threshold: float | None = Field(
        default=None, alias="CHECKIN_SIMILARITY_THRESHOLD"
    )
    checkin_cooldown_seconds: int = Field(default=300, alias="CHECKIN_COOLDOWN_SECONDS")
    checkin_device_tokens: str = Field(default="", alias="CHECKIN_DEVICE_TOKENS")

    bootstrap_on_startup: bool = Field(default=False, alias="BOOTSTRAP_ON_STARTUP")
    bootstrap_admin_name: str = Field(default="Demo Admin", alias="BOOTSTRAP_ADMIN_NAME")
    bootstrap_admin_email: str | None = Field(
        default=None, alias="BOOTSTRAP_ADMIN_EMAIL"
    )
    bootstrap_admin_password: str | None = Field(
        default=None, alias="BOOTSTRAP_ADMIN_PASSWORD"
    )
    bootstrap_users_file: str | None = Field(default=None, alias="BOOTSTRAP_USERS_FILE")

    enable_demo_ui: bool = Field(default=True, alias="ENABLE_DEMO_UI")
    trusted_proxy_ips: list[str] = Field(
        default_factory=list, alias="TRUSTED_PROXY_IPS"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")

    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")

    @field_validator("cors_origins", "trusted_proxy_ips", mode="before")
    @classmethod
    def _split_csv(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item.strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).split(",") if part.strip()]

    @model_validator(mode="after")
    def _production_guardrails(self) -> Settings:
        if self.environment != "production":
            return self

        if not self.secret_key or self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value in production"
            )
        if self.bootstrap_on_startup:
            raise ValueError("BOOTSTRAP_ON_STARTUP must be false in production")
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS must be an explicit allowlist in production (no wildcard)"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def effective_checkin_similarity_threshold(self) -> float:
        if self.checkin_similarity_threshold is not None:
            return self.checkin_similarity_threshold
        return self.similarity_threshold

    @property
    def openapi_enabled(self) -> bool:
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
