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

from remora.services.aws_service import AWSSession, paginate_all, retry_with_backoff
from remora.services.cost_service import CostService, CostQueryBuilder
from remora.services.anomaly_service import AnomalyService, AnomalyClassifierChain
from remora.services.forecast_service import (
    ForecastService,
    ForecastStrategy,
    AWSCostExplorerNativeForecast,
    LinearRegressionForecast,
    MovingAverageForecast,
)
from remora.services.report_service import (
    ReportService,
    ReportFormatter,
    TableFormatter,
    JsonFormatter,
    CsvFormatter,
    MarkdownFormatter,
)
from remora.services.config_service import ConfigService, ConfigBuilder

__all__ = [
    # AWS
    "AWSSession",
    "paginate_all",
    "retry_with_backoff",
    # Cost
    "CostService",
    "CostQueryBuilder",
    # Anomaly
    "AnomalyService",
    "AnomalyClassifierChain",
    # Forecast
    "ForecastService",
    "ForecastStrategy",
    "AWSCostExplorerNativeForecast",
    "LinearRegressionForecast",
    "MovingAverageForecast",
    # Report
    "ReportService",
    "ReportFormatter",
    "TableFormatter",
    "JsonFormatter",
    "CsvFormatter",
    "MarkdownFormatter",
    # Config
    "ConfigService",
    "ConfigBuilder",
]
