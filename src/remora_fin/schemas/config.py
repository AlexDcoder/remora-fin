"""Configuration schemas — app settings loaded from .env / config files."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class AWSConfig(BaseModel):
    """AWS connection configuration."""

    model_config = ConfigDict(frozen=True)

    profile: str = "default"
    region: str = "us-east-1"
    role_arn: str | None = None


class CacheConfig(BaseModel):
    """Local cache configuration for AWS API responses."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    ttl_seconds: int = Field(default=3600, ge=60)
    directory: Path = Field(default=Path.home() / ".remora" / "cache")


class UIConfig(BaseModel):
    """TUI (Text User Interface) configuration."""

    model_config = ConfigDict(frozen=True)

    theme: str = "dark"
    refresh_interval: int = Field(default=30, ge=5)
    default_period_days: int = Field(default=30, ge=1, le=365)


class AppSettings(BaseModel):
    """Top-level application settings."""

    model_config = ConfigDict(frozen=True)

    aws: AWSConfig = Field(default_factory=AWSConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    @classmethod
    def from_env(cls) -> AppSettings:
        """Load settings from environment variables (python-dotenv pattern)."""
        import os

        load_dotenv()

        return cls(
            aws=AWSConfig(
                profile=os.getenv("AWS_PROFILE", "default"),
                region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                role_arn=os.getenv("AWS_ROLE_ARN") or None,
            ),
            cache=CacheConfig(
                enabled=os.getenv("REMORA_CACHE_ENABLED", "true").lower() == "true",
                ttl_seconds=int(os.getenv("REMORA_CACHE_TTL", "3600")),
            ),
            ui=UIConfig(
                theme=os.getenv("REMORA_UI_THEME", "dark"),
                default_period_days=int(os.getenv("REMORA_DEFAULT_DAYS", "30")),
            ),
        )
