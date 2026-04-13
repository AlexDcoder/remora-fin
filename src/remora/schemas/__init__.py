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

from remora.schemas.common import DateRange, DateRangeInput, Money, Percent
from remora.schemas.aws import AWSCredentials, AWSAccount, AWSService, AWSRegion, AWSCallerIdentity
from remora.schemas.cost import (
    CostEntry,
    CostSummary,
    CostGroup,
    CostBreakdown,
    CostTrendPoint,
    CostTrend,
)
from remora.schemas.anomaly import (
    AnomalySeverity,
    AnomalyType,
    AnomalyFeedback,
    AnomalyRootCause,
    AnomalyScore,
    AnomalyImpact,
    Anomaly,
    AnomalyReport,
)
from remora.schemas.forecast import (
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
    ForecastComparison,
)
from remora.schemas.report import (
    ReportFormat,
    ReportFilters,
    ReportConfig,
    ReportMetadata,
)
from remora.schemas.config import (
    AWSConfig,
    CacheConfig,
    UIConfig,
    AppSettings,
)

__all__ = [
    # common
    "DateRange",
    "DateRangeInput",
    "Money",
    "Percent",
    # aws
    "AWSCredentials",
    "AWSAccount",
    "AWSService",
    "AWSRegion",
    "AWSCallerIdentity",
    # cost
    "CostEntry",
    "CostSummary",
    "CostGroup",
    "CostBreakdown",
    "CostTrendPoint",
    "CostTrend",
    # anomaly
    "AnomalySeverity",
    "AnomalyType",
    "AnomalyFeedback",
    "AnomalyRootCause",
    "AnomalyScore",
    "AnomalyImpact",
    "Anomaly",
    "AnomalyReport",
    # forecast
    "ForecastMetric",
    "ForecastModel",
    "ForecastPoint",
    "ForecastResult",
    "VarianceAnalysis",
    "ForecastComparison",
    # report
    "ReportFormat",
    "ReportFilters",
    "ReportConfig",
    "ReportMetadata",
    # config
    "AWSConfig",
    "CacheConfig",
    "UIConfig",
    "AppSettings",
]
