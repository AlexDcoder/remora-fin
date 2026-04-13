"""Cost Service — AWS Cost Explorer integration with Builder pattern.

Design Patterns: Repository + Builder (CostQueryBuilder)
Uses AWS NATIVE get_cost_and_usage() for all raw data collection.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import polars as pl

from remora.schemas.common import DateRange
from remora.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)
from remora.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)

# Valid metrics from AWS native API
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
    "SERVICE", "LINKED_ACCOUNT", "REGION", "USAGE_TYPE",
    "PLATFORM", "INSTANCE_TYPE", "PURCHASE_TYPE", "AZ",
    "TENANCY", "OPERATION", "RECORD_TYPE",
)


class CostQueryBuilder:
    """Builder for AWS Cost Explorer query parameters.

    Usage:
        query = (CostQueryBuilder()
            .with_time_period(start, end)
            .with_granularity("DAILY")
            .with_metric("UnblendedCost")
            .with_filter("SERVICE", "AmazonEC2")
            .with_group_by("DIMENSION", "SERVICE")
            .build())
    """

    def __init__(self) -> None:
        self._time_period: dict[str, str] | None = None
        self._granularity: str = "DAILY"
        self._metrics: list[str] = ["UnblendedCost"]
        self._filters: list[dict[str, Any]] = []
        self._group_by: list[dict[str, str]] = []
        self._next_page_token: str | None = None

    def with_time_period(self, start: date, end: date) -> "CostQueryBuilder":
        self._time_period = {"Start": start.isoformat(), "End": end.isoformat()}
        return self

    def with_granularity(self, granularity: str) -> "CostQueryBuilder":
        g = granularity.upper()
        if g not in VALID_GRANULARITIES:
            raise ValueError(f"Invalid granularity: {granularity}. Must be one of {VALID_GRANULARITIES}")
        self._granularity = g
        return self

    def with_metric(self, metric: str) -> "CostQueryBuilder":
        if metric not in VALID_METRICS:
            raise ValueError(f"Invalid metric: {metric}. Must be one of {VALID_METRICS}")
        self._metrics = [metric]
        return self

    def with_filter(
        self,
        key: str,
        value: str,
        match_option: str = "EQUALS",
    ) -> "CostQueryBuilder":
        """Add a dimension/tag/cost category filter."""
        if key.upper() in DIMENSION_KEYS:
            self._filters.append({
                "Dimensions": {
                    "Key": key.upper(),
                    "Values": [value],
                    "MatchOptions": [match_option],
                }
            })
        else:
            # Treat as tag
            self._filters.append({
                "Tags": {
                    "Key": key,
                    "Values": [value],
                    "MatchOptions": [match_option],
                }
            })
        return self

    def with_logical_operator(
        self,
        operator: str,
        filters: list[dict[str, Any]],
    ) -> "CostQueryBuilder":
        """Combine filters with And/Or/Not."""
        op = operator.upper()
        if op not in ("AND", "OR", "NOT"):
            raise ValueError(f"Invalid operator: {operator}")
        self._filters.append({op: filters})
        return self

    def with_group_by(
        self,
        group_type: str,
        key: str,
    ) -> "CostQueryBuilder":
        gt = group_type.upper()
        if gt not in ("DIMENSION", "TAG", "COST_CATEGORY"):
            raise ValueError(f"Invalid group type: {group_type}")
        self._group_by.append({"Type": gt, "Key": key})
        return self

    def with_page_token(self, token: str) -> "CostQueryBuilder":
        self._next_page_token = token
        return self

    def build(self) -> dict[str, Any]:
        """Build the query dict ready for boto3."""
        if not self._time_period:
            raise ValueError("Time period is required. Call with_time_period() first.")

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
        if self._next_page_token:
            query["NextPageToken"] = self._next_page_token
        return query


class CostService:
    """Repository for AWS Cost Explorer data.

    All raw data comes from AWS NATIVE APIs.
    Polars is used for complementary transformations.
    """

    def __init__(self, session: AWSSession | None = None) -> None:
        self._session = session or AWSSession.get_instance()

    def _fetch_all_pages(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch all paginated results automatically."""
        ce = self._session.cost_explorer()
        pages = []
        current_query = query.copy()

        while True:
            resp = ce.get_cost_and_usage(**current_query)
            pages.append(resp)
            next_token = resp.get("NextPageToken")
            if not next_token:
                break
            current_query["NextPageToken"] = next_token

        logger.info("Fetched %d pages from Cost Explorer", len(pages))
        return pages

    def _parse_results(self, pages: list[dict[str, Any]]) -> pl.DataFrame:
        """Parse Cost Explorer response into a Polars DataFrame."""
        rows = []
        for page in pages:
            for result in page.get("ResultsByTime", []):
                time_period = result.get("TimePeriod", {})
                period_start = datetime.strptime(
                    time_period.get("Start", ""), "%Y-%m-%d"
                ).date()

                # Total metrics (no group-by)
                totals = result.get("Total", {})
                unblended = Decimal(totals.get("UnblendedCost", {}).get("Amount", "0"))
                blended = Decimal(totals.get("BlendedCost", {}).get("Amount", "0"))
                amortized = Decimal(totals.get("AmortizedCost", {}).get("Amount", "0"))

                rows.append({
                    "date": period_start,
                    "service": "",
                    "account": "",
                    "region": None,
                    "usage_type": None,
                    "unblended_cost": unblended,
                    "blended_cost": blended,
                    "amortized_cost": amortized,
                    "usage_quantity": Decimal("0"),
                    "currency": totals.get("UnblendedCost", {}).get("Unit", "USD"),
                })

                # Group-level metrics
                for group in result.get("Groups", []):
                    keys = group.get("Keys", [])
                    metrics = group.get("Metrics", {})
                    rows.append({
                        "date": period_start,
                        "service": keys[0] if len(keys) > 0 else "",
                        "account": keys[1] if len(keys) > 1 else "",
                        "region": None,
                        "usage_type": None,
                        "unblended_cost": Decimal(
                            metrics.get("UnblendedCost", {}).get("Amount", "0")
                        ),
                        "blended_cost": Decimal(
                            metrics.get("BlendedCost", {}).get("Amount", "0")
                        ),
                        "amortized_cost": Decimal(
                            metrics.get("AmortizedCost", {}).get("Amount", "0")
                        ),
                        "usage_quantity": Decimal(
                            metrics.get("UsageQuantity", {}).get("Amount", "0")
                        ),
                        "currency": metrics.get("UnblendedCost", {}).get("Unit", "USD"),
                    })

        return pl.DataFrame(rows, schema={
            "date": pl.Date,
            "service": pl.Utf8,
            "account": pl.Utf8,
            "region": pl.Utf8,
            "usage_type": pl.Utf8,
            "unblended_cost": pl.Decimal(scale=6),
            "blended_cost": pl.Decimal(scale=6),
            "amortized_cost": pl.Decimal(scale=6),
            "usage_quantity": pl.Decimal(scale=6),
            "currency": pl.Utf8,
        })

    # -- Public API --

    def get_total_cost(
        self,
        start: date,
        end: date,
        granularity: str = "DAILY",
        metric: str = "UnblendedCost",
    ) -> CostSummary:
        """Get total cost summary for a period."""
        query = (
            CostQueryBuilder()
            .with_time_period(start, end)
            .with_granularity(granularity)
            .with_metric(metric)
            .with_group_by("DIMENSION", "SERVICE")
            .build()
        )
        pages = self._fetch_all_pages(query)
        df = self._parse_results(pages)

        # Aggregations with Polars
        total = df["unblended_cost"].sum()
        daily_avg = df.group_by("date").agg(pl.col("unblended_cost").sum())["unblended_cost"].mean()
        daily_totals = df.group_by("date").agg(pl.col("unblended_cost").sum())["unblended_cost"]

        top_services = (
            df.filter(pl.col("service") != "")
            .group_by("service")
            .agg(pl.col("unblended_cost").sum())
            .sort("unblended_cost", descending=True)
        )

        return CostSummary(
            total_cost=total,
            daily_average=daily_avg or Decimal("0"),
            max_daily_cost=daily_totals.max() or Decimal("0"),
            min_daily_cost=daily_totals.min() or Decimal("0"),
            top_service=top_services["service"][0] if len(top_services) > 0 else "Unknown",
            num_services=df.filter(pl.col("service") != "")["service"].n_unique(),
            num_accounts=df.filter(pl.col("account") != "")["account"].n_unique(),
        )

    def get_cost_by_service(
        self,
        start: date,
        end: date,
        granularity: str = "DAILY",
        metric: str = "UnblendedCost",
    ) -> CostBreakdown:
        """Get cost breakdown by service."""
        query = (
            CostQueryBuilder()
            .with_time_period(start, end)
            .with_granularity(granularity)
            .with_metric(metric)
            .with_group_by("DIMENSION", "SERVICE")
            .build()
        )
        pages = self._fetch_all_pages(query)
        df = self._parse_results(pages)

        # Filter grouped entries
        grouped_df = (
            df.filter(pl.col("service") != "")
            .group_by("service")
            .agg(pl.col("unblended_cost").sum())
            .sort("unblended_cost", descending=True)
        )

        total_cost = df["unblended_cost"].sum()
        groups = []
        for row in grouped_df.iter_rows(named=True):
            service = row["service"]
            cost = row["unblended_cost"]
            pct = float(cost / total_cost * 100) if total_cost > 0 else 0.0
            groups.append(CostGroup(
                key=service,
                label=service,
                cost=cost,
                percentage=round(pct, 2),
            ))

        entries = [
            CostEntry(
                date=r["date"],
                service=r["service"],
                linked_account=r["account"],
                unblended_cost=r["unblended_cost"],
                blended_cost=r["blended_cost"],
                amortized_cost=r["amortized_cost"],
            )
            for r in df.iter_rows(named=True)
        ]

        summary = self.get_total_cost(start, end, granularity, metric)

        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity=granularity,
            metric=metric,
            entries=entries,
            groups=groups,
            summary=summary,
        )

    def get_daily_trend(
        self,
        start: date,
        end: date,
        metric: str = "UnblendedCost",
    ) -> CostTrend:
        """Get daily cost trend."""
        query = (
            CostQueryBuilder()
            .with_time_period(start, end)
            .with_granularity("DAILY")
            .with_metric(metric)
            .build()
        )
        pages = self._fetch_all_pages(query)
        df = self._parse_results(pages)

        daily = (
            df.group_by("date")
            .agg(pl.col("unblended_cost").sum().alias("cost"))
            .sort("date")
        )

        points = [
            CostTrendPoint(date=r["date"], cost=r["cost"])
            for r in daily.iter_rows(named=True)
        ]

        return CostTrend(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric=metric,
            points=points,
        )

    def get_cost_by_account(
        self,
        start: date,
        end: date,
        granularity: str = "DAILY",
        metric: str = "UnblendedCost",
    ) -> CostBreakdown:
        """Get cost breakdown by AWS account."""
        query = (
            CostQueryBuilder()
            .with_time_period(start, end)
            .with_granularity(granularity)
            .with_metric(metric)
            .with_group_by("DIMENSION", "LINKED_ACCOUNT")
            .build()
        )
        pages = self._fetch_all_pages(query)
        df = self._parse_results(pages)
        summary = self.get_total_cost(start, end, granularity, metric)

        grouped = (
            df.filter(pl.col("account") != "")
            .group_by("account")
            .agg(pl.col("unblended_cost").sum())
            .sort("unblended_cost", descending=True)
        )

        total = df["unblended_cost"].sum()
        groups = []
        for row in grouped.iter_rows(named=True):
            acct = row["account"]
            cost = row["unblended_cost"]
            pct = float(cost / total * 100) if total > 0 else 0.0
            groups.append(CostGroup(key=acct, cost=cost, percentage=round(pct, 2)))

        entries = [
            CostEntry(
                date=r["date"],
                service=r["service"],
                linked_account=r["account"],
                unblended_cost=r["unblended_cost"],
                blended_cost=r["blended_cost"],
                amortized_cost=r["amortized_cost"],
            )
            for r in df.iter_rows(named=True)
        ]

        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity=granularity,
            metric=metric,
            entries=entries,
            groups=groups,
            summary=summary,
        )

    def get_reservation_coverage(
        self,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        """Get Reserved Instance coverage from native API."""
        ce = self._session.cost_explorer()
        resp = ce.get_reservation_coverage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        )
        return resp

    def get_savings_plans_coverage(
        self,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        """Get Savings Plans coverage from native API."""
        ce = self._session.cost_explorer()
        resp = ce.get_savings_plans_coverage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        )
        return resp

    def get_tag_coverage(
        self,
        start: date,
        end: date,
    ) -> list[str]:
        """Get available cost allocation tags."""
        ce = self._session.cost_explorer()
        resp = ce.get_tags(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            SearchString="",
        )
        return resp.get("Tags", [])

    def get_budget_performance(
        self,
        budget_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get budget performance history."""
        budgets = self._session.budgets()
        accounts = self._session.sts().get_caller_identity()
        account_id = accounts["Account"]

        if budget_name:
            resp = budgets.describe_budget_performance_history(
                AccountId=account_id,
                BudgetName=budget_name,
            )
            return [resp]

        # Get all budgets
        all_budgets = budgets.describe_budgets(AccountId=account_id)
        results = []
        for budget in all_budgets.get("Budgets", []):
            name = budget["BudgetName"]
            perf = budgets.describe_budget_performance_history(
                AccountId=account_id,
                BudgetName=name,
            )
            results.append(perf)
        return results
