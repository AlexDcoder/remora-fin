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
from remora_fin.services.aws_service import AWSSession, paginate_all, retry_with_backoff
from remora_fin.services.cloudfront_service import CloudFrontService
from remora_fin.services.config_service import ConfigBuilder, ConfigService
from remora_fin.services.cost_service import CostQueryBuilder, CostService
from remora_fin.services.dynamodb_service import DynamoDBService
from remora_fin.services.ec2_service import EC2Service
from remora_fin.services.forecast_service import (
    AWSCostExplorerNativeForecast,
    ForecastService,
    ForecastStrategy,
    LinearRegressionForecast,
    MovingAverageForecast,
)
from remora_fin.services.lambda_service import LambdaService
from remora_fin.services.rds_service import RDSService
from remora_fin.services.report_service import (
    JsonFormatter,
    MarkdownFormatter,
    PDFFormatter,
    ReportFormatter,
    ReportService,
    TableFormatter,
)
from remora_fin.services.s3_service import S3Service

__all__ = [
    "AWSCostExplorerNativeForecast",
    "AWSSession",
    "AnomalyService",
    "CloudFrontService",
    "ConfigBuilder",
    "ConfigService",
    "CostQueryBuilder",
    "CostService",
    "DynamoDBService",
    "EC2Service",
    "ForecastService",
    "ForecastStrategy",
    "JsonFormatter",
    "LambdaService",
    "LinearRegressionForecast",
    "MarkdownFormatter",
    "MovingAverageForecast",
    "PDFFormatter",
    "RDSService",
    "ReportFormatter",
    "ReportService",
    "S3Service",
    "TableFormatter",
    "paginate_all",
    "retry_with_backoff",
]
