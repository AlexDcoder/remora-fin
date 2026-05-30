"""ElastiCache Service — AWS ElastiCache metadata and cluster management.

This service provides methods to fetch ElastiCache cluster details,
enabling correlation of caching infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class ElastiCacheService:
    """Service layer for AWS ElastiCache management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize ElastiCacheService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @retry_with_backoff(max_retries=3)
    def list_clusters(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all ElastiCache clusters in the current region with metadata."""
        query = {"service": "elasticache", "action": "list_clusters", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        ec = self._session.elasticache()
        clusters = []

        paginator = ec.get_paginator("describe_cache_clusters")
        for page in paginator.paginate():
            for cluster in page.get("CacheClusters", []):
                clusters.append(
                    {
                        "id": cluster["CacheClusterId"],
                        "node_type": cluster["CacheNodeType"],
                        "engine": cluster["Engine"],
                        "status": cluster["CacheClusterStatus"],
                        "num_nodes": cluster["NumCacheNodes"],
                        "preferred_az": cluster.get("PreferredAvailabilityZone"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] ElastiCache clusters", len(clusters))

        if use_cache:
            self._cache.set_json(query, clusters)

        return clusters

    def get_elasticache_stats(self) -> dict[str, Any]:
        """Get summary statistics for ElastiCache clusters."""
        clusters = self.list_clusters()
        engines: dict[str, int] = {}
        status: dict[str, int] = {}

        for cluster in clusters:
            engines[cluster["engine"]] = engines.get(cluster["engine"], 0) + 1
            status[cluster["status"]] = status.get(cluster["status"], 0) + 1

        return {
            "total_count": len(clusters),
            "engines": engines,
            "status": status,
        }
