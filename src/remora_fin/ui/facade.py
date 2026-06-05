"""UI Facade — Centralized orchestration for Textual TUI.

Provides a unified interface for screens to fetch formatted, UI-ready data,
optimizing performance through centralized caching and parallel orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NamedTuple

from remora_fin.services import (
    AnomalyService,
    AWSSession,
    CostService,
    DashboardService,
    ForecastService,
    InventoryService,
)

logger = logging.getLogger(__name__)


class DashboardUIData(NamedTuple):
    """UI-ready data for the dashboard."""

    total_cost: str
    daily_avg: str
    anomaly_count: int
    inventory: str
    status_title: str
    status_subtitle: str
    chart_data: list[tuple[str, float]]
    table_data: list[tuple[str, str, str]]


class UIFacade:
    """Facade for Textual UI to interact with services."""

    def __init__(self, session: AWSSession | None) -> None:
        self._session = session
        self._dashboard_service = DashboardService(session)
        self._cost_service = CostService(session)
        self._anomaly_service = AnomalyService(session)
        self._forecast_service = ForecastService(session)
        self._inventory_service = InventoryService(session)

        # Data cache for UI performance
        self._cache: dict[str, Any] = {}
        self._cache_expiry: dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes default

    def _get_from_cache(self, key: str) -> Any | None:
        """Retrieve from internal cache if valid."""
        import time

        if key in self._cache and time.time() < self._cache_expiry.get(key, 0):
            return self._cache[key]
        return None

    def _set_to_cache(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store in internal cache with expiry."""
        import time

        self._cache[key] = value
        self._cache_expiry[key] = time.time() + (ttl or self._cache_ttl)

    async def get_available_services(self, days: int, region: str | None = None) -> list[str]:
        """Fetch list of active services for filtering (with caching)."""
        cache_key = f"services_{days}_{region}"
        cached = self._get_from_cache(cache_key)
        if isinstance(cached, list):
            return cached

        end = date.today()
        start = end - timedelta(days=days)

        try:
            breakdown = await self._cost_service.get_cost_by_service_async(start, end, region=region)
            cost_services = {g.key for g in breakdown.groups if g.key} if breakdown else set()

            # Resources available in the Inventory Registry
            integrated_services = {
                "CloudFront",
                "DynamoDB",
                "EC2",
                "ElastiCache",
                "EMR",
                "KMS",
                "Lambda",
                "RDS",
                "Redshift",
                "S3",
                "SageMaker",
                "SecretsManager",
                "SNS",
                "SQS",
            }

            services = sorted(list(cost_services | integrated_services))
            self._set_to_cache(cache_key, services)
            return services
        except Exception as e:
            logger.error(f"UIFacade: Failed to load services: {e}")
            return []

    async def get_dashboard_data(
        self,
        days: int,
        region: str | None = None,
        selected_service: str = "All Services",
    ) -> DashboardUIData:
        """Fetch and format dashboard data based on selection (with caching)."""
        cache_key = f"dashboard_{days}_{region}_{selected_service}"
        cached = self._get_from_cache(cache_key)
        if isinstance(cached, DashboardUIData):
            return cached

        data: DashboardUIData
        if selected_service == "All Services":
            data = await self._get_all_services_dashboard(days, region)
        else:
            data = await self._get_single_service_dashboard(selected_service, days, region)

        self._set_to_cache(cache_key, data)
        return data

    async def _get_all_services_dashboard(self, days: int, region: str | None = None) -> DashboardUIData:
        """Logic for comprehensive 'All Services' dashboard view."""
        data = await self._dashboard_service.get_summary_parallel(days=days, region=region)

        summary = data.get("cost_summary")
        trend = data.get("cost_trend")
        anomalies = data.get("anomalies")
        infra_counts = data.get("infrastructure", {}).get("counts", {})

        total_cost_str = f"${summary.total_cost:,.2f}" if summary else "$0.00"
        daily_avg_str = f"${summary.daily_average:,.2f}" if summary else "$0.00"
        anomaly_count = anomalies.total_anomalies if anomalies else 0
        total_resources = sum(infra_counts.values()) if infra_counts else 0

        chart_data = [(str(p.date), float(p.cost)) for p in trend.points] if trend else []

        # Report table data (top costs)
        end = date.today()
        start = end - timedelta(days=days)
        breakdown = await self._cost_service.get_cost_by_service_async(start, end, region=region)
        table_data = [("•", g.key, f"${g.cost:,.2f}") for g in breakdown.groups[:50]] if breakdown else []

        return DashboardUIData(
            total_cost=total_cost_str,
            daily_avg=daily_avg_str,
            anomaly_count=anomaly_count,
            inventory=f"{total_resources} Res",
            status_title=f"Region: {region or 'Global'}",
            status_subtitle="Comprehensive Monitoring",
            chart_data=chart_data,
            table_data=table_data,
        )

    async def _get_single_service_dashboard(
        self, service: str, days: int, region: str | None = None
    ) -> DashboardUIData:
        """Logic for specialized single service analysis view."""
        end = date.today()
        start = end - timedelta(days=days)

        tasks = [
            self._cost_service.get_cost_by_service_async(start, end, region=region),
            self._cost_service.get_daily_trend_async(start, end, region=region),
            self._inventory_service.list_resources_async(service, use_cache=True),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        from remora_fin.schemas.cost import CostBreakdown

        svc_breakdown = results[0] if isinstance(results[0], CostBreakdown) else None
        inventory_data = results[2] if not isinstance(results[2], BaseException) else []

        service_group = (
            next((g for g in svc_breakdown.groups if service.lower() in g.key.lower()), None) if svc_breakdown else None
        )
        display_total = service_group.cost if service_group else Decimal("0")
        display_avg = display_total / days
        inventory_str = f"{len(inventory_data)} Res" if isinstance(inventory_data, list) else "—"

        # Chart points (Daily breakdown for the specific service)
        chart_points = []
        if svc_breakdown:
            service_entries = [e for e in svc_breakdown.entries if service.lower() in e.service.lower()]
            daily_map: dict[str, float] = {}
            for e in service_entries:
                daily_map[str(e.date)] = daily_map.get(str(e.date), 0.0) + float(e.unblended_cost)
            chart_points = sorted(daily_map.items())

        # Table data (Detailed cost entries)
        table_data = []
        if svc_breakdown:
            service_entries = sorted(
                [e for e in svc_breakdown.entries if service.lower() in e.service.lower()],
                key=lambda x: x.date,
                reverse=True,
            )
            table_data = [(str(e.date), e.service, f"${e.unblended_cost:,.2f}") for e in service_entries[:100]]

        # Contextual metadata
        svc_contexts = {
            "EC2": "Server Fleet & Instances",
            "RDS": "Relational Database Clusters",
            "S3": "Object Storage Buckets",
            "Lambda": "Serverless Function Matrix",
            "DynamoDB": "NoSQL Table Performance",
            "SageMaker": "ML Models & Notebooks",
            "CloudFront": "Edge Content Delivery",
            "ElastiCache": "In-Memory Cache Clusters",
            "Redshift": "Data Warehouse Clusters",
            "EMR": "Big Data Analysis",
            "SNS": "Pub/Sub Messaging Topics",
            "SQS": "Message Queue Latency",
            "KMS": "Cryptographic Key Matrix",
            "SecretsManager": "Sensitive Credential Vault",
        }
        context = "AWS Service Analysis"
        for key, ctx in svc_contexts.items():
            if key.lower() in service.lower():
                context = ctx
                break

        return DashboardUIData(
            total_cost=f"${display_total:,.2f}",
            daily_avg=f"${display_avg:,.2f}",
            anomaly_count=0,
            inventory=inventory_str,
            status_title=service,
            status_subtitle=context,
            chart_data=chart_points,
            table_data=table_data,
        )

    async def get_cost_data(self, days: int) -> list[tuple[str, float]]:
        """Fetch basic cost trend data."""
        end = date.today()
        start = end - timedelta(days=days)
        trend = await self._cost_service.get_daily_trend_async(start, end)
        return [(str(p.date), float(p.cost)) for p in trend.points]

    async def get_anomaly_report(self, days: int) -> Any:
        """Fetch anomaly detection report."""
        end = date.today()
        start = end - timedelta(days=min(days, 90))
        return await self._anomaly_service.get_anomaly_summary_async(start, end)

    async def get_forecast_result(self, days: int) -> Any:
        """Fetch cost forecast result."""
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=days)
        return await self._forecast_service.get_aws_native_forecast_async(start=start, end=end)
