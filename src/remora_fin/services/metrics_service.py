"""Metrics Service — AWS CloudWatch integration.

Handles fetching utilization metrics for AWS resources to support
Right-sizing and Unit Economics analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from remora_fin.schemas import MetricSummary, ResourceMetric
from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class MetricsService(BaseService):
    """Service for querying AWS CloudWatch metrics."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        super().__init__("metrics", session, cache)

    @retry_with_backoff(max_retries=3)
    def get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: list[dict[str, str]],
        start_time: datetime,
        end_time: datetime,
        period: int = 3600,
        statistics: list[str] | None = None,
    ) -> MetricSummary | None:
        if statistics is None:
            statistics = ["Average", "Minimum", "Maximum"]

        resource_id = dimensions[0]["Value"] if dimensions else "unknown"
        query: dict[str, Any] = {
            "service": "metrics",
            "method": "get_metric_statistics",
            "namespace": namespace,
            "metric": metric_name,
            "resource_id": resource_id,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        }

        cached = self._cache.get_json(query, max_age_hours=1)
        if isinstance(cached, dict):
            return MetricSummary(**cached)

        cw = self._session.cloudwatch()

        try:
            resp = cw.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics,
            )

            datapoints = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
            if not datapoints:
                return None

            points = [
                ResourceMetric(
                    timestamp=dp["Timestamp"],
                    value=dp.get("Average", dp.get("Maximum", 0.0)),
                    unit=dp.get("Unit", "Percent"),
                )
                for dp in datapoints
            ]

            values = [p.value for p in points]
            summary = MetricSummary(
                metric_name=metric_name,
                resource_id=resource_id,
                unit=points[0].unit,
                min=min(values),
                max=max(values),
                average=sum(values) / len(values),
                p95=sorted(values)[int(len(values) * 0.95)] if values else 0.0,
                data_points=points,
            )

            self._cache.set_json(query, summary.model_dump(mode="json"))
            return summary

        except Exception as e:
            logger.error(f"Failed to fetch metrics for {resource_id}: {e}")
            return None

    def get_ec2_cpu_utilization(self, instance_id: str, days: int = 7) -> MetricSummary | None:
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_metric_statistics(
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            start_time=start,
            end_time=end,
        )

    def get_rds_cpu_utilization(self, db_instance_id: str, days: int = 7) -> MetricSummary | None:
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_metric_statistics(
            namespace="AWS/RDS",
            metric_name="CPUUtilization",
            dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_id}],
            start_time=start,
            end_time=end,
        )

    def get_lambda_errors(self, function_name: str, days: int = 7) -> MetricSummary | None:
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_metric_statistics(
            namespace="AWS/Lambda",
            metric_name="Errors",
            dimensions=[{"Name": "FunctionName", "Value": function_name}],
            start_time=start,
            end_time=end,
            statistics=["Sum"],
        )

    def get_lambda_duration(self, function_name: str, days: int = 7) -> MetricSummary | None:
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_metric_statistics(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions=[{"Name": "FunctionName", "Value": function_name}],
            start_time=start,
            end_time=end,
            statistics=["Average"],
        )
