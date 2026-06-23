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
    """Service to correlate cost, pricing, and utilization for EC2, RDS, and Lambda."""

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
        instances = await self._inventory.list_resources_async("ec2")
        results = []

        for inst in instances:
            instance_id = inst["id"]
            instance_type = inst["type"]

            price_detail = self._pricing.get_ec2_price(instance_type, self._session.region)
            on_demand = price_detail.on_demand_price if price_detail else None
            hourly_rate = on_demand.price_per_unit if on_demand else Decimal("0")

            cpu_summary = self._metrics.get_ec2_cpu_utilization(instance_id, days=days)
            avg_cpu = cpu_summary.average if cpu_summary else 0.0

            waste_percent = max(0, 100 - (avg_cpu * 2)) / 100
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
        buckets = await self._inventory.list_resources_async("s3")
        results = []

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

    async def get_rds_efficiency(self, days: int = 7) -> list[dict[str, Any]]:
        instances = await self._inventory.list_resources_async("rds")
        results = []

        for inst in instances:
            db_id = inst["id"]
            instance_class = inst["class"]
            engine = inst["engine"]

            price_detail = self._pricing.get_rds_price(instance_class, self._session.region, engine)
            on_demand = price_detail.on_demand_price if price_detail else None
            hourly_rate = on_demand.price_per_unit if on_demand else Decimal("0")

            cpu_summary = self._metrics.get_rds_cpu_utilization(db_id, days=days)
            avg_cpu = cpu_summary.average if cpu_summary else 0.0

            is_underutilized = avg_cpu < 10.0 if cpu_summary else False
            waste_percent = max(0, 100 - (avg_cpu * 2)) / 100 if avg_cpu > 0 else 0.8
            potential_savings = hourly_rate * Decimal(24 * days) * Decimal(str(waste_percent))

            results.append(
                {
                    "id": db_id,
                    "class": instance_class,
                    "engine": engine,
                    "status": inst["status"],
                    "hourly_rate": hourly_rate,
                    "avg_cpu": avg_cpu,
                    "is_underutilized": is_underutilized,
                    "potential_savings_7d": potential_savings,
                }
            )

        return sorted(results, key=lambda x: x["potential_savings_7d"], reverse=True)

    async def get_lambda_efficiency(self, days: int = 7) -> list[dict[str, Any]]:
        functions = await self._inventory.list_resources_async("lambda")
        results = []

        price_data = self._pricing.get_lambda_price(self._session.region)
        duration_price = price_data.get("duration")
        request_price = price_data.get("requests")

        duration_rate = duration_price.on_demand_price.price_per_unit if duration_price and duration_price.on_demand_price else Decimal("0.0000166667")
        request_rate = request_price.on_demand_price.price_per_unit if request_price and request_price.on_demand_price else Decimal("0.0000002")

        for func in functions:
            name = func["name"]
            memory = func.get("memory", 128)

            duration_summary = getattr(self._metrics, "get_lambda_duration", lambda *args, **kwargs: None)(name, days=days)
            error_summary = getattr(self._metrics, "get_lambda_errors", lambda *args, **kwargs: None)(name, days=days)

            avg_duration_ms = duration_summary.average if duration_summary else 0.0
            avg_duration_sec = avg_duration_ms / 1000.0
            error_count = error_summary.max if error_summary else 0.0

            memory_gb = memory / 1024.0
            cost_per_invocation = Decimal(memory_gb * avg_duration_sec) * duration_rate
            cost_per_invocation += request_rate

            is_efficient = avg_duration_ms < 100 and error_count < 10

            results.append(
                {
                    "name": name,
                    "memory_mb": memory,
                    "avg_duration_ms": avg_duration_ms,
                    "error_count_7d": error_count,
                    "is_efficient": is_efficient,
                    "estimated_cost_per_invocation": cost_per_invocation,
                }
            )

        return sorted(results, key=lambda x: x["estimated_cost_per_invocation"], reverse=True)