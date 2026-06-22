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
from remora_fin.services.cost_service import CostService
from remora_fin.services.governance_service import GovernanceService
from remora_fin.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)


class DashboardService(BaseService):
    """Orchestrates multiple services to provide high-agility dashboard data."""

    def __init__(
        self,
        session: AWSSession | None = None,
        cost_service: CostService | None = None,
        anomaly_service: AnomalyService | None = None,
        inventory_service: InventoryService | None = None,
        governance_service: GovernanceService | None = None,
    ) -> None:
        super().__init__("dashboard", session)
        self._cost = cost_service or CostService(self._session)
        self._anomaly = anomaly_service or AnomalyService(self._session)
        self._inventory = inventory_service or InventoryService(self._session)
        self._governance = governance_service or GovernanceService(self._session)

    async def get_summary_parallel(
        self,
        days: int = 30,
        use_cache: bool = True,
        required_tags: list[str] | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Fetch all dashboard components concurrently."""
        end = date.today()
        start = end - timedelta(days=days)
        tags = required_tags or ["Environment", "Project", "Owner"]

        logger.info(
            "Fetching comprehensive dashboard summary in parallel (period: [cyan]%d days[/], region: [cyan]%s[/])",
            days,
            region or "Global",
        )

        # Core cost and anomaly tasks
        tasks = [
            self._cost.get_total_cost_async(start, end, region=region),
            self._cost.get_daily_trend_async(start, end, region=region),
            self._anomaly.get_anomaly_summary_async(start, end, use_cache=use_cache),
            self._governance.get_tag_compliance_async(tags, use_cache=use_cache),
            # Cost breakdown by service with normalized names
            self._cost.get_cost_by_service_async(start, end, region=region),
        ]

        # Inventory tasks - consolidated via InventoryService
        resource_types = [
            "ec2",
            "rds",
            "lambda",
            "s3",
            "cloudfront",
            "dynamodb",
            "elasticache",
            "emr",
            "redshift",
            "sagemaker",
            "sns",
            "sqs",
            "kms",
            "secretsmanager",
        ]

        for r_type in resource_types:
            tasks.append(self._inventory.list_resources_async(r_type, use_cache=use_cache))

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

        # Map back results
        anomaly_data = _get_result(2)
        if isinstance(anomaly_data, str):
            anomaly_data = None

        # Get cost breakdown with normalized service names
        cost_breakdown = _get_result(4)

        infra_details = {}
        for i, r_type in enumerate(resource_types):
            infra_details[r_type] = _get_result(5 + i, [])

        summary = {
            "cost_summary": _get_result(0),
            "cost_trend": _get_result(1),
            "anomalies": anomaly_data,
            "cost_breakdown": cost_breakdown,
            "infrastructure": {
                "counts": {k: len(v) if isinstance(v, (list, dict, str)) else 0 for k, v in infra_details.items()},
                "details": infra_details,
            },
            "governance": _get_result(3),
            "last_updated": date.today().isoformat(),
        }

        return summary