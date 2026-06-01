"""SageMaker Service — AWS SageMaker metadata and resource management.

This service provides methods to fetch SageMaker notebook and training job details,
enabling correlation of ML infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class SageMakerService(BaseService):
    """Service layer for AWS SageMaker management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize SageMakerService with optional AWS session and Cache service."""
        super().__init__("sagemaker", session, cache)

    @retry_with_backoff(max_retries=3)
    def list_notebook_instances(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all SageMaker notebook instances in the current region."""
        query = {"service": "sagemaker", "action": "list_notebook_instances", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        sm = self._session.sagemaker()
        instances = []

        paginator = sm.get_paginator("list_notebook_instances")
        for page in paginator.paginate():
            for inst in page.get("NotebookInstances", []):
                instances.append(
                    {
                        "name": inst["NotebookInstanceName"],
                        "status": inst["NotebookInstanceStatus"],
                        "type": inst["InstanceType"],
                        "arn": inst["NotebookInstanceArn"],
                    }
                )

        logger.info("Found [bold cyan]%d[/] SageMaker notebook instances", len(instances))

        if use_cache:
            self._cache.set_json(query, instances)

        return instances

    @async_retry_with_backoff(max_retries=3)
    async def list_notebook_instances_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_notebook_instances."""
        query = {"service": "sagemaker", "action": "list_notebook_instances", "region": self._session.region}

        async def _fetch():
            instances = []
            async with self._session.async_client("sagemaker") as sm:
                paginator = sm.get_paginator("list_notebook_instances")
                async for page in paginator.paginate():
                    for inst in page.get("NotebookInstances", []):
                        instances.append(
                            {
                                "name": inst["NotebookInstanceName"],
                                "status": inst["NotebookInstanceStatus"],
                                "type": inst["InstanceType"],
                                "arn": inst["NotebookInstanceArn"],
                            }
                        )
            logger.info("Found [bold cyan]%d[/] SageMaker notebook instances (async)", len(instances))
            return instances

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    @retry_with_backoff(max_retries=3)
    def list_training_jobs(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List SageMaker training jobs in the current region."""
        query = {"service": "sagemaker", "action": "list_training_jobs", "region": self._session.region}

        if use_cache:
            cached = self._cache.get_json(query, max_age_hours=1)
            if cached is not None:
                return cast("list[dict[str, Any]]", cached)

        sm = self._session.sagemaker()
        jobs = []

        paginator = sm.get_paginator("list_training_jobs")
        for page in paginator.paginate():
            for job in page.get("TrainingJobSummaries", []):
                jobs.append(
                    {
                        "name": job["TrainingJobName"],
                        "status": job["TrainingJobStatus"],
                        "creation_time": job["CreationTime"].isoformat(),
                    }
                )

        if use_cache:
            self._cache.set_json(query, jobs)

        return jobs

    @async_retry_with_backoff(max_retries=3)
    async def list_training_jobs_async(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Async version of list_training_jobs."""
        query = {"service": "sagemaker", "action": "list_training_jobs", "region": self._session.region}

        async def _fetch():
            jobs = []
            async with self._session.async_client("sagemaker") as sm:
                paginator = sm.get_paginator("list_training_jobs")
                async for page in paginator.paginate():
                    for job in page.get("TrainingJobSummaries", []):
                        jobs.append(
                            {
                                "name": job["TrainingJobName"],
                                "status": job["TrainingJobStatus"],
                                "creation_time": job["CreationTime"].isoformat(),
                            }
                        )
            return jobs

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
