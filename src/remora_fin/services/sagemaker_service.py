"""SageMaker Service — AWS SageMaker metadata and resource management.

This service provides methods to fetch SageMaker notebook and training job details,
enabling correlation of ML infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class SageMakerService:
    """Service layer for AWS SageMaker management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize SageMakerService with optional AWS session and Cache service."""
        self._session = session or AWSSession.get_instance()
        self._cache = cache or CacheService()

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
