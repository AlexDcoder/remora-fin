"""CloudFront Service — AWS CloudFront distribution management.

This service provides methods to fetch CloudFront distribution details,
essential for monitoring data transfer and edge costs.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService, ServiceType, aws_service_type

logger = logging.getLogger(__name__)


@aws_service_type(ServiceType.GLOBAL)
class CloudFrontService(BaseService):
    """Service layer for AWS CloudFront management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize CloudFrontService with an optional AWS session."""
        super().__init__("cloudfront", session)

    @retry_with_backoff(max_retries=3)
    def list_distributions(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all CloudFront distributions."""
        query = {"service": "cloudfront", "action": "list_distributions"}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        client = self._session.cloudfront()
        distributions = []

        paginator = client.get_paginator("list_distributions")
        for page in paginator.paginate():
            dist_list = page.get("DistributionList", {})
            for dist in dist_list.get("Items", []):
                distributions.append(
                    {
                        "id": dist["Id"],
                        "arn": dist["ARN"],
                        "status": dist["Status"],
                        "domain": dist["DomainName"],
                        "enabled": dist["Enabled"],
                    }
                )

        logger.info("Found [bold cyan]%d[/] CloudFront distributions", len(distributions))

        if use_cache:
            self._cache.set_json(query, distributions)

        return distributions

    @async_retry_with_backoff(max_retries=3)
    async def list_distributions_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_distributions."""
        query = {"service": "cloudfront", "action": "list_distributions"}

        async def _fetch():
            distributions = []
            async with self._session.async_client("cloudfront") as client:
                paginator = client.get_paginator("list_distributions")
                async for page in paginator.paginate():
                    dist_list = page.get("DistributionList", {})
                    for dist in dist_list.get("Items", []):
                        distributions.append(
                            {
                                "id": dist["Id"],
                                "arn": dist["ARN"],
                                "status": dist["Status"],
                                "domain": dist["DomainName"],
                                "enabled": dist["Enabled"],
                            }
                        )
            logger.info("Found [bold cyan]%d[/] CloudFront distributions (async)", len(distributions))
            return distributions

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
