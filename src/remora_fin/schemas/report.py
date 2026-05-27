"""Report schemas — export configuration and metadata."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from remora_fin.schemas.anomaly import AnomalyReport
from remora_fin.schemas.common import DateRange
from remora_fin.schemas.cost import CostBreakdown, CostTrend
from remora_fin.schemas.forecast import ForecastResult


class ReportFormat(StrEnum):
    """Output format for reports."""

    PDF = "pdf"
    TABLE = "table"
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    MARKDOWN = "markdown"


class ReportFilters(BaseModel):
    """Filters to apply when generating reports."""

    model_config = ConfigDict(frozen=True)

    services: list[str] | None = None
    accounts: list[str] | None = None
    regions: list[str] | None = None
    tags: dict[str, str] | None = None
    min_cost: float | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0)


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    model_config = ConfigDict(frozen=True)

    format: ReportFormat = ReportFormat.PDF
    include_charts: bool = False
    output_path: Path | None = None
    filters: ReportFilters = Field(default_factory=ReportFilters)
    currency: str = "USD"
    group_by: str | None = None  # SERVICE, LINKED_ACCOUNT, REGION, etc.


class ReportMetadata(BaseModel):
    """Metadata attached to generated reports."""

    model_config = ConfigDict(frozen=True)

    generated_at: datetime = Field(default_factory=datetime.now)
    generated_by: str | None = None  # IAM User/Role
    account_id: str | None = None
    period: DateRange
    filters_applied: ReportFilters = Field(default_factory=ReportFilters)
    version: str = "0.1.0"
    data_source: str = "AWS Cost Explorer API"


class FullReport(BaseModel):
    """A comprehensive report containing all analysis types."""

    cost_breakdown: CostBreakdown | None = None
    cost_trend: CostTrend | None = None
    anomalies: AnomalyReport | None = None
    forecast: ForecastResult | None = None


# Ensure all forward refs are resolved
FullReport.model_rebuild()
