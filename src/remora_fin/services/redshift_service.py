"""Redshift Service — AWS Redshift metadata and cluster management.

This service provides methods to fetch Redshift cluster details,
enabling correlation of data warehousing infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class RedshiftService(BaseService):
    """Service layer for AWS Redshift management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize RedshiftService with optional AWS session and Cache service."""
        super().__init__("redshift", session, cache)

    @retry_with_backoff(max_retries=3)
    def list_clusters(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all Redshift clusters in the current region with metadata."""
        query = {"service": "redshift", "action": "list_clusters", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        rs = self._session.redshift()
        clusters = []

        paginator = rs.get_paginator("describe_clusters")
        for page in paginator.paginate():
            for cluster in page.get("Clusters", []):
                clusters.append(
                    {
                        "id": cluster["ClusterIdentifier"],
                        "node_type": cluster["NodeType"],
                        "status": cluster["ClusterStatus"],
                        "num_nodes": cluster["NumberOfNodes"],
                        "db_name": cluster.get("DBName"),
                        "version": cluster.get("ClusterVersion"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] Redshift clusters", len(clusters))

        if use_cache:
            self._cache.set_json(query, clusters)

        return clusters

    @async_retry_with_backoff(max_retries=3)
    async def list_clusters_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_clusters."""
        query = {"service": "redshift", "action": "list_clusters", "region": self._session.region}

        async def _fetch():
            clusters = []
            async with self._session.async_client("redshift") as rs:
                paginator = rs.get_paginator("describe_clusters")
                async for page in paginator.paginate():
                    for cluster in page.get("Clusters", []):
                        clusters.append(
                            {
                                "id": cluster["ClusterIdentifier"],
                                "node_type": cluster["NodeType"],
                                "status": cluster["ClusterStatus"],
                                "num_nodes": cluster["NumberOfNodes"],
                                "db_name": cluster.get("DBName"),
                                "version": cluster.get("ClusterVersion"),
                            }
                        )
            logger.info("Found [bold cyan]%d[/] Redshift clusters (async)", len(clusters))
            return clusters

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    def get_redshift_stats(self) -> dict[str, Any]:
        """Get summary statistics for Redshift clusters."""
        clusters = self.list_clusters()
        status: dict[str, int] = {}
        node_types: dict[str, int] = {}

        for cluster in clusters:
            status[cluster["status"]] = status.get(cluster["status"], 0) + 1
            node_types[cluster["node_type"]] = node_types.get(cluster["node_type"], 0) + 1

        return {
            "total_count": len(clusters),
            "status": status,
            "node_types": node_types,
        }
