"""Schemas package — Pydantic models for AWS FinOps data structures.

This package contains all data models used throughout the application,
including cost, anomaly, forecast, metrics, pricing, and configuration schemas.
"""

# Common schemas
from remora_fin.schemas.common import DateRange, DateRangeInput, Money, Percent

# AWS schemas
from remora_fin.schemas.aws import AWSCallerIdentity

# Configuration schemas
from remora_fin.schemas.config import AppSettings, AWSConfig, CacheConfig, UIConfig

# Cost schemas
from remora_fin.schemas.cost import (
    CostBreakdown,
    CostEntry,
    CostGroup,
    CostSummary,
    CostTrend,
    CostTrendPoint,
)

# Anomaly schemas
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

# Forecast schemas
from remora_fin.schemas.forecast import (
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)

# Metrics schemas
from remora_fin.schemas.metrics import MetricSummary, ResourceMetric

# Pricing schemas
from remora_fin.schemas.pricing import AWSPrice, PricingDetail, ProductAttributes

# Report schemas
from remora_fin.schemas.report import (
    FullReport,
    ReportConfig,
    ReportFilters,
    ReportFormat,
    ReportMetadata,
)

__all__ = [
    # Common
    "DateRange",
    "DateRangeInput",
    "Money",
    "Percent",
    # AWS
    "AWSCallerIdentity",
    # Config
    "AppSettings",
    "AWSConfig",
    "CacheConfig",
    "UIConfig",
    # Cost
    "CostBreakdown",
    "CostEntry",
    "CostGroup",
    "CostSummary",
    "CostTrend",
    "CostTrendPoint",
    # Anomaly
    "Anomaly",
    "AnomalyFeedback",
    "AnomalyImpact",
    "AnomalyReport",
    "AnomalyRootCause",
    "AnomalyScore",
    "AnomalySeverity",
    "AnomalyType",
    # Forecast
    "ForecastComparison",
    "ForecastMetric",
    "ForecastModel",
    "ForecastPoint",
    "ForecastResult",
    "VarianceAnalysis",
    # Metrics
    "MetricSummary",
    "ResourceMetric",
    # Pricing
    "AWSPrice",
    "PricingDetail",
    "ProductAttributes",
    # Report
    "FullReport",
    "ReportConfig",
    "ReportFilters",
    "ReportFormat",
    "ReportMetadata",
]