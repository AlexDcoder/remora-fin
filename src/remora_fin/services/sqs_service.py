"""SQS Service — AWS SQS metadata and queue management.

This service provides methods to fetch SQS queue details,
enabling correlation of messaging infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class SQSService:
    """Service layer for AWS SQS management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize SQSService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

    @retry_with_backoff(max_retries=3)
    def list_queues(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all SQS queues in the current region with metadata."""
        query = {"service": "sqs", "action": "list_queues", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        sqs = self._session.sqs()
        queues = []

        paginator = sqs.get_paginator("list_queues")
        for page in paginator.paginate():
            for url in page.get("QueueUrls", []):
                # Extract attributes
                attrs = sqs.get_queue_attributes(
                    QueueUrl=url, AttributeNames=["QueueArn", "ApproximateNumberOfMessages", "CreatedTimestamp"]
                ).get("Attributes", {})

                queues.append(
                    {
                        "url": url,
                        "arn": attrs.get("QueueArn"),
                        "name": url.split("/")[-1],
                        "message_count": int(attrs.get("ApproximateNumberOfMessages", 0)),
                        "created_at": attrs.get("CreatedTimestamp"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] SQS queues", len(queues))

        if use_cache:
            self._cache.set_json(query, queues)

        return queues
