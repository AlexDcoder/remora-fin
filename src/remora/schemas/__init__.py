"""Schemas package — Pydantic models for all data transfer objects.

Organized by domain:
    common   → shared types (DateRange, Money, Percent)
    aws      → AWS infrastructure (credentials, accounts, services, regions)
    cost     → Cost Explorer data (entries, summaries, breakdowns, trends)
    anomaly  → Anomaly detection (severity, types, root causes, reports)
    forecast → Cost forecasting (metrics, points, results, variance analysis)
    report   → Report export (formats, filters, config, metadata)
    config   → Application settings (AWS, cache, UI, AppSettings)
"""

from __future__ import annotations

from remora.schemas.anomaly import (
    Anomaly,
    AnomalyFeedback,
    AnomalyImpact,
    AnomalyReport,
    AnomalyRootCause,
    AnomalyScore,
    AnomalySeverity,
    AnomalyType,
)
from remora.schemas.aws import AWSAccount, AWSCallerIdentity, AWSCredentials, AWSRegion, AWSService
from remora.schemas.common import DateRange, DateRangeInput, Money, Percent
from remora.schemas.config import (
    AppSettings,
    AWSConfig,
    CacheConfig,
    UIConfig,
)
from remora.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)
from remora.schemas.forecast import (
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)
from remora.schemas.report import (
    ReportConfig,
    ReportFilters,
    ReportFormat,
    ReportMetadata,
)

__all__ = [
    "AWSAccount",
    "AWSCallerIdentity",
    # config
    "AWSConfig",
    # aws
    "AWSCredentials",
    "AWSRegion",
    "AWSService",
    "Anomaly",
    "AnomalyFeedback",
    "AnomalyImpact",
    "AnomalyReport",
    "AnomalyRootCause",
    "AnomalyScore",
    # anomaly
    "AnomalySeverity",
    "AnomalyType",
    "AppSettings",
    "CacheConfig",
    "CostBreakdown",
    # cost
    "CostEntry",
    "CostGroup",
    "CostSummary",
    "CostTrend",
    "CostTrendPoint",
    # common
    "DateRange",
    "DateRangeInput",
    "ForecastComparison",
    # forecast
    "ForecastMetric",
    "ForecastModel",
    "ForecastPoint",
    "ForecastResult",
    "Money",
    "Percent",
    "ReportConfig",
    "ReportFilters",
    # report
    "ReportFormat",
    "ReportMetadata",
    "UIConfig",
    "VarianceAnalysis",
]
