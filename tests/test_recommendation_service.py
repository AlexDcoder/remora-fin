from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from remora_fin.schemas import MetricSummary, ResourceMetric
from remora_fin.services.recommendation_service import RecommendationService


def _metric(name: str, average: float, p95: float, total: float | None = None) -> MetricSummary:
    points = [
        ResourceMetric(timestamp=datetime.now(UTC) - timedelta(hours=index), value=average, unit="Percent")
        for index in range(4)
    ]
    return MetricSummary(
        metric_name=name,
        resource_id="resource",
        unit="Percent",
        min=average,
        max=p95,
        average=average,
        total=average * len(points) if total is None else total,
        p95=p95,
        data_points=points,
    )


class MissingLifecycleError(Exception):
    response: ClassVar[dict[str, dict[str, str]]] = {"Error": {"Code": "NoSuchLifecycleConfiguration"}}


@pytest.mark.asyncio
async def test_recommendations_are_ranked_and_use_defensible_savings() -> None:
    inventory = MagicMock()

    async def resources(resource_type: str, use_cache: bool = True) -> list[dict[str, Any]]:
        del use_cache
        resources_by_type: dict[str, list[dict[str, Any]]] = {
            "ec2": [{"id": "i-123", "name": "worker", "type": "t3.small", "state": "running"}],
            "rds": [{"id": "db-1", "class": "db.t3.small", "engine": "postgres", "status": "available"}],
            "lambda": [{"name": "unused-function", "memory": 128}],
            "s3": [{"name": "archive", "creation_date": "2020-01-01T00:00:00+00:00"}],
        }
        return resources_by_type[resource_type]

    inventory.list_resources_async = AsyncMock(side_effect=resources)

    metrics = MagicMock()
    metrics.get_ec2_cpu_utilization.return_value = _metric("CPUUtilization", 3.0, 8.0)
    metrics.get_rds_cpu_utilization.return_value = _metric("CPUUtilization", 4.0, 9.0)
    metrics.get_rds_connections.return_value = _metric("DatabaseConnections", 0.2, 0.5)
    metrics.get_lambda_invocations.return_value = _metric("Invocations", 0.0, 0.0, total=0.0)

    price = SimpleNamespace(on_demand_price=SimpleNamespace(price_per_unit=Decimal("1.00")))
    pricing = MagicMock()
    pricing.get_ec2_price.return_value = price
    pricing.get_rds_price.return_value = price

    governance = MagicMock()
    governance.get_tag_compliance_async = AsyncMock(
        return_value={
            "details": [
                {
                    "arn": "arn:aws:ec2:us-east-1:123:instance/i-123",
                    "missing_tags": ["Owner"],
                }
            ]
        }
    )
    session = MagicMock()
    session.region = "us-east-1"
    session.s3.return_value.get_bucket_lifecycle_configuration.side_effect = MissingLifecycleError()

    result = await RecommendationService(
        session=session,
        inventory=inventory,
        pricing=pricing,
        metrics=metrics,
        governance=governance,
    ).get_recommendations(days=14)

    assert result.total_findings == 5
    assert result.total_estimated_monthly_savings == Decimal("730.0000")
    assert [item.service for item in result.recommendations[:2]] == ["EC2", "RDS"]
    assert result.recommendations[0].id == result.recommendations[0].id
    assert next(item for item in result.recommendations if item.service == "Lambda").estimated_monthly_savings is None
    assert next(item for item in result.recommendations if item.service == "S3").confidence.value == "medium"


@pytest.mark.asyncio
async def test_source_failure_is_reported_without_losing_other_findings() -> None:
    inventory = MagicMock()
    inventory.list_resources_async = AsyncMock(side_effect=RuntimeError("inventory denied"))
    governance = MagicMock()
    governance.get_tag_compliance_async = AsyncMock(
        return_value={"details": [{"arn": "arn:resource", "missing_tags": ["Owner"]}]}
    )
    session = MagicMock()
    session.region = "us-east-1"

    result = await RecommendationService(
        session=session,
        inventory=inventory,
        pricing=MagicMock(),
        metrics=MagicMock(),
        governance=governance,
    ).get_recommendations(services=["ec2", "governance"])

    assert result.total_findings == 1
    assert result.recommendations[0].category.value == "governance"
    assert result.partial_failures == ["EC2: inventory denied"]


@pytest.mark.asyncio
async def test_insufficient_metrics_do_not_create_rightsizing_finding() -> None:
    inventory = MagicMock()
    inventory.list_resources_async = AsyncMock(
        return_value=[{"id": "i-123", "name": "worker", "type": "t3.small", "state": "running"}]
    )
    metrics = MagicMock()
    metrics.get_ec2_cpu_utilization.return_value = MetricSummary(
        metric_name="CPUUtilization",
        resource_id="i-123",
        unit="Percent",
        average=1.0,
        p95=1.0,
        data_points=[ResourceMetric(timestamp=datetime.now(UTC), value=1.0)],
    )
    session = MagicMock()
    session.region = "us-east-1"

    result = await RecommendationService(
        session=session,
        inventory=inventory,
        pricing=MagicMock(),
        metrics=metrics,
        governance=MagicMock(),
    ).get_recommendations(services=["ec2"])

    assert result.total_findings == 0
    assert not result.partial_failures
