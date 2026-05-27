"""RDS Service — AWS RDS metadata and instance management.

This service provides methods to fetch RDS instance details,
enabling correlation of database infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class RDSService:
    """Service layer for AWS RDS management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize RDSService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @retry_with_backoff(max_retries=3)
    def list_db_instances(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all RDS DB instances in the current region with metadata."""
        query = {"service": "rds", "action": "list_db_instances", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        rds = self._session.rds()
        instances = []

        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for instance in page.get("DBInstances", []):
                instances.append(
                    {
                        "id": instance["DBInstanceIdentifier"],
                        "class": instance["DBInstanceClass"],
                        "engine": instance["Engine"],
                        "status": instance["DBInstanceStatus"],
                        "multi_az": instance["MultiAZ"],
                        "storage_type": instance.get("StorageType"),
                        "allocated_storage": instance.get("AllocatedStorage"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] RDS instances", len(instances))

        if use_cache:
            self._cache.set_json(query, instances)

        return instances

    def get_rds_stats(self) -> dict[str, Any]:
        """Get summary statistics for RDS instances."""
        instances = self.list_db_instances()
        engines: dict[str, int] = {}
        status: dict[str, int] = {}

        for inst in instances:
            engines[inst["engine"]] = engines.get(inst["engine"], 0) + 1
            status[inst["status"]] = status.get(inst["status"], 0) + 1

        return {
            "total_count": len(instances),
            "engines": engines,
            "status": status,
        }
