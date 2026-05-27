"""DynamoDB Service — AWS DynamoDB metadata and table management.

This service provides methods to fetch DynamoDB table details,
helping track costs for NoSQL workloads.
"""

from __future__ import annotations

import logging
from typing import Any

from remora_fin.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)


class DynamoDBService:
    """Service layer for AWS DynamoDB management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize DynamoDBService with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    @retry_with_backoff(max_retries=3)
    def list_tables(self) -> list[str]:
        """List all DynamoDB table names."""
        client = self._session.dynamodb()
        tables = []

        paginator = client.get_paginator("list_tables")
        for page in paginator.paginate():
            tables.extend(page.get("TableNames", []))

        logger.info("Found [bold cyan]%d[/] DynamoDB tables", len(tables))
        return tables

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
