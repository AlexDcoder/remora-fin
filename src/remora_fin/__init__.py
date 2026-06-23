"""Remora-Fin — High-performance AWS FinOps CLI and TUI.

A lightweight, high-performance FinOps toolkit for AWS built with Polars and Textual.
"""

__version__ = "1.0.6"

# Core exports for easy access
from remora_fin import commands, schemas, services, ui

# Infrastructure services (most commonly used)
from remora_fin.services import (
    AWSSession,
    CacheService,
    ConfigService,
    CostService,
    AnomalyService,
    ForecastService,
    DashboardService,
    GovernanceService,
    InventoryService,
    MetricsService,
    PricingService,
    ReportService,
    UnitEconomicsService,
)

# Schemas (most commonly used)
from remora_fin.schemas import (
    AppSettings,
    CostBreakdown,
    CostTrend,
    AnomalyReport,
    ForecastResult,
    FullReport,
    ReportConfig,
)

__all__ = [
    # Version
    "__version__",
    # Subpackages
    "commands",
    "schemas",
    "services",
    "ui",
    # Infrastructure Services
    "AWSSession",
    "CacheService",
    "ConfigService",
    "ConfigBuilder",
    # Core Services
    "CostService",
    "AnomalyService",
    "ForecastService",
    "DashboardService",
    "GovernanceService",
    "InventoryService",
    "MetricsService",
    "PricingService",
    "ReportService",
    "UnitEconomicsService",
    # Core Schemas
    "AppSettings",
    "CostBreakdown",
    "CostTrend",
    "AnomalyReport",
    "ForecastResult",
    "FullReport",
    "ReportConfig",
]