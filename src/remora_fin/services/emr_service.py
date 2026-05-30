"""EMR Service — AWS EMR metadata and cluster management.

This service provides methods to fetch EMR cluster details,
enabling correlation of big data infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class EMRService:
    """Service layer for AWS EMR management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize EMRService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @retry_with_backoff(max_retries=3)
    def list_clusters(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all EMR clusters in the current region with metadata."""
        query = {"service": "emr", "action": "list_clusters", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        emr = self._session.emr()
        clusters = []

        paginator = emr.get_paginator("list_clusters")
        for page in paginator.paginate():
            for cluster in page.get("Clusters", []):
                clusters.append(
                    {
                        "id": cluster["Id"],
                        "name": cluster["Name"],
                        "status": cluster["Status"]["State"],
                        "normalized_instance_hours": cluster.get("NormalizedInstanceHours", 0),
                    }
                )

        logger.info("Found [bold cyan]%d[/] EMR clusters", len(clusters))

        if use_cache:
            self._cache.set_json(query, clusters)

        return clusters
