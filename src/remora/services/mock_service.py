"""Mock services for UI testing and demo mode."""

from __future__ import annotations

import random
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Any

from remora.schemas.anomaly import (
    Anomaly,
    AnomalyImpact,
    AnomalyReport,
    AnomalyRootCause,
    AnomalyScore,
    AnomalySeverity,
    AnomalyType,
    AnomalyFeedback,
)
from remora.schemas.cost import CostTrend, CostTrendPoint, CostSummary, CostBreakdown, CostGroup, CostEntry
from remora.schemas.forecast import ForecastPoint, ForecastResult, ForecastModel, ForecastMetric
from remora.schemas.common import DateRange


class MockCostService:
    """Mock implementation of CostService providing randomized data."""

    def __init__(self, session: Any = None) -> None:
        """Initialize with optional session."""
        self._session = session
        self._services = [
            "AmazonEC2", "AmazonS3", "AmazonRDS", "AWSLambda", 
            "AmazonDynamoDB", "AmazonVPC", "AmazonRoute53", "AmazonCloudWatch"
        ]

    def get_daily_trend(self, start: date, end: date) -> CostTrend:
        """Generate a random cost trend for the dashboard chart."""
        points = []
        current = start
        base_cost = 150.0
        
        while current <= end:
            daily_cost = base_cost + random.uniform(-20, 40)
            points.append(
                CostTrendPoint(
                    date=current,
                    cost=Decimal(f"{daily_cost:.2f}")
                )
            )
            current += timedelta(days=1)
            base_cost += 0.8
            
        return CostTrend(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric="UnblendedCost",
            points=points,
        )

    def get_total_cost(self, start: date, end: date) -> CostSummary:
        """Generate a summarized cost view."""
        trend = self.get_daily_trend(start, end)
        total = sum(p.cost for p in trend.points)
        avg = total / len(trend.points) if trend.points else Decimal("0")
        
        return CostSummary(
            total_cost=total,
            daily_average=avg,
            max_daily_cost=max(p.cost for p in trend.points),
            min_daily_cost=min(p.cost for p in trend.points),
            top_service="AmazonEC2",
            num_services=len(self._services),
            num_accounts=3,
        )

    def get_cost_by_service(self, start: date, end: date) -> CostBreakdown:
        """Generate a detailed cost breakdown by service with daily entries."""
        service_costs: dict[str, Decimal] = {}
        entries = []
        total_cost = Decimal("0")
        
        for svc in self._services:
            svc_total = Decimal("0")
            current = start
            while current <= end:
                # Use a specific seed for consistency per service/date if needed
                svc_daily = Decimal(f"{random.uniform(5, 50):.2f}")
                entries.append(CostEntry(
                    date=current,
                    service=svc,
                    linked_account="123456789012",
                    unblended_cost=svc_daily,
                    blended_cost=svc_daily,
                    amortized_cost=svc_daily
                ))
                svc_total += svc_daily
                current += timedelta(days=1)
            
            service_costs[svc] = svc_total
            total_cost += svc_total

        groups = []
        for svc, cost in service_costs.items():
            pct = float(cost / total_cost * 100) if total_cost > 0 else 0.0
            groups.append(CostGroup(
                key=svc,
                label=svc,
                cost=cost,
                percentage=round(pct, 2)
            ))
            
        return CostBreakdown(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric="UnblendedCost",
            entries=entries,
            groups=sorted(groups, key=lambda x: x.cost, reverse=True),
            summary=self.get_total_cost(start, end),
        )


class MockAnomalyService:
    """Mock implementation of AnomalyService."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    def get_anomaly_summary(self, start: date, end: date) -> AnomalyReport:
        """Generate random anomalies with realistic variance."""
        anomalies = []
        services = ["AmazonEC2", "AmazonS3", "AmazonRDS", "Lambda", "DynamoDB"]
        
        for i in range(5):
            service = random.choice(services)
            actual = random.uniform(800, 2000)
            expected = random.uniform(100, 300)
            variance = ((actual - expected) / expected) * 100
            severity = AnomalySeverity.from_percentage(variance)
            
            anomalies.append(
                Anomaly(
                    id=f"anomaly-{i}-{random.randint(1000, 9999)}",
                    monitor_arn=f"arn:aws:ce:us-east-1:123456789012:monitor/{service}-monitor",
                    start_date=date.today() - timedelta(days=random.randint(1, 15)),
                    dimension_value=service,
                    root_causes=[
                        AnomalyRootCause(
                            service=service,
                            contribution=Decimal(f"{actual - expected:.2f}")
                        )
                    ],
                    score=AnomalyScore(max_score=95.0, current_score=random.uniform(70, 90)),
                    impact=AnomalyImpact(
                        total_actual_spend=Decimal(f"{actual:.2f}"),
                        total_expected_spend=Decimal(f"{expected:.2f}"),
                        total_impact=Decimal(f"{actual - expected:.2f}"),
                        total_impact_percentage=variance,
                    ),
                    severity=severity,
                    anomaly_type=AnomalyType.SPIKE,
                    feedback=AnomalyFeedback.YES,
                )
            )
            
        return AnomalyReport(
            total_anomalies=len(anomalies),
            by_severity={s: sum(1 for a in anomalies if a.severity == s) for s in AnomalySeverity},
            by_type={AnomalyType.SPIKE: len(anomalies)},
            total_actual_impact=sum(a.impact.total_impact for a in anomalies),
            total_expected_without_anomalies=sum(a.impact.total_expected_spend for a in anomalies),
            anomalies=anomalies,
            generated_at=datetime.now(),
        )


class MockForecastService:
    """Mock implementation of ForecastService."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    def get_aws_native_forecast(self, start: date, end: date) -> ForecastResult:
        """Generate a random forecast with confidence intervals."""
        predictions = []
        current = start
        base_cost = 200.0
        
        while current <= end:
            predicted = base_cost + random.uniform(-10, 25)
            predictions.append(
                ForecastPoint(
                    date=current,
                    predicted_cost=Decimal(f"{predicted:.2f}"),
                    lower_bound=Decimal(f"{predicted * 0.85:.2f}"),
                    upper_bound=Decimal(f"{predicted * 1.15:.2f}"),
                    confidence_level=0.95,
                )
            )
            current += timedelta(days=1)
            base_cost += 0.5
            
        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            metric=ForecastMetric.UNBLENDED_COST,
            granularity="DAILY",
            predictions=predictions,
            model_used=ForecastModel.AWS_NATIVE_ARIMA,
            accuracy_score=0.88,
        )


class MockReportService:
    """Mock implementation of ReportService for testing and demos."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    def generate_report(self, data: Any, config: Any = None) -> str | bytes:
        """Simulate report generation in various formats."""
        format_name = config.format.value if config and hasattr(config, "format") else "pdf"
        
        if format_name in ("pdf", "parquet"):
            return b"Mock binary content for " + format_name.encode()
        
        return f"Mock report content in {format_name} format"
