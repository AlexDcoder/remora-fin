"""Base Service — Foundation for all AWS-integrated services.

Provides shared session management, caching logic, and async-first patterns.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseService:
    """Base class for services to reduce boilerplate and unify async patterns."""

    def __init__(
        self,
        service_name: str,
        session: AWSSession | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self.service_name = service_name
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @property
    def session(self) -> AWSSession:
        return self._session

    @property
    def cache(self) -> CacheService:
        return self._cache

    async def get_cached_or_fetch_async(
        self,
        query: dict[str, Any],
        fetch_func: Callable[[], Any],
        use_cache: bool = True,
        max_age_hours: int = 1,
    ) -> Any:
        """Helper to handle the common pattern: check JSON cache, then fetch async."""
        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=max_age_hours)
            if cached is not None:
                return cached

        try:
            data = await fetch_func()
        except Exception as e:
            logger.warning(f"Async fetch failed for {self.service_name}: {e}")
            return None

        if use_cache:
            cache_data = data
            if hasattr(data, "model_dump"):
                cache_data = data.model_dump(mode="json")
            self._cache.set_json(query, cache_data)

        return data