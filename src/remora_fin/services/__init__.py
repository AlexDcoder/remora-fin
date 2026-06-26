"""Services package — business logic and AWS integration.

This package contains all service implementations for AWS FinOps operations.
"""

# ─── Infrastructure Services ───
# ─── Core Business Services ───
from remora_fin.services.anomaly_service import AnomalyService
from remora_fin.services.aws_service import AWSSession
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService
from remora_fin.services.config_service import ConfigBuilder, ConfigService
from remora_fin.services.cost_service import CostQueryBuilder, CostService
from remora_fin.services.dashboard_service import DashboardService
from remora_fin.services.forecast_service import ForecastService
from remora_fin.services.governance_service import GovernanceService
from remora_fin.services.inventory_service import InventoryService
from remora_fin.services.metrics_service import MetricsService
from remora_fin.services.pricing_service import PricingService
from remora_fin.services.report_service import ReportService
from remora_fin.services.unit_economics_service import UnitEconomicsService

__all__ = [
    # Infrastructure
    "AWSSession",
    # Domain Services
    "AnomalyService",
    "BaseService",
    "CacheService",
    "ConfigBuilder",
    "ConfigService",
    "CostQueryBuilder",
    "CostService",
    "DashboardService",
    "ForecastService",
    "GovernanceService",
    "InventoryService",
    "MetricsService",
    "PricingService",
    "ReportService",
    "UnitEconomicsService",
]

# Grouped exports for convenience
INFRASTRUCTURE_SERVICES = [
    AWSSession,
    BaseService,
    CacheService,
    ConfigBuilder,
    ConfigService,
]

CORE_SERVICES = [
    AnomalyService,
    CostQueryBuilder,
    CostService,
    DashboardService,
    ForecastService,
    GovernanceService,
    InventoryService,
    MetricsService,
    PricingService,
    ReportService,
    UnitEconomicsService,
]
