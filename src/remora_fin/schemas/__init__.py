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

from remora_fin.schemas.anomaly import (
    Anomaly,
    AnomalyFeedback,
    AnomalyImpact,
    AnomalyReport,
    AnomalyRootCause,
    AnomalyScore,
    AnomalySeverity,
    AnomalyType,
)
from remora_fin.schemas.aws import AWSCallerIdentity
from remora_fin.schemas.common import DateRange, DateRangeInput, Money, Percent
from remora_fin.schemas.config import (
    AppSettings,
    AWSConfig,
    CacheConfig,
    UIConfig,
)
from remora_fin.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)
from remora_fin.schemas.forecast import (
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)
from remora_fin.schemas.report import (
    ReportConfig,
    ReportFilters,
    ReportFormat,
    ReportMetadata,
)

__all__ = [
    "AWSCallerIdentity",
    "AWSConfig",
    "Anomaly",
    "AnomalyFeedback",
    "AnomalyImpact",
    "AnomalyReport",
    "AnomalyRootCause",
    "AnomalyScore",
    "AnomalySeverity",
    "AnomalyType",
    "AppSettings",
    "CacheConfig",
    "CostBreakdown",
    "CostEntry",
    "CostGroup",
    "CostSummary",
    "CostTrend",
    "CostTrendPoint",
    "DateRange",
    "DateRangeInput",
    "ForecastComparison",
    "ForecastMetric",
    "ForecastModel",
    "ForecastPoint",
    "ForecastResult",
    "Money",
    "Percent",
    "ReportConfig",
    "ReportFilters",
    "ReportFormat",
    "ReportMetadata",
    "UIConfig",
    "VarianceAnalysis",
]
