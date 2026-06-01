"""Dashboard Service — High-performance parallel data orchestration.

Provides a unified view for the UI by fetching costs, anomalies, and
infrastructure metadata concurrently.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from remora_fin.services.anomaly_service import AnomalyService
from remora_fin.services.aws_service import AWSSession
from remora_fin.services.base_service import BaseService
from remora_fin.services.cloudfront_service import CloudFrontService
from remora_fin.services.cost_service import CostService
from remora_fin.services.dynamodb_service import DynamoDBService
from remora_fin.services.ec2_service import EC2Service
from remora_fin.services.elasticache_service import ElastiCacheService
from remora_fin.services.emr_service import EMRService
from remora_fin.services.governance_service import GovernanceService
from remora_fin.services.lambda_service import LambdaService
from remora_fin.services.rds_service import RDSService
from remora_fin.services.redshift_service import RedshiftService
from remora_fin.services.s3_service import S3Service
from remora_fin.services.sagemaker_service import SageMakerService
from remora_fin.services.sns_service import SNSService
from remora_fin.services.sqs_service import SQSService

logger = logging.getLogger(__name__)


class DashboardService(BaseService):
    """Orchestrates multiple services to provide high-agility dashboard data."""

    def __init__(
        self,
        session: AWSSession | None = None,
        cost_service: CostService | None = None,
        anomaly_service: AnomalyService | None = None,
        ec2_service: EC2Service | None = None,
        rds_service: RDSService | None = None,
        lambda_service: LambdaService | None = None,
        governance_service: GovernanceService | None = None,
        s3_service: S3Service | None = None,
        cloudfront_service: CloudFrontService | None = None,
        dynamodb_service: DynamoDBService | None = None,
        elasticache_service: ElastiCacheService | None = None,
        emr_service: EMRService | None = None,
        redshift_service: RedshiftService | None = None,
        sagemaker_service: SageMakerService | None = None,
        sns_service: SNSService | None = None,
        sqs_service: SQSService | None = None,
    ) -> None:
        super().__init__("dashboard", session)
        self._cost = cost_service or CostService(self._session)
        self._anomaly = anomaly_service or AnomalyService(self._session)
        self._ec2 = ec2_service or EC2Service(self._session)
        self._rds = rds_service or RDSService(self._session)
        self._lambda = lambda_service or LambdaService(self._session)
        self._governance = governance_service or GovernanceService(self._session)
        self._s3 = s3_service or S3Service(self._session)
        self._cloudfront = cloudfront_service or CloudFrontService(self._session)
        self._dynamodb = dynamodb_service or DynamoDBService(self._session)
        self._elasticache = elasticache_service or ElastiCacheService(self._session)
        self._emr = emr_service or EMRService(self._session)
        self._redshift = redshift_service or RedshiftService(self._session)
        self._sagemaker = sagemaker_service or SageMakerService(self._session)
        self._sns = sns_service or SNSService(self._session)
        self._sqs = sqs_service or SQSService(self._session)

    async def get_summary_parallel(
        self,
        days: int = 30,
        use_cache: bool = True,
        required_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch all dashboard components concurrently."""
        end = date.today()
        start = end - timedelta(days=days)
        tags = required_tags or ["Environment", "Project", "Owner"]

        logger.info("Fetching comprehensive dashboard summary in parallel (period: [cyan]%d days[/])", days)

        # Run all requests in parallel
        tasks = [
            self._cost.get_total_cost_async(start, end),
            self._cost.get_daily_trend_async(start, end),
            self._anomaly.get_anomaly_summary_async(start, end, use_cache=use_cache),
            self._ec2.list_instances_async(use_cache=use_cache),
            self._rds.list_db_instances_async(use_cache=use_cache),
            self._lambda.list_functions_async(use_cache=use_cache),
            self._governance.get_tag_compliance_async(tags, use_cache=use_cache),
            self._s3.list_buckets_async(use_cache=use_cache),
            self._cloudfront.list_distributions_async(use_cache=use_cache),
            self._dynamodb.list_tables_async(use_cache=use_cache),
            self._elasticache.list_clusters_async(use_cache=use_cache),
            self._emr.list_clusters_async(use_cache=use_cache),
            self._redshift.list_clusters_async(use_cache=use_cache),
            self._sagemaker.list_notebook_instances_async(use_cache=use_cache),
            self._sns.list_topics_async(use_cache=use_cache),
            self._sqs.list_queues_async(use_cache=use_cache),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions gracefully
        def _get_result(idx: int, default: Any = None) -> Any:
            try:
                val = results[idx]
                if isinstance(val, Exception):
                    logger.error("Parallel fetch error in task %d: %s", idx, val)
                    return default
                return val if val is not None else default
            except (IndexError, AttributeError):
                return default

        anomaly_data = _get_result(2)
        # Ensure it's not just a string if it failed earlier but didn't raise
        if isinstance(anomaly_data, str):
            anomaly_data = None

        infra = {
            "ec2": _get_result(3, []),
            "rds": _get_result(4, []),
            "lambda": _get_result(5, []),
            "s3": _get_result(7, []),
            "cloudfront": _get_result(8, []),
            "dynamodb": _get_result(9, []),
            "elasticache": _get_result(10, []),
            "emr": _get_result(11, []),
            "redshift": _get_result(12, []),
            "sagemaker": _get_result(13, []),
            "sns": _get_result(14, []),
            "sqs": _get_result(15, []),
        }

        summary = {
            "cost_summary": _get_result(0),
            "cost_trend": _get_result(1),
            "anomalies": anomaly_data,
            "infrastructure": {
                "counts": {k: len(v) if isinstance(v, (list, dict, str)) else 0 for k, v in infra.items()},
                "details": infra,
            },
            "governance": _get_result(6),
            "last_updated": date.today().isoformat(),
        }

        return summary
