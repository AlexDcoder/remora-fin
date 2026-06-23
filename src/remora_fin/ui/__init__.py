"""UI package — Textual TUI for Remora FinOps.

This package provides the interactive terminal user interface for AWS FinOps
operations, including dashboards, cost analysis, anomaly detection, and forecasting.
"""

# ─── Main Application ───
from remora_fin.ui.app import RemoraApp

# ─── Facade ───
from remora_fin.ui.facade import UIFacade

# ─── Themes ───
from remora_fin.ui.styles.theme import (
    DARK_THEME,
    LIGHT_THEME,
    THEMES,
    get_theme_css,
)

# ─── Widgets ───
from remora_fin.ui.widgets import (
    # Forecast
    AccuracyMeter,
    # Anomaly
    AnomalyDetailCard,
    AnomalyPanel,
    # Chart
    CostChartWidget,
    # Dashboard
    DashboardWidget,
    # Common
    ErrorBanner,
    ForecastPanel,
    KPICard,
    SeverityBadge,
)

__all__ = [
    # Themes
    "DARK_THEME",
    "LIGHT_THEME",
    "THEMES",
    # Widgets
    "AccuracyMeter",
    "AnomalyDetailCard",
    "AnomalyPanel",
    "CostChartWidget",
    "DashboardWidget",
    "ErrorBanner",
    "ForecastPanel",
    "KPICard",
    # App
    "RemoraApp",
    "SeverityBadge",
    # Facade
    "UIFacade",
    "get_theme_css",
]
