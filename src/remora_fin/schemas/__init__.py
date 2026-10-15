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
from remora_fin.schemas.finops import (
    Alert,
    AlertStatus,
    AllocationEntry,
    Budget,
    BudgetCheck,
    BudgetScope,
    BudgetStatus,
    HistorySnapshot,
    RecommendationRecord,
    RecommendationState,
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
from remora_fin.schemas.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationConfidence,
    RecommendationSeverity,
    RecommendationSummary,
)

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
    "Alert",
    "AlertStatus",
    "AllocationEntry",
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
    "Budget",
    "BudgetCheck",
    "BudgetScope",
    "BudgetStatus",
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
    "HistorySnapshot",
    # Metrics
    "MetricSummary",
    "Money",
    "Percent",
    "PricingDetail",
    "ProductAttributes",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationConfidence",
    "RecommendationRecord",
    "RecommendationSeverity",
    "RecommendationState",
    "RecommendationSummary",
    "ReportConfig",
    "ReportFilters",
    "ReportFormat",
    "ReportMetadata",
    "ResourceMetric",
    "UIConfig",
    "VarianceAnalysis",
]
