"""Lambda Service — AWS Lambda metadata and function management.

This service provides methods to fetch Lambda function details,
which are crucial for monitoring serverless spending.
"""

from __future__ import annotations

import logging
from typing import Any

from remora_fin.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)


class LambdaService:
    """Service layer for AWS Lambda management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize LambdaService with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    @retry_with_backoff(max_retries=3)
    def list_functions(self) -> list[dict[str, Any]]:
        """List all Lambda functions in the current region."""
        client = self._session.lambda_client()
        functions = []

        paginator = client.get_paginator("list_functions")
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                functions.append(
                    {
                        "name": func["FunctionName"],
                        "runtime": func.get("Runtime"),
                        "memory": func.get("MemorySize"),
                        "last_modified": func.get("LastModified"),
                        "handler": func.get("Handler"),
                        "timeout": func.get("Timeout"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] Lambda functions", len(functions))
        return functions

    def get_runtime_distribution(self) -> dict[str, int]:
        """Get distribution of Lambda functions by runtime."""
        functions = self.list_functions()
        runtimes: dict[str, int] = {}
        for f in functions:
            rt = f["runtime"] or "unknown"
            runtimes[rt] = runtimes.get(rt, 0) + 1
        return runtimes
