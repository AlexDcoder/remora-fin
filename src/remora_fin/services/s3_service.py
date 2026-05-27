"""S3 Service — AWS S3 metadata and bucket management.

This service provides methods to fetch S3 bucket details and storage metrics,
useful for identifying high-cost storage patterns.
"""

from __future__ import annotations

import logging
from typing import Any

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class S3Service:
    """Service layer for AWS S3 management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize S3Service with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @retry_with_backoff(max_retries=3)
    def list_buckets(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all S3 buckets with basic metadata."""
        query = {"service": "s3", "action": "list_buckets"}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cached

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

    @retry_with_backoff(max_retries=3)
    def get_bucket_region(self, bucket_name: str) -> str:
        """Get the region of a specific bucket."""
        s3 = self._session.s3()
        try:
            resp = s3.get_bucket_location(Bucket=bucket_name)
            return resp.get("LocationConstraint") or "us-east-1"
        except Exception:
            return "unknown"
