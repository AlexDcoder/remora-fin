"""Cost Service — AWS Cost Explorer integration with Builder pattern.

This service provides high-level methods to query AWS Cost and Usage data,
leveraging a Builder pattern for complex query construction and Polars for
data transformation and caching.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import polars as pl

from remora_fin.schemas.common import DateRange
from remora_fin.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)
from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)

VALID_METRICS = (
    "UnblendedCost",
    "BlendedCost",
    "NetUnblendedCost",
    "NetAmortizedCost",
    "AmortizedCost",
    "UsageQuantity",
    "NormalizedUsageAmount",
)

VALID_GRANULARITIES = ("DAILY", "MONTHLY", "HOURLY")

DIMENSION_KEYS = (
    "SERVICE",
    "LINKED_ACCOUNT",
    "REGION",
    "USAGE_TYPE",
    "PLATFORM",
    "INSTANCE_TYPE",
    "PURCHASE_TYPE",
    "AZ",
    "TENANCY",
    "OPERATION",
    "RECORD_TYPE",
)


class CostQueryBuilder:
    """Fluent builder for AWS Cost Explorer query parameters."""

    def __init__(self) -> None:
        """Initialize the builder with default values."""
        self._time_period: dict[str, str] | None = None
        self._granularity: str = "DAILY"
        self._metrics: list[str] = ["UnblendedCost"]
        self._filters: list[dict[str, Any]] = []
        self._group_by: list[dict[str, str]] = []
        self._next_page_token: str | None = None

    def with_time_period(self, start: date, end: date) -> CostQueryBuilder:
        """Set the time period for the query.

        Args:
            start: Start date (inclusive).
            end: End date (exclusive).
        """
        self._time_period = {"Start": start.isoformat(), "End": end.isoformat()}
        return self

    def with_granularity(self, granularity: str) -> CostQueryBuilder:
        """Set the time granularity of the results."""
        g = granularity.upper()
        if g not in VALID_GRANULARITIES:
            raise ValueError(f"Invalid granularity: {granularity}")
        self._granularity = g
        return self

    def with_metric(self, metric: str) -> CostQueryBuilder:
        """Set the cost metric to retrieve."""
        if metric not in VALID_METRICS:
            raise ValueError(f"Invalid metric: {metric}")
        self._metrics = [metric]
        return self

    def with_filter(
        self,
        key: str,
        value: str,
        match_option: str = "EQUALS",
    ) -> CostQueryBuilder:
        """Add a dimension or tag filter to the query."""
        if key.upper() in DIMENSION_KEYS:
            self._filters.append(
                {
                    "Dimensions": {
                        "Key": key.upper(),
                        "Values": [value],
                        "MatchOptions": [match_option],
                    }
                }
            )
        else:
            self._filters.append(
                {
                    "Tags": {
                        "Key": key,
                        "Values": [value],
                        "MatchOptions": [match_option],
                    }
                }
            )
        return self

    def with_group_by(
        self,
        group_type: str,
        key: str,
    ) -> CostQueryBuilder:
        """Add a grouping criteria to the query."""
        gt = group_type.upper()
        if gt not in ("DIMENSION", "TAG", "COST_CATEGORY"):
            raise ValueError(f"Invalid group type: {group_type}")
        self._group_by.append({"Type": gt, "Key": key})
        return self

    def build(self) -> dict[str, Any]:
        """Finalize and return the query dictionary for AWS SDK."""
        if not self._time_period:
            raise ValueError("Time period is required for Cost Explorer queries.")

        query: dict[str, Any] = {
            "TimePeriod": self._time_period,
            "Granularity": self._granularity,
            "Metrics": self._metrics,
        }
        if self._filters:
            if len(self._filters) == 1:
                query["Filter"] = self._filters[0]
            else:
                query["Filter"] = {"And": self._filters}
        if self._group_by:
            query["GroupBy"] = self._group_by
        return query


class CostService(BaseService):
    """Service layer for AWS Cost and Usage data management."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        """Initialize CostService with optional AWS session and Cache service."""
        super().__init__("cost", session, cache)

    @retry_with_backoff(max_retries=5)
    def _fetch_all_pages(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Internal helper to fetch all paginated results from AWS Cost Explorer."""
        ce = self._session.cost_explorer()
        return self._session.fetch_token_paginated(ce.get_cost_and_usage, **query)

    @async_retry_with_backoff(max_retries=5)
    async def _fetch_all_pages_async(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Async version of fetch_all_pages."""
        async with self._session.async_client("ce") as ce:
            return await self._session.fetch_token_paginated_async(ce, "get_cost_and_usage", **query)

    def _parse_results(self, pages: list[dict[str, Any]]) -> pl.DataFrame:
        """Parse raw AWS Cost Explorer pages into a standardized Polars DataFrame."""
        rows = []
        for page in pages:
            for result in page.get("ResultsByTime", []):
                time_period = result.get("TimePeriod", {})
                period_start = datetime.strptime(time_period.get("Start", ""), "%Y-%m-%d").date()

                for group in result.get("Groups", []):
                    keys = group.get("Keys", [])
                    metrics = group.get("Metrics", {})
                    rows.append(
                        {
                            "date": period_start,
                            "service": keys[0] if len(keys) > 0 else "",
                            "account": keys[1] if len(keys) > 1 else "",
                            "unblended_cost": Decimal(metrics.get("UnblendedCost", {}).get("Amount", "0")),
                            "blended_cost": Decimal(metrics.get("BlendedCost", {}).get("Amount", "0")),
                            "amortized_cost": Decimal(metrics.get("AmortizedCost", {}).get("Amount", "0")),
                            "net_unblended_cost": Decimal(metrics.get("NetUnblendedCost", {}).get("Amount", "0")),
                            "usage_quantity": Decimal(metrics.get("UsageQuantity", {}).get("Amount", "0")),
                        }
                    )

                if not result.get("Groups"):
                    totals = result.get("Total", {})
                    rows.append(
                        {
                            "date": period_start,
                            "service": "Total",
                            "account": "",
                            "unblended_cost": Decimal(totals.get("UnblendedCost", {}).get("Amount", "0")),
                            "blended_cost": Decimal(totals.get("BlendedCost", {}).get("Amount", "0")),
                            "amortized_cost": Decimal(totals.get("AmortizedCost", {}).get("Amount", "0")),
                            "net_unblended_cost": Decimal(totals.get("NetUnblendedCost", {}).get("Amount", "0")),
                            "usage_quantity": Decimal(totals.get("UsageQuantity", {}).get("Amount", "0")),
                        }
                    )

        return pl.DataFrame(rows)

    def _process_pages(self, pages: list[dict[str, Any]]) -> pl.DataFrame:
        """Standardized processing of Cost Explorer response pages."""
        return self._parse_results(pages)

    def _get_data(self, query: dict[str, Any], use_cache: bool = True) -> pl.DataFrame:
        """Retrieve cost data, checking cache first."""
        if use_cache:
            cached_df = self._cache.get(query)
            if cached_df is not None:
                return cached_df

        pages = self._fetch_all_pages(query)
        df = self._process_pages(pages)

        if use_cache:
            self._cache.set(query, df)

        return df

    async def _get_data_async(self, query: dict[str, Any], use_cache: bool = True) -> pl.DataFrame:
        """Async version of _get_data."""
        if use_cache:
            cached_df = self._cache.get(query)
            if cached_df is not None:
                return cached_df

        try:
            pages = await self._fetch_all_pages_async(query)
            df = self._process_pages(pages)
        except Exception as e:
            logger.error(f"Error fetching cost data async: {e}")
            return pl.DataFrame()

        if use_cache:
            self._cache.set(query, df)

        return df

    def _get_metric_column(self, metric: str) -> str:
        """Map AWS metric name to internal DataFrame column name."""
        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
            "UsageQuantity": "usage_quantity",
        }
        return col_map.get(metric, "unblended_cost")

    def get_total_cost(self, start: date, end: date, region: str | None = None) -> CostSummary:
        """Get summary of total costs for a given period."""
        builder = CostQueryBuilder().with_time_period(start, end).with_group_by("DIMENSION", "SERVICE")
        if region:
            builder.with_filter("REGION", region)
        df = self._get_data(builder.build())
        return self._summarize_df(df)

    async def get_total_cost_async(self, start: date, end: date, region: str | None = None) -> CostSummary:
        """Async version of get_total_cost."""
        builder = CostQueryBuilder().with_time_period(start, end).with_group_by("DIMENSION", "SERVICE")
        if region:
            builder.with_filter("REGION", region)
        df = await self._get_data_async(builder.build())
        return self._summarize_df(df)

    def _summarize_df(self, df: pl.DataFrame) -> CostSummary:
        """Helper to create CostSummary from DataFrame."""
        if df.is_empty():
            return CostSummary(
                total_cost=Decimal("0"),
                daily_average=Decimal("0"),
                max_daily_cost=Decimal("0"),
                min_daily_cost=Decimal("0"),
                top_service="N/A",
                num_services=0,
                num_accounts=0,
            )

        total = df["unblended_cost"].sum()
        daily_agg = df.group_by("date").agg(pl.col("unblended_cost").sum())
        daily_avg = daily_agg["unblended_cost"].mean()

        top_service_df = (
            df.filter(pl.col("service") != "Total")
            .group_by("service")
            .agg(pl.col("unblended_cost").sum())
            .sort("unblended_cost", descending=True)
        )

        return CostSummary(
            total_cost=Decimal(str(total)),
            daily_average=Decimal(str(daily_avg or 0)),
            max_daily_cost=Decimal(str(daily_agg["unblended_cost"].max() or 0)),
            min_daily_cost=Decimal(str(daily_agg["unblended_cost"].min() or 0)),
            top_service=top_service_df["service"][0] if len(top_service_df) > 0 else "N/A",
            num_services=df.filter(pl.col("service") != "Total")["service"].n_unique(),
            num_accounts=df["account"].n_unique(),
        )

    def get_daily_trend(
        self, start: date, end: date, metric: str = "UnblendedCost", region: str | None = None
    ) -> CostTrend:
        """Get daily cost trend for a given period."""
        builder = CostQueryBuilder().with_time_period(start, end).with_metric(metric).with_granularity("DAILY")
        if region:
            builder.with_filter("REGION", region)
        query = builder.build()
        df = self._get_data(query)

        # metric name to column name mapping
        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
            "UsageQuantity": "usage_quantity",
        }
        col_name = col_map.get(metric, "unblended_cost")

        daily_data = df.filter(pl.col("service") == "Total").sort("date")

        points = [
            CostTrendPoint(date=r["date"], cost=Decimal(str(r[col_name])), usage=Decimal(str(r["usage_quantity"])))
            for r in daily_data.iter_rows(named=True)
        ]

        return CostTrend(period=DateRange(start=start, end=end), granularity="DAILY", metric=metric, points=points)

    async def get_daily_trend_async(
        self, start: date, end: date, metric: str = "UnblendedCost", region: str | None = None
    ) -> CostTrend:
        """Async version of get_daily_trend."""
        builder = CostQueryBuilder().with_time_period(start, end).with_metric(metric).with_granularity("DAILY")
        if region:
            builder.with_filter("REGION", region)
        query = builder.build()
        df = await self._get_data_async(query)

        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
            "UsageQuantity": "usage_quantity",
        }
        col_name = col_map.get(metric, "unblended_cost")

        if df.is_empty():
            return CostTrend(period=DateRange(start=start, end=end), granularity="DAILY", metric=metric, points=[])

        daily_data = df.filter(pl.col("service") == "Total").sort("date")
        points = [
            CostTrendPoint(date=r["date"], cost=Decimal(str(r[col_name])), usage=Decimal(str(r["usage_quantity"])))
            for r in daily_data.iter_rows(named=True)
        ]

        return CostTrend(period=DateRange(start=start, end=end), granularity="DAILY", metric=metric, points=points)

    async def get_cost_by_service_async(
        self, start: date, end: date, metric: str = "UnblendedCost", region: str | None = None
    ) -> CostBreakdown:
        """Async version of get_cost_by_service."""
        builder = (
            CostQueryBuilder().with_time_period(start, end).with_metric(metric).with_group_by("DIMENSION", "SERVICE")
        )
        if region:
            builder.with_filter("REGION", region)
        query = builder.build()
        df = await self._get_data_async(query)

        if df.is_empty():
            return CostBreakdown(
                period=DateRange(start=start, end=end),
                granularity="DAILY",
                metric=metric,
                entries=[],
                groups=[],
                summary=await self.get_total_cost_async(start, end, region=region),
            )

        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
        }
        col_name = col_map.get(metric, "unblended_cost")

        grouped = (
            df.filter(pl.col("service") != "Total")
            .group_by("service")
            .agg([pl.col(col_name).sum(), pl.col("usage_quantity").sum()])
            .sort(col_name, descending=True)
        )

        total = grouped[col_name].sum()
        groups = [
            CostGroup(
                key=r["service"],
                label=r["service"],
                cost=Decimal(str(r[col_name])),
                percentage=float(r[col_name] / total * 100) if total > 0 else 0,
                usage_quantity=Decimal(str(r["usage_quantity"])),
            )
            for r in grouped.iter_rows(named=True)
        ]

        entries = [
            CostEntry(
                date=r["date"],
                service=r["service"],
                linked_account=r["account"],
                unblended_cost=Decimal(str(r["unblended_cost"])),
                blended_cost=Decimal(str(r["blended_cost"])),
                amortized_cost=Decimal(str(r["amortized_cost"])),
                usage_quantity=Decimal(str(r["usage_quantity"])),
            )
            for r in df.iter_rows(named=True)
        ]

        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric=metric,
            entries=entries,
            groups=groups,
            summary=await self.get_total_cost_async(start, end, region=region),
        )

    def get_cost_by_service(
        self, start: date, end: date, metric: str = "UnblendedCost", region: str | None = None
    ) -> CostBreakdown:
        """Get cost breakdown grouped by AWS service."""
        builder = (
            CostQueryBuilder().with_time_period(start, end).with_metric(metric).with_group_by("DIMENSION", "SERVICE")
        )
        if region:
            builder.with_filter("REGION", region)
        query = builder.build()
        df = self._get_data(query)

        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
        }
        col_name = col_map.get(metric, "unblended_cost")

        grouped = (
            df.filter(pl.col("service") != "Total")
            .group_by("service")
            .agg([pl.col(col_name).sum(), pl.col("usage_quantity").sum()])
            .sort(col_name, descending=True)
        )

        total = grouped[col_name].sum()

        groups = [
            CostGroup(
                key=r["service"],
                label=r["service"],
                cost=Decimal(str(r[col_name])),
                percentage=float(r[col_name] / total * 100) if total > 0 else 0,
                usage_quantity=Decimal(str(r["usage_quantity"])),
            )
            for r in grouped.iter_rows(named=True)
        ]

        entries = [
            CostEntry(
                date=r["date"],
                service=r["service"],
                linked_account=r["account"],
                unblended_cost=r["unblended_cost"],
                blended_cost=r["blended_cost"],
                amortized_cost=r["amortized_cost"],
                usage_quantity=r["usage_quantity"],
            )
            for r in df.iter_rows(named=True)
        ]

        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric=metric,
            entries=entries,
            groups=groups,
            summary=self.get_total_cost(start, end, region=region),
        )

    def get_cost_by_account(self, start: date, end: date, metric: str = "UnblendedCost") -> CostBreakdown:
        """Get cost breakdown grouped by AWS account."""
        query = (
            CostQueryBuilder()
            .with_time_period(start, end)
            .with_metric(metric)
            .with_group_by("DIMENSION", "LINKED_ACCOUNT")
            .build()
        )
        df = self._get_data(query)

        col_map = {
            "UnblendedCost": "unblended_cost",
            "BlendedCost": "blended_cost",
            "AmortizedCost": "amortized_cost",
            "NetUnblendedCost": "net_unblended_cost",
        }
        col_name = col_map.get(metric, "unblended_cost")

        grouped = (
            df.filter(pl.col("service") != "Total")
            .group_by("account")
            .agg([pl.col(col_name).sum(), pl.col("usage_quantity").sum()])
            .sort(col_name, descending=True)
        )

        total = grouped[col_name].sum()

        groups = [
            CostGroup(
                key=r["account"],
                label=r["account"],
                cost=Decimal(str(r[col_name])),
                percentage=float(r[col_name] / total * 100) if total > 0 else 0,
                usage_quantity=Decimal(str(r["usage_quantity"])),
            )
            for r in grouped.iter_rows(named=True)
        ]

        entries = [
            CostEntry(
                date=r["date"],
                service=r["service"],
                linked_account=r["account"],
                unblended_cost=r["unblended_cost"],
                blended_cost=r["blended_cost"],
                amortized_cost=r["amortized_cost"],
                usage_quantity=r["usage_quantity"],
            )
            for r in df.iter_rows(named=True)
        ]

        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric=metric,
            entries=entries,
            groups=groups,
            summary=self.get_total_cost(start, end),
        )

    def get_unit_economics(self, cost_df: pl.DataFrame, business_df: pl.DataFrame, on: str = "date") -> pl.DataFrame:
        """Calculate unit economics by joining cost data with business metrics.

        Args:
            cost_df: DataFrame with unblended_cost.
            business_df: DataFrame with metric_value.
            on: Column name to join on (usually 'date').
        """
        return cost_df.join(business_df, on=on).with_columns(
            (pl.col("unblended_cost") / pl.col("metric_value")).alias("cost_per_unit")
        )
