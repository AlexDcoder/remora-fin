"""UI Widgets — Reusable Textual components for the Remora-Fin TUI.

This package contains all custom Textual widgets used in the Remora-Fin interface.
"""

# ─── Anomaly Widgets ───
from remora_fin.ui.widgets.anomaly_panel import AnomalyDetailCard, AnomalyPanel, SeverityBadge

# ─── Common Widgets ───
from remora_fin.ui.widgets.common.widgets import ErrorBanner, KPICard

# ─── Chart Widgets ───
from remora_fin.ui.widgets.cost_chart import CostChartWidget

# ─── Dashboard Widgets ───
from remora_fin.ui.widgets.dashboard import DashboardWidget

# ─── Forecast Widgets ───
from remora_fin.ui.widgets.forecast_panel import AccuracyMeter, ForecastPanel

__all__ = [
    # Forecast
    "AccuracyMeter",
    # Anomaly
    "AnomalyDetailCard",
    "AnomalyPanel",
    # Chart
    "CostChartWidget",
    # Dashboard
    "DashboardWidget",
    # Common
    "ErrorBanner",
    "ForecastPanel",
    "KPICard",
    "SeverityBadge",
]
