"""Read-only recommendation engine built from existing FinOps signals."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from remora_fin.schemas import (
    Recommendation,
    RecommendationCategory,
    RecommendationConfidence,
    RecommendationSeverity,
    RecommendationSummary,
)
from remora_fin.services.aws_service import AWSSession
from remora_fin.services.governance_service import GovernanceService
from remora_fin.services.inventory_service import InventoryService
from remora_fin.services.metrics_service import MetricsService
from remora_fin.services.pricing_service import PricingService

logger = logging.getLogger(__name__)

MINIMUM_DATAPOINTS = 3
LOW_CPU_AVERAGE = 10.0
LOW_CPU_P95 = 20.0
LOW_RDS_CONNECTIONS = 1.0
S3_MINIMUM_AGE_DAYS = 90
MONTHLY_HOURS = Decimal("730")
CONSERVATIVE_RIGHTSIZE_FACTOR = Decimal("0.50")


class RecommendationService:
    """Create ranked recommendations without changing AWS resources."""

    def __init__(
        self,
        session: AWSSession | None = None,
        inventory: InventoryService | None = None,
        pricing: PricingService | None = None,
        metrics: MetricsService | None = None,
        governance: GovernanceService | None = None,
    ) -> None:
        self._session = session or AWSSession.get_instance()
        self._inventory = inventory or InventoryService(self._session)
        self._pricing = pricing or PricingService(self._session)
        self._metrics = metrics or MetricsService(self._session)
        self._governance = governance or GovernanceService(self._session)

    @staticmethod
    def _id(category: str, service: str, resource_id: str, rule: str) -> str:
        value = f"{category}:{service}:{resource_id}:{rule}".lower()
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    @staticmethod
    def _severity(savings: Decimal | None) -> RecommendationSeverity:
        if savings is None:
            return RecommendationSeverity.MEDIUM
        if savings >= Decimal("100"):
            return RecommendationSeverity.HIGH
        if savings >= Decimal("25"):
            return RecommendationSeverity.MEDIUM
        return RecommendationSeverity.LOW

    async def get_recommendations(
        self,
        days: int = 14,
        services: list[str] | None = None,
        required_tags: list[str] | None = None,
    ) -> RecommendationSummary:
        """Evaluate recommendation sources independently and return ranked findings."""
        selected = {service.lower() for service in services} if services else None
        checks: list[tuple[str, Any]] = []
        if selected is None or "ec2" in selected:
            checks.append(("EC2", self._ec2(days)))
        if selected is None or "rds" in selected:
            checks.append(("RDS", self._rds(days)))
        if selected is None or "lambda" in selected:
            checks.append(("Lambda", self._lambda(days)))
        if selected is None or "s3" in selected:
            checks.append(("S3", self._s3()))
        if selected is None or "governance" in selected or "tags" in selected:
            checks.append(("Governance", self._tags(required_tags or ["Environment", "Project", "Owner"])))

        results = await asyncio.gather(*(check for _, check in checks), return_exceptions=True)
        recommendations: list[Recommendation] = []
        failures: list[str] = []
        for (name, _), result in zip(checks, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("Recommendation source %s failed: %s", name, result)
                failures.append(f"{name}: {result}")
            else:
                recommendations.extend(result)

        severity_order = {
            RecommendationSeverity.HIGH: 0,
            RecommendationSeverity.MEDIUM: 1,
            RecommendationSeverity.LOW: 2,
        }
        recommendations.sort(
            key=lambda item: (
                -(item.estimated_monthly_savings or Decimal("0")),
                severity_order[item.severity],
                item.service,
                item.resource_id,
            )
        )
        total = sum(
            (item.estimated_monthly_savings or Decimal("0") for item in recommendations),
            Decimal("0"),
        )
        return RecommendationSummary(
            analysis_days=days,
            recommendations=recommendations,
            total_estimated_monthly_savings=total,
            partial_failures=failures,
        )

    async def _ec2(self, days: int) -> list[Recommendation]:
        findings: list[Recommendation] = []
        for instance in await self._inventory.list_resources_async("ec2"):
            if instance.get("state") != "running":
                continue
            resource_id = str(instance["id"])
            metric = self._metrics.get_ec2_cpu_utilization(resource_id, days=days)
            if (
                metric is None
                or len(metric.data_points) < MINIMUM_DATAPOINTS
                or metric.average >= LOW_CPU_AVERAGE
                or metric.p95 >= LOW_CPU_P95
            ):
                continue
            price = self._pricing.get_ec2_price(str(instance["type"]), self._session.region)
            rate = price.on_demand_price.price_per_unit if price and price.on_demand_price else None
            savings = rate * MONTHLY_HOURS * CONSERVATIVE_RIGHTSIZE_FACTOR if rate is not None else None
            findings.append(
                Recommendation(
                    id=self._id("cost", "ec2", resource_id, "low-cpu"),
                    category=RecommendationCategory.COST,
                    service="EC2",
                    resource_id=resource_id,
                    resource_name=instance.get("name") or None,
                    title="Review underutilized EC2 instance",
                    severity=self._severity(savings),
                    confidence=RecommendationConfidence.HIGH,
                    evidence=[
                        f"Average CPU was {metric.average:.1f}% over {days} days",
                        f"p95 CPU was {metric.p95:.1f}% across {len(metric.data_points)} datapoints",
                    ],
                    suggested_action="Review workload requirements, then consider stopping or rightsizing the instance.",
                    estimated_monthly_savings=savings,
                )
            )
        return findings

    async def _rds(self, days: int) -> list[Recommendation]:
        findings: list[Recommendation] = []
        for database in await self._inventory.list_resources_async("rds"):
            if database.get("status") != "available":
                continue
            resource_id = str(database["id"])
            cpu = self._metrics.get_rds_cpu_utilization(resource_id, days=days)
            connections = self._metrics.get_rds_connections(resource_id, days=days)
            if (
                cpu is None
                or connections is None
                or len(cpu.data_points) < MINIMUM_DATAPOINTS
                or len(connections.data_points) < MINIMUM_DATAPOINTS
                or cpu.average >= LOW_CPU_AVERAGE
                or cpu.p95 >= LOW_CPU_P95
                or connections.average >= LOW_RDS_CONNECTIONS
            ):
                continue
            price = self._pricing.get_rds_price(str(database["class"]), self._session.region, str(database["engine"]))
            rate = price.on_demand_price.price_per_unit if price and price.on_demand_price else None
            savings = rate * MONTHLY_HOURS * CONSERVATIVE_RIGHTSIZE_FACTOR if rate is not None else None
            findings.append(
                Recommendation(
                    id=self._id("cost", "rds", resource_id, "low-utilization"),
                    category=RecommendationCategory.COST,
                    service="RDS",
                    resource_id=resource_id,
                    title="Review underutilized RDS instance",
                    severity=self._severity(savings),
                    confidence=RecommendationConfidence.HIGH,
                    evidence=[
                        f"Average CPU was {cpu.average:.1f}% and p95 was {cpu.p95:.1f}%",
                        f"Average database connections were {connections.average:.1f} over {days} days",
                    ],
                    suggested_action="Validate peak and availability needs, then consider a smaller instance class or retirement.",
                    estimated_monthly_savings=savings,
                )
            )
        return findings

    async def _lambda(self, days: int) -> list[Recommendation]:
        findings: list[Recommendation] = []
        for function in await self._inventory.list_resources_async("lambda"):
            name = str(function["name"])
            invocations = self._metrics.get_lambda_invocations(name, days=days)
            if invocations is None or not invocations.data_points or invocations.total > 0:
                continue
            findings.append(
                Recommendation(
                    id=self._id("hygiene", "lambda", name, "zero-invocations"),
                    category=RecommendationCategory.HYGIENE,
                    service="Lambda",
                    resource_id=name,
                    resource_name=name,
                    title="Review inactive Lambda function",
                    severity=RecommendationSeverity.LOW,
                    confidence=RecommendationConfidence.HIGH,
                    evidence=[f"CloudWatch recorded zero invocations over {days} days"],
                    suggested_action="Confirm the function is not seasonal or event-driven before archiving or deleting it.",
                )
            )
        return findings

    async def _s3(self) -> list[Recommendation]:
        findings: list[Recommendation] = []
        s3 = self._session.s3()
        now = datetime.now(UTC)
        for bucket in await self._inventory.list_resources_async("s3"):
            created = datetime.fromisoformat(str(bucket["creation_date"]))
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_days = (now - created).days
            if age_days < S3_MINIMUM_AGE_DAYS:
                continue
            try:
                response = s3.get_bucket_lifecycle_configuration(Bucket=bucket["name"])
                if response.get("Rules"):
                    continue
            except Exception as exc:
                error = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if error not in {"NoSuchLifecycleConfiguration", "NoSuchLifecycle"}:
                    logger.debug("Could not inspect lifecycle for %s: %s", bucket["name"], exc)
                    continue
            name = str(bucket["name"])
            findings.append(
                Recommendation(
                    id=self._id("hygiene", "s3", name, "missing-lifecycle"),
                    category=RecommendationCategory.HYGIENE,
                    service="S3",
                    resource_id=name,
                    resource_name=name,
                    title="Review S3 lifecycle configuration",
                    severity=RecommendationSeverity.MEDIUM,
                    confidence=RecommendationConfidence.MEDIUM,
                    evidence=[f"Bucket is {age_days} days old and has no lifecycle rules"],
                    suggested_action="Review object access patterns and add transition or expiration rules where appropriate.",
                )
            )
        return findings

    async def _tags(self, required_tags: list[str]) -> list[Recommendation]:
        result = await self._governance.get_tag_compliance_async(required_tags)
        findings: list[Recommendation] = []
        for resource in result.get("details", []):
            missing = resource.get("missing_tags", [])
            if not missing:
                continue
            arn = str(resource["arn"])
            findings.append(
                Recommendation(
                    id=self._id("governance", "tags", arn, "missing-required-tags"),
                    category=RecommendationCategory.GOVERNANCE,
                    service="Tags",
                    resource_id=arn,
                    title="Add required ownership tags",
                    severity=RecommendationSeverity.MEDIUM,
                    confidence=RecommendationConfidence.HIGH,
                    evidence=[f"Missing required tags: {', '.join(missing)}"],
                    suggested_action="Add the missing tags after confirming the resource owner and project.",
                )
            )
        return findings
