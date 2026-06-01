"""DynamoDB Service — AWS DynamoDB metadata and table management.

This service provides methods to fetch DynamoDB table details,
helping track costs for NoSQL workloads.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService

logger = logging.getLogger(__name__)


class DynamoDBService(BaseService):
    """Service layer for AWS DynamoDB management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize DynamoDBService with an optional AWS session."""
        super().__init__("dynamodb", session)

    @retry_with_backoff(max_retries=3)
    def list_tables(self, use_cache: bool = True) -> list[str]:
        """List all DynamoDB table names."""
        query = {"service": "dynamodb", "action": "list_tables", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[str]", cached)

        client = self._session.dynamodb()
        tables = []

        paginator = client.get_paginator("list_tables")
        for page in paginator.paginate():
            tables.extend(page.get("TableNames", []))

        logger.info("Found [bold cyan]%d[/] DynamoDB tables", len(tables))

        if use_cache:
            self._cache.set_json(query, tables)

        return tables

    @async_retry_with_backoff(max_retries=3)
    async def list_tables_async(self, use_cache: bool = True) -> list[str]:
        """Async version of list_tables."""
        query = {"service": "dynamodb", "action": "list_tables", "region": self._session.region}

        async def _fetch():
            tables = []
            async with self._session.async_client("dynamodb") as client:
                paginator = client.get_paginator("list_tables")
                async for page in paginator.paginate():
                    tables.extend(page.get("TableNames", []))
            logger.info("Found [bold cyan]%d[/] DynamoDB tables (async)", len(tables))
            return tables

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    @retry_with_backoff(max_retries=3)
    def get_table_details(self, table_name: str) -> dict[str, Any]:
        """Get detailed metadata for a specific table."""
        client = self._session.dynamodb()
        resp = client.describe_table(TableName=table_name)
        table = resp["Table"]

        return {
            "name": table["TableName"],
            "status": table["TableStatus"],
            "item_count": table.get("ItemCount"),
            "size_bytes": table.get("TableSizeBytes"),
            "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED"),
        }
