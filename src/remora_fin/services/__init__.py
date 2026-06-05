"""Services package — Business logic and AWS integrations.

Service modules:
    aws_service      → AWS session management (Singleton + Factory)
    cost_service     → Cost Explorer queries (Repository + Builder)
    anomaly_service  → Anomaly detection (Repository + Chain of Responsibility)
    forecast_service → Cost forecasting (Strategy pattern)
    report_service   → Multi-format export (Strategy + Template Method)
    config_service   → App configuration (Singleton + Builder)
    ec2_service      → EC2 metadata and management
"""

from __future__ import annotations

from remora_fin.services.anomaly_service import AnomalyService
from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, paginate_all, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.config_service import ConfigBuilder, ConfigService
from remora_fin.services.cost_service import CostQueryBuilder, CostService
from remora_fin.services.dashboard_service import DashboardService
from remora_fin.services.forecast_service import (
    AWSCostExplorerNativeForecast,
    ForecastService,
    ForecastStrategy,
    LinearRegressionForecast,
    MovingAverageForecast,
)
from remora_fin.services.governance_service import GovernanceService
from remora_fin.services.inventory_service import InventoryService
from remora_fin.services.report_service import (
    ExcelFormatter,
    MarkdownFormatter,
    PDFFormatter,
    ReportFormatter,
    ReportService,
)

__all__ = [
    "AWSCostExplorerNativeForecast",
    "AWSSession",
    "AnomalyService",
    "BaseService",
    "ConfigBuilder",
    "ConfigService",
    "CostQueryBuilder",
    "CostService",
    "DashboardService",
    "ExcelFormatter",
    "ForecastService",
    "ForecastStrategy",
    "GovernanceService",
    "InventoryService",
    "LinearRegressionForecast",
    "MarkdownFormatter",
    "MovingAverageForecast",
    "PDFFormatter",
    "ReportFormatter",
    "ReportService",
    "async_retry_with_backoff",
    "paginate_all",
    "retry_with_backoff",
]
