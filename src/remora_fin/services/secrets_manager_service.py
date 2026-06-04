"""Secrets Manager Service — AWS Secrets Manager metadata and secret management.

This service provides methods to fetch secret details,
helping track costs for secret storage and access.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService, ServiceType, aws_service_type

logger = logging.getLogger(__name__)


@aws_service_type(ServiceType.REGIONAL)
class SecretsManagerService(BaseService):
    """Service layer for AWS Secrets Manager management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize SecretsManagerService with an optional AWS session."""
        super().__init__("secretsmanager", session)

    @retry_with_backoff(max_retries=3)
    def list_secrets(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all secrets in the current region."""
        query = {"service": "secretsmanager", "action": "list_secrets", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        client = self._session.secretsmanager()
        secrets = []

        paginator = client.get_paginator("list_secrets")
        for page in paginator.paginate():
            for secret in page.get("SecretList", []):
                secrets.append(
                    {
                        "name": secret["Name"],
                        "arn": secret["ARN"],
                        "last_accessed": secret.get("LastAccessedDate", "").isoformat() if secret.get("LastAccessedDate") else None,
                    }
                )

        logger.info("Found [bold cyan]%d[/] Secrets", len(secrets))

        if use_cache:
            self._cache.set_json(query, secrets)

        return secrets

    @async_retry_with_backoff(max_retries=3)
    async def list_secrets_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_secrets."""
        query = {"service": "secretsmanager", "action": "list_secrets", "region": self._session.region}

        async def _fetch():
            secrets = []
            async with self._session.async_client("secretsmanager") as client:
                paginator = client.get_paginator("list_secrets")
                async for page in paginator.paginate():
                    for secret in page.get("SecretList", []):
                        secrets.append(
                            {
                                "name": secret["Name"],
                                "arn": secret["ARN"],
                                "last_accessed": secret.get("LastAccessedDate", "").isoformat() if secret.get("LastAccessedDate") else None,
                            }
                        )
            logger.info("Found [bold cyan]%d[/] Secrets (async)", len(secrets))
            return secrets

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
