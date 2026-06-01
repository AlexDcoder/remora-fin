"""Lambda Service — AWS Lambda metadata and function management.

This service provides methods to fetch Lambda function details,
which are crucial for monitoring serverless spending.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService

logger = logging.getLogger(__name__)


class LambdaService(BaseService):
    """Service layer for AWS Lambda management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize LambdaService with an optional AWS session."""
        super().__init__("lambda", session)

    @retry_with_backoff(max_retries=3)
    def list_functions(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all Lambda functions in the current region."""
        query = {"service": "lambda", "action": "list_functions", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

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

        if use_cache:
            self._cache.set_json(query, functions)

        return functions

    @async_retry_with_backoff(max_retries=3)
    async def list_functions_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_functions."""
        query = {"service": "lambda", "action": "list_functions", "region": self._session.region}

        async def _fetch():
            functions = []
            async with self._session.async_client("lambda") as client:
                paginator = client.get_paginator("list_functions")
                async for page in paginator.paginate():
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
            logger.info("Found [bold cyan]%d[/] Lambda functions (async)", len(functions))
            return functions

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    def get_runtime_distribution(self) -> dict[str, int]:
        """Get distribution of Lambda functions by runtime."""
        functions = self.list_functions()
        runtimes: dict[str, int] = {}
        for f in functions:
            rt = f["runtime"] or "unknown"
            runtimes[rt] = runtimes.get(rt, 0) + 1
        return runtimes
