"""KMS Service — AWS KMS metadata and key management.

This service provides methods to fetch KMS key details,
helping track costs for cryptographic operations.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService, ServiceType, aws_service_type

logger = logging.getLogger(__name__)


@aws_service_type(ServiceType.REGIONAL)
class KMSService(BaseService):
    """Service layer for AWS KMS management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize KMSService with an optional AWS session."""
        super().__init__("kms", session)

    @retry_with_backoff(max_retries=3)
    def list_keys(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all KMS keys in the current region."""
        query = {"service": "kms", "action": "list_keys", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        client = self._session.kms()
        keys = []

        paginator = client.get_paginator("list_keys")
        for page in paginator.paginate():
            for key in page.get("Keys", []):
                keys.append(
                    {
                        "id": key["KeyId"],
                        "arn": key["KeyArn"],
                    }
                )

        logger.info("Found [bold cyan]%d[/] KMS keys", len(keys))

        if use_cache:
            self._cache.set_json(query, keys)

        return keys

    @async_retry_with_backoff(max_retries=3)
    async def list_keys_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_keys."""
        query = {"service": "kms", "action": "list_keys", "region": self._session.region}

        async def _fetch():
            keys = []
            async with self._session.async_client("kms") as client:
                paginator = client.get_paginator("list_keys")
                async for page in paginator.paginate():
                    for key in page.get("Keys", []):
                        keys.append(
                            {
                                "id": key["KeyId"],
                                "arn": key["KeyArn"],
                            }
                        )
            logger.info("Found [bold cyan]%d[/] KMS keys (async)", len(keys))
            return keys

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
