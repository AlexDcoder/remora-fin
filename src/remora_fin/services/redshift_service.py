"""Redshift Service — AWS Redshift metadata and cluster management.

This service provides methods to fetch Redshift cluster details,
enabling correlation of data warehousing infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class RedshiftService:
    """Service layer for AWS Redshift management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize RedshiftService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

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
