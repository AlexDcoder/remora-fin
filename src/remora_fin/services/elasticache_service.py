"""ElastiCache Service — AWS ElastiCache metadata and cluster management.

This service provides methods to fetch ElastiCache cluster details,
enabling correlation of caching infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class ElastiCacheService(BaseService):
    """Service layer for AWS ElastiCache management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize ElastiCacheService with optional AWS session and Cache service."""
        super().__init__("elasticache", session, cache)

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

    @async_retry_with_backoff(max_retries=3)
    async def list_clusters_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_clusters."""
        query = {"service": "elasticache", "action": "list_clusters", "region": self._session.region}

        async def _fetch():
            clusters = []
            async with self._session.async_client("elasticache") as ec:
                paginator = ec.get_paginator("describe_cache_clusters")
                async for page in paginator.paginate():
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
            logger.info("Found [bold cyan]%d[/] ElastiCache clusters (async)", len(clusters))
            return clusters

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

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
