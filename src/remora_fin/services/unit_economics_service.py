"""Unit Economics Service — Correlating Inventory, Cost, Pricing, and Metrics.

This service provides high-level analysis by combining multiple data sources
to calculate the efficiency and cost-effectiveness of AWS resources.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.base_service import BaseService
from remora_fin.services.inventory_service import InventoryService
from remora_fin.services.metrics_service import MetricsService
from remora_fin.services.pricing_service import PricingService

logger = logging.getLogger(__name__)


class UnitEconomicsService(BaseService):
    """Service to correlate cost, pricing, and utilization."""

    def __init__(
        self,
        session: AWSSession | None = None,
        inventory: InventoryService | None = None,
        pricing: PricingService | None = None,
        metrics: MetricsService | None = None,
    ) -> None:
        super().__init__("unit_economics", session)
        self._inventory = inventory or InventoryService(session)
        self._pricing = pricing or PricingService(session)
        self._metrics = metrics or MetricsService(session)

    async def get_ec2_efficiency(self, days: int = 7) -> list[dict[str, Any]]:
        """Calculate efficiency for EC2 instances."""
        instances = await self._inventory.list_resources_async("ec2")
        results = []

        for inst in instances:
            instance_id = inst["id"]
            instance_type = inst["type"]

            # Get pricing
            price_detail = self._pricing.get_ec2_price(instance_type, self._session.region)
            on_demand = price_detail.on_demand_price if price_detail else None
            hourly_rate = on_demand.price_per_unit if on_demand else Decimal("0")

            # Get metrics
            cpu_summary = self._metrics.get_ec2_cpu_utilization(instance_id, days=days)
            avg_cpu = cpu_summary.average if cpu_summary else 0.0

            # Calculate waste (rough estimate)
            # If CPU < 10%, we consider 90% of the cost as potential waste
            waste_percent = max(0, 100 - (avg_cpu * 2)) / 100  # Conservative multiplier
            potential_savings = hourly_rate * Decimal(24 * days) * Decimal(str(waste_percent))

            results.append(
                {
                    "id": instance_id,
                    "name": inst["name"],
                    "type": instance_type,
                    "hourly_rate": hourly_rate,
                    "avg_cpu": avg_cpu,
                    "is_underutilized": cpu_summary.is_underutilized if cpu_summary else False,
                    "potential_savings_7d": potential_savings,
                }
            )

        return sorted(results, key=lambda x: x["potential_savings_7d"], reverse=True)

    async def get_s3_efficiency(self) -> list[dict[str, Any]]:
        """Analyze S3 buckets for pricing tiers."""
        buckets = await self._inventory.list_resources_async("s3")
        results = []

        # S3 pricing is more complex (storage classes), here we just show standard rate
        standard_price = self._pricing.get_s3_price("Standard", self._session.region)
        rate = (
            standard_price.on_demand_price.price_per_unit
            if standard_price and standard_price.on_demand_price
            else Decimal("0.023")
        )

        for b in buckets:
            results.append(
                {
                    "name": b["name"],
                    "creation_date": b["creation_date"],
                    "standard_rate_gb": rate,
                }
            )

        return results
