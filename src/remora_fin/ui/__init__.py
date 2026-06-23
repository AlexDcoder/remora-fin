"""UI package — Textual TUI for Remora FinOps.

This package provides the interactive terminal user interface for AWS FinOps
operations, including dashboards, cost analysis, anomaly detection, and forecasting.
"""

# Main application
from remora_fin.ui.app import RemoraApp

# Facade for UI services
from remora_fin.ui.facade import UIFacade

# Themes
from remora_fin.ui.styles.theme import (
    DARK_THEME,
    LIGHT_THEME,
    THEMES,
    get_theme_css,
)

# Widgets
from remora_fin.ui.widgets import (
    AnomalyDetailCard,
    AnomalyPanel,
    SeverityBadge,
    CostChartWidget,
    DashboardWidget,
    ForecastPanel,
    AccuracyMeter,
    ErrorBanner,
    KPICard,
)

__all__ = [
    # App
    "RemoraApp",
    # Facade
    "UIFacade",
    # Themes
    "DARK_THEME",
    "LIGHT_THEME",
    "THEMES",
    "get_theme_css",
    # Widgets
    "AnomalyDetailCard",
    "AnomalyPanel",
    "SeverityBadge",
    "CostChartWidget",
    "DashboardWidget",
    "ForecastPanel",
    "AccuracyMeter",
    "ErrorBanner",
    "KPICard",
]