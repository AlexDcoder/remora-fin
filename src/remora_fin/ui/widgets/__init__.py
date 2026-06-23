"""UI Widgets — Reusable Textual components for the Remora-Fin TUI.

This package contains all custom Textual widgets used in the Remora-Fin interface,
organized by functionality and reusability.
"""

# Anomaly widgets
from remora_fin.ui.widgets.anomaly_panel import (
    AnomalyDetailCard,
    AnomalyPanel,
    SeverityBadge,
)

# Chart widgets
from remora_fin.ui.widgets.cost_chart import CostChartWidget

# Dashboard widgets
from remora_fin.ui.widgets.dashboard import DashboardWidget

# Forecast widgets
from remora_fin.ui.widgets.forecast_panel import (
    AccuracyMeter,
    ForecastPanel,
)

# Common widgets
from remora_fin.ui.widgets.common.widgets import (
    ErrorBanner,
    KPICard,
)

__all__ = [
    # Anomaly
    "AnomalyDetailCard",
    "AnomalyPanel",
    "SeverityBadge",
    # Chart
    "CostChartWidget",
    # Dashboard
    "DashboardWidget",
    # Forecast
    "AccuracyMeter",
    "ForecastPanel",
    # Common
    "ErrorBanner",
    "KPICard",
]