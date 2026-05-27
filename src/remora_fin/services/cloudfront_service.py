"""CloudFront Service — AWS CloudFront distribution management.

This service provides methods to fetch CloudFront distribution details,
essential for monitoring data transfer and edge costs.
"""

from __future__ import annotations

import logging
from typing import Any

from remora_fin.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)


class CloudFrontService:
    """Service layer for AWS CloudFront management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize CloudFrontService with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    @retry_with_backoff(max_retries=3)
    def list_distributions(self) -> list[dict[str, Any]]:
        """List all CloudFront distributions."""
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
        return distributions
