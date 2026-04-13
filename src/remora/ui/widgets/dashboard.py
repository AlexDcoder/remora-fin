"""Dashboard widget — consolidated FinOps overview."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal

from remora.ui.widgets.common.widgets import KPICard
from remora.ui.widgets.cost_chart import CostChartWidget


class DashboardWidget(Container):
    """Consolidated dashboard showing key FinOps metrics.

    Design Pattern: Composite — aggregates multiple sub-widgets.
    """

    DEFAULT_CSS = """
    DashboardWidget {
        layout: vertical;
        padding: 1 2;
    }
    #kpi-row {
        height: 5;
    }
    #chart-row {
        height: 15;
        margin: 1 0;
    }
    """

    def __init__(
        self,
        total_cost: str = "$0.00",
        daily_avg: str = "$0.00",
        anomaly_count: int = 0,
        forecast_trend: str = "—",
        default_days: int = 30,
    ) -> None:
        super().__init__()
        self._total_cost = total_cost
        self._daily_avg = daily_avg
        self._anomaly_count = anomaly_count
        self._forecast_trend = forecast_trend
        self._default_days = default_days

    def compose(self) -> ComposeResult:
        # KPI Row
        yield Horizontal(
            KPICard("Total Spend", self._total_cost),
            KPICard("Daily Average", self._daily_avg),
            KPICard(
                "Anomalies",
                str(self._anomaly_count),
                variant="warning" if self._anomaly_count > 5 else "normal",
            ),
            KPICard(
                "Forecast",
                self._forecast_trend,
                variant=("danger" if "↑" in self._forecast_trend else "normal"),
            ),
            id="kpi-row",
        )

        # Chart placeholder
        yield CostChartWidget("30-Day Cost Trend", id="dashboard-chart")  # type: ignore[call-arg]

    def update_kpis(
        self,
        total_cost: str | None = None,
        daily_avg: str | None = None,
        anomaly_count: int | None = None,
        forecast_trend: str | None = None,
    ) -> None:
        """Update KPI cards with new data."""
        if total_cost is not None:
            self._total_cost = total_cost
        if daily_avg is not None:
            self._daily_avg = daily_avg
        if anomaly_count is not None:
            self._anomaly_count = anomaly_count
        if forecast_trend is not None:
            self._forecast_trend = forecast_trend

    def refresh_all(self) -> None:
        """Full refresh of all dashboard data."""
        # This would be called when new data arrives from services
        # Triggers recomputation of all KPIs and chart
        pass
