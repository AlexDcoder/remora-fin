"""S3 Service — AWS S3 metadata and bucket management.

This service provides methods to fetch S3 bucket details and storage metrics,
useful for identifying high-cost storage patterns.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class S3Service(BaseService):
    """Service layer for AWS S3 management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize S3Service with optional AWS session and Cache service."""
        super().__init__("s3", session, cache)

    @retry_with_backoff(max_retries=3)
    def list_buckets(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all S3 buckets with basic metadata."""
        query = {"service": "s3", "action": "list_buckets"}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        s3 = self._session.s3()
        resp = s3.list_buckets()
        buckets = []

        for b in resp.get("Buckets", []):
            name = b["Name"]
            buckets.append(
                {
                    "name": name,
                    "creation_date": b["CreationDate"].isoformat(),
                }
            )

        logger.info("Found [bold cyan]%d[/] S3 buckets", len(buckets))

        if use_cache:
            self._cache.set_json(query, buckets)

        return buckets

    @async_retry_with_backoff(max_retries=3)
    async def list_buckets_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_buckets."""
        query = {"service": "s3", "action": "list_buckets"}

        async def _fetch():
            buckets = []
            async with self._session.async_client("s3") as s3:
                resp = await s3.list_buckets()
                for b in resp.get("Buckets", []):
                    buckets.append(
                        {
                            "name": b["Name"],
                            "creation_date": b["CreationDate"].isoformat(),
                        }
                    )
            logger.info("Found [bold cyan]%d[/] S3 buckets (async)", len(buckets))
            return buckets

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    @retry_with_backoff(max_retries=3)
    def get_bucket_region(self, bucket_name: str) -> str:
        """Get the region of a specific bucket."""
        s3 = self._session.s3()
        try:
            resp = s3.get_bucket_location(Bucket=bucket_name)
            return resp.get("LocationConstraint") or "us-east-1"
        except Exception:
            return "unknown"
