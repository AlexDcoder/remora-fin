"""Services package — Business logic and AWS integrations.

Service modules:
    aws_service      → AWS session management (Singleton + Factory)
    cost_service     → Cost Explorer queries (Repository + Builder)
    anomaly_service  → Anomaly detection (Repository + Chain of Responsibility)
    forecast_service → Cost forecasting (Strategy pattern)
    report_service   → Multi-format export (Strategy + Template Method)
    config_service   → App configuration (Singleton + Builder)
"""

from __future__ import annotations

from remora.services.anomaly_service import AnomalyClassifierChain, AnomalyService
from remora.services.aws_service import AWSSession, paginate_all, retry_with_backoff
from remora.services.config_service import ConfigBuilder, ConfigService
from remora.services.cost_service import CostQueryBuilder, CostService
from remora.services.forecast_service import (
    AWSCostExplorerNativeForecast,
    ForecastService,
    ForecastStrategy,
    LinearRegressionForecast,
    MovingAverageForecast,
)
from remora.services.report_service import (
    CsvFormatter,
    JsonFormatter,
    MarkdownFormatter,
    ReportFormatter,
    ReportService,
    TableFormatter,
)

__all__ = [
    "AWSCostExplorerNativeForecast",
    # AWS
    "AWSSession",
    "AnomalyClassifierChain",
    # Anomaly
    "AnomalyService",
    "ConfigBuilder",
    # Config
    "ConfigService",
    "CostQueryBuilder",
    # Cost
    "CostService",
    "CsvFormatter",
    # Forecast
    "ForecastService",
    "ForecastStrategy",
    "JsonFormatter",
    "LinearRegressionForecast",
    "MarkdownFormatter",
    "MovingAverageForecast",
    "ReportFormatter",
    # Report
    "ReportService",
    "TableFormatter",
    "paginate_all",
    "retry_with_backoff",
]
