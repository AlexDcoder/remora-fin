"""Governance Service — Tag hygiene and compliance.

This service identifies resources missing mandatory tags and provides compliance
scoring and details.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService

logger = logging.getLogger(__name__)


class GovernanceService(BaseService):
    """Handles AWS tag compliance and resource hygiene management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        super().__init__("governance", session)

    @retry_with_backoff(max_retries=3)
    def get_tag_compliance(self, required_tags: list[str], use_cache: bool = True) -> dict[str, Any]:
        """Scan resources and evaluate compliance against a list of required tags."""
        query = {"service": "governance", "action": "tag_compliance", "tags": required_tags}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=2)
            if cached is not None:
                return cast("dict[str, Any]", cached)

        tagging = self._session.tagging()
        resources = []

        paginator = tagging.get_paginator("get_resources")
        for page in paginator.paginate():
            for mapping in page.get("ResourceTagMappingList", []):
                arn = mapping["ResourceARN"]
                tags = {t["Key"]: t["Value"] for t in mapping.get("Tags", [])}

                missing = [rt for rt in required_tags if rt not in tags]
                resources.append({"arn": arn, "tags": tags, "missing_tags": missing, "is_compliant": len(missing) == 0})

        total = len(resources)
        compliant = sum(1 for r in resources if r["is_compliant"])
        score = (compliant / total * 100) if total > 0 else 100

        result = {
            "score": score,
            "total_resources": total,
            "compliant_resources": compliant,
            "non_compliant_resources": total - compliant,
            "details": resources,
        }

        if use_cache:
            self._cache.set_json(query, result)

        return result

    @async_retry_with_backoff(max_retries=3)
    async def get_tag_compliance_async(self, required_tags: list[str], use_cache: bool = True) -> dict[str, Any]:
        """Async version of get_tag_compliance."""
        query = {"service": "governance", "action": "tag_compliance", "tags": required_tags}

        async def _fetch():
            resources = []
            # async_client() is a coroutine that returns an async client; await it first
            tagging = await self._session.async_client("resourcegroupstaggingapi")
            paginator = tagging.get_paginator("get_resources")
            async for page in paginator.paginate():
                for mapping in page.get("ResourceTagMappingList", []):
                    arn = mapping["ResourceARN"]
                    tags = {t["Key"]: t["Value"] for t in mapping.get("Tags", [])}
                    missing = [rt for rt in required_tags if rt not in tags]
                    resources.append(
                        {"arn": arn, "tags": tags, "missing_tags": missing, "is_compliant": len(missing) == 0}
                    )

            total = len(resources)
            compliant = sum(1 for r in resources if r["is_compliant"])
            score = (compliant / total * 100) if total > 0 else 100

            return {
                "score": score,
                "total_resources": total,
                "compliant_resources": compliant,
                "non_compliant_resources": total - compliant,
                "details": resources,
            }

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache, max_age_hours=2)