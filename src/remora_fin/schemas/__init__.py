"""Schemas package — Pydantic models for AWS FinOps data structures.

This package contains all data models used throughout the application,
including cost, anomaly, forecast, metrics, pricing, and configuration schemas.
"""

# ─── Common ───
# ─── Anomaly ───
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

# ─── AWS ───
from remora_fin.schemas.aws import AWSCallerIdentity
from remora_fin.schemas.common import DateRange, DateRangeInput, Money, Percent

# ─── Configuration ───
from remora_fin.schemas.config import AppSettings, AWSConfig, CacheConfig, UIConfig

# ─── Cost ───
from remora_fin.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)

# ─── Forecast ───
from remora_fin.schemas.forecast import (
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)

# ─── Metrics ───
from remora_fin.schemas.metrics import MetricSummary, ResourceMetric

# ─── Pricing ───
from remora_fin.schemas.pricing import AWSPrice, PricingDetail, ProductAttributes

# ─── Report ───
from remora_fin.schemas.report import (
    FullReport,
    ReportConfig,
    ReportFilters,
    ReportFormat,
    ReportMetadata,
)

__all__ = [
    # AWS
    "AWSCallerIdentity",
    "AWSConfig",
    # Pricing
    "AWSPrice",
    # Anomaly
    "Anomaly",
    "AnomalyFeedback",
    "AnomalyImpact",
    "AnomalyReport",
    "AnomalyRootCause",
    "AnomalyScore",
    "AnomalySeverity",
    "AnomalyType",
    # Config
    "AppSettings",
    "CacheConfig",
    # Cost
    "CostBreakdown",
    "CostEntry",
    "CostGroup",
    "CostSummary",
    "CostTrend",
    "CostTrendPoint",
    # Common
    "DateRange",
    "DateRangeInput",
    # Forecast
    "ForecastComparison",
    "ForecastMetric",
    "ForecastModel",
    "ForecastPoint",
    "ForecastResult",
    # Report
    "FullReport",
    # Metrics
    "MetricSummary",
    "Money",
    "Percent",
    "PricingDetail",
    "ProductAttributes",
    "ReportConfig",
    "ReportFilters",
    "ReportFormat",
    "ReportMetadata",
    "ResourceMetric",
    "UIConfig",
    "VarianceAnalysis",
]
