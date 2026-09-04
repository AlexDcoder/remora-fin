"""Config Service — Centralized application configuration.

Design Patterns: Singleton + Builder
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from remora_fin.schemas import AppSettings, AWSConfig, CacheConfig, UIConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path.home() / ".remora" / "config.json"


class ConfigService:
    """Singleton service for managing application configuration."""

    _instance: ConfigService | None = None
    _initialized: bool = False
    _settings: AppSettings | None = None

    def __new__(cls) -> ConfigService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._config_path = _DEFAULT_CONFIG_PATH
        self._settings = self._load()
        self._initialized = True

    def _load(self) -> AppSettings:
        """Load settings from env first, then config file as override."""
        try:
            settings = AppSettings.from_env()
        except Exception:
            logger.debug("Failed to load from env, using defaults")
            settings = AppSettings()

        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text())
                if "aws" in data:
                    settings = AppSettings(
                        aws=AWSConfig(**data["aws"]),
                        cache=settings.cache,
                        ui=settings.ui,
                    )
                if "cache" in data:
                    settings = AppSettings(
                        aws=settings.aws,
                        cache=CacheConfig(**data["cache"]),
                        ui=settings.ui,
                    )
                if "ui" in data:
                    settings = AppSettings(
                        aws=settings.aws,
                        cache=settings.cache,
                        ui=UIConfig(**data["ui"]),
                    )
                logger.info("Config loaded from %s", self._config_path)
            except Exception as e:
                logger.warning("Failed to load config file: %s", e)

        return settings

    @property
    def settings(self) -> AppSettings:
        return self._settings or AppSettings()

    def get_aws_profile(self) -> str:
        return self.settings.aws.profile

    def get_default_region(self) -> str:
        return self.settings.aws.region

    def get_output_format(self) -> str:
        return "pdf"

    def save_config(self, settings: AppSettings) -> None:
        """Persist settings to config file."""
        self._settings = settings
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps(settings.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        logger.info("Config saved to %s", self._config_path)

    def is_configured(self) -> bool:
        """Return True if a configuration file exists on disk."""
        return self._config_path.exists()


class ConfigBuilder:
    """Builder for AppSettings."""

    def __init__(self) -> None:
        self._aws = AWSConfig()
        self._cache = CacheConfig()
        self._ui = UIConfig()

    def with_aws_profile(self, profile: str) -> ConfigBuilder:
        self._aws = AWSConfig(profile=profile, region=self._aws.region)
        return self

    def with_region(self, region: str) -> ConfigBuilder:
        self._aws = AWSConfig(profile=self._aws.profile, region=region)
        return self

    def with_role_arn(self, role_arn: str) -> ConfigBuilder:
        self._aws = AWSConfig(
            profile=self._aws.profile,
            region=self._aws.region,
            role_arn=role_arn,
        )
        return self

    def with_cache_enabled(self, enabled: bool) -> ConfigBuilder:
        self._cache = CacheConfig(
            enabled=enabled,
            ttl_seconds=self._cache.ttl_seconds,
            directory=self._cache.directory,
        )
        return self

    def with_cache_ttl(self, ttl: int) -> ConfigBuilder:
        self._cache = CacheConfig(
            enabled=self._cache.enabled,
            ttl_seconds=ttl,
            directory=self._cache.directory,
        )
        return self

    def with_theme(self, theme: str) -> ConfigBuilder:
        self._ui = UIConfig(
            theme=theme,
            refresh_interval=self._ui.refresh_interval,
            default_period_days=self._ui.default_period_days,
        )
        return self

    def build(self) -> AppSettings:
        return AppSettings(
            aws=self._aws,
            cache=self._cache,
            ui=self._ui,
        )
