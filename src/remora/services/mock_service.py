"""Mock services for UI testing and demo mode."""

from __future__ import annotations

import random
from datetime import date, timedelta, datetime
from decimal import Decimal

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
from remora.schemas.cost import CostTrend, CostTrendPoint, CostSummary
from remora.schemas.forecast import ForecastPoint, ForecastResult, ForecastModel, ForecastMetric
from remora.schemas.common import DateRange


class MockCostService:
    """Mock implementation of CostService."""

    def __init__(self, session: any = None) -> None:
        self._session = session

    def get_daily_trend(self, start: date, end: date) -> CostTrend:
        """Generate a random cost trend."""
        points = []
        current = start
        base_cost = 100.0
        
        while current <= end:
            # Add some randomness and a slight upward trend
            daily_cost = base_cost + random.uniform(-10, 20)
            points.append(
                CostTrendPoint(
                    date=current,
                    cost=Decimal(f"{daily_cost:.2f}"),
                    usage=Decimal(f"{daily_cost * 1.5:.2f}"),
                )
            )
            current += timedelta(days=1)
            base_cost += 0.5
            
        return CostTrend(
            period=DateRange(start=start, end=end),
            granularity="DAILY",
            metric="UnblendedCost",
            points=points,
        )

    def get_total_cost(self, start: date, end: date) -> CostSummary:
        """Generate a random cost summary."""
        trend = self.get_daily_trend(start, end)
        total = sum(p.cost for p in trend.points)
        avg = total / len(trend.points) if trend.points else Decimal("0")
        
        return CostSummary(
            total_cost=total,
            daily_average=avg,
            max_daily_cost=max(p.cost for p in trend.points),
            min_daily_cost=min(p.cost for p in trend.points),
            top_service="AmazonEC2",
            num_services=12,
            num_accounts=3,
        )


class MockAnomalyService:
    """Mock implementation of AnomalyService."""

    def __init__(self, session: any = None) -> None:
        self._session = session

    def get_anomaly_summary(self, start: date, end: date) -> AnomalyReport:
        """Generate random anomalies."""
        anomalies = []
        services = ["AmazonEC2", "AmazonS3", "AmazonRDS", "Lambda", "DynamoDB"]
        
        for i in range(3):
            service = random.choice(services)
            actual = random.uniform(500, 1000)
            expected = random.uniform(100, 200)
            variance = ((actual - expected) / expected) * 100
            severity = AnomalySeverity.from_percentage(variance)
            
            anomalies.append(
                Anomaly(
                    id=f"anomaly-{i}",
                    monitor_arn="arn:aws:ce:us-east-1:123456789012:monitor/test",
                    start_date=date.today() - timedelta(days=random.randint(1, 10)),
                    dimension_value=service,
                    root_causes=[
                        AnomalyRootCause(
                            service=service,
                            contribution=Decimal(f"{actual - expected:.2f}")
                        )
                    ],
                    score=AnomalyScore(max_score=80.0, current_score=75.0),
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
            by_severity={a.severity: 1 for a in anomalies},
            by_type={AnomalyType.SPIKE: len(anomalies)},
            total_actual_impact=sum(a.impact.total_actual_spend for a in anomalies),
            total_expected_without_anomalies=sum(a.impact.total_expected_spend for a in anomalies),
            anomalies=anomalies,
            generated_at=datetime.now(),
        )


class MockForecastService:
    """Mock implementation of ForecastService."""

    def __init__(self, session: any = None) -> None:
        self._session = session

    def get_aws_native_forecast(self, start: date, end: date) -> ForecastResult:
        """Generate a random forecast."""
        predictions = []
        current = start
        base_cost = 120.0
        
        while current <= end:
            predicted = base_cost + random.uniform(-5, 15)
            predictions.append(
                ForecastPoint(
                    date=current,
                    predicted_cost=Decimal(f"{predicted:.2f}"),
                    lower_bound=Decimal(f"{predicted * 0.9:.2f}"),
                    upper_bound=Decimal(f"{predicted * 1.1:.2f}"),
                    confidence_level=0.95,
                )
            )
            current += timedelta(days=1)
            base_cost += 0.3
            
        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            metric=ForecastMetric.UNBLENDED_COST,
            granularity="DAILY",
            predictions=predictions,
            model_used=ForecastModel.AWS_NATIVE_ARIMA,
            accuracy_score=0.92,
        )
