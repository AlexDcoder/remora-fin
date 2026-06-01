"""SNS Service — AWS SNS metadata and topic management.

This service provides methods to fetch SNS topic details,
enabling correlation of messaging infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class SNSService(BaseService):
    """Service layer for AWS SNS management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize SNSService with optional AWS session and Cache service."""
        super().__init__("sns", session, cache)

    @retry_with_backoff(max_retries=3)
    def list_topics(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all SNS topics in the current region with metadata."""
        query = {"service": "sns", "action": "list_topics", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        sns = self._session.sns()
        topics = []

        paginator = sns.get_paginator("list_topics")
        for page in paginator.paginate():
            for topic in page.get("Topics", []):
                arn = topic["TopicArn"]
                # Extract attributes for more detail (optional, but good for cost)
                attrs = sns.get_topic_attributes(TopicArn=arn).get("Attributes", {})

                topics.append(
                    {
                        "arn": arn,
                        "name": arn.split(":")[-1],
                        "subscriptions_confirmed": attrs.get("SubscriptionsConfirmed"),
                        "subscriptions_pending": attrs.get("SubscriptionsPending"),
                    }
                )

        logger.info("Found [bold cyan]%d[/] SNS topics", len(topics))

        if use_cache:
            self._cache.set_json(query, topics)

        return topics

    @async_retry_with_backoff(max_retries=3)
    async def list_topics_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_topics."""
        query = {"service": "sns", "action": "list_topics", "region": self._session.region}

        async def _fetch():
            topics = []
            async with self._session.async_client("sns") as sns:
                paginator = sns.get_paginator("list_topics")
                async for page in paginator.paginate():
                    for topic in page.get("Topics", []):
                        arn = topic["TopicArn"]
                        attrs_resp = await sns.get_topic_attributes(TopicArn=arn)
                        attrs = attrs_resp.get("Attributes", {})

                        topics.append(
                            {
                                "arn": arn,
                                "name": arn.split(":")[-1],
                                "subscriptions_confirmed": attrs.get("SubscriptionsConfirmed"),
                                "subscriptions_pending": attrs.get("SubscriptionsPending"),
                            }
                        )
            logger.info("Found [bold cyan]%d[/] SNS topics (async)", len(topics))
            return topics

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
