"""Dashboard widget — consolidated FinOps overview."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, ContentSwitcher, DataTable, Select

from remora_fin.ui.widgets.common.widgets import KPICard
from remora_fin.ui.widgets.cost_chart import CostChartWidget


class DashboardWidget(Container):
    """Consolidated dashboard showing key FinOps metrics.

    Uses ContentSwitcher for high-performance view toggling.
    """

    DEFAULT_CSS = """
    DashboardWidget {
        layout: vertical;
        padding: 1 2;
        background: #06060e;
    }
    #control-row {
        height: auto;
        margin-bottom: 1;
        align: center middle;
        border: tall #00f3ff;
        background: #0a1931;
        padding: 0 1;
    }
    #service-selector {
        width: 1fr;
        border: none;
    }
    #view-toggle {
        width: auto;
        margin-left: 2;
        min-width: 25;
        border: tall #00f2ff;
    }
    #kpi-row {
        height: 6;
        margin: 1 0;
    }
    #chart-row {
        height: 18;
        margin: 1 0;
    }
    #dashboard-content-switcher {
        height: 1fr;
    }
    #dashboard-report-table {
        height: 1fr;
        border: tall #00f2ff;
    }
    #dashboard-chart {
        height: 1fr;
    }
    """

    def __init__(
        self,
        total_cost: str = "$0.00",
        daily_avg: str = "$0.00",
        anomaly_count: int = 0,
        forecast_trend: str = "—",
        default_days: int = 30,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._total_cost = total_cost
        self._daily_avg = daily_avg
        self._anomaly_count = anomaly_count
        self._forecast_trend = forecast_trend
        self._default_days = default_days
        self._view_mode = "dashboard"

    def compose(self) -> ComposeResult:
        # Controls
        yield Horizontal(
            Select(
                [(s, s) for s in ["All Services"]],
                value="All Services",
                id="service-selector",
                prompt="Select AWS Service",
            ),
            Button("Switch to Report", id="view-toggle", variant="primary"),
            id="control-row",
        )

        # KPI Row
        yield Horizontal(
            KPICard("Total Spend", self._total_cost, id="kpi-total"),
            KPICard("Daily Average", self._daily_avg, id="kpi-avg"),
            KPICard(
                "Anomalies",
                str(self._anomaly_count),
                variant="warning" if self._anomaly_count > 5 else "normal",
                id="kpi-anomalies",
            ),
            KPICard(
                "Forecast",
                self._forecast_trend,
                variant=("danger" if "↑" in self._forecast_trend else "normal"),
                id="kpi-forecast",
            ),
            id="kpi-row",
        )

        # Content Area with ContentSwitcher for better performance
        with ContentSwitcher(id="dashboard-content-switcher", initial="dashboard-chart"):
            yield CostChartWidget("Cost Trend", id="dashboard-chart")
            yield DataTable(id="dashboard-report-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        """Initialize table columns once."""
        table = self.query_one("#dashboard-report-table", DataTable)
        table.add_columns("Date", "Service", "Cost")

    def update_kpis(
        self,
        total_cost: str | None = None,
        daily_avg: str | None = None,
        anomaly_count: int | None = None,
        forecast_trend: str | None = None,
    ) -> None:
        """Update KPI cards with new data."""
        if total_cost is not None:
            self.query_one("#kpi-total", KPICard).update_value(total_cost)
        if daily_avg is not None:
            self.query_one("#kpi-avg", KPICard).update_value(daily_avg)
        if anomaly_count is not None:
            self.query_one("#kpi-anomalies", KPICard).update_value(
                str(anomaly_count), variant="warning" if anomaly_count > 5 else "normal"
            )
        if forecast_trend is not None:
            self.query_one("#kpi-forecast", KPICard).update_value(
                forecast_trend, variant=("danger" if "↑" in forecast_trend else "normal")
            )

    def toggle_view(self) -> None:
        """Toggle between chart and report table using ContentSwitcher."""
        switcher = self.query_one("#dashboard-content-switcher", ContentSwitcher)
        btn = self.query_one("#view-toggle", Button)

        if self._view_mode == "dashboard":
            self._view_mode = "report"
            switcher.current = "dashboard-report-table"
            btn.label = "Switch to Dashboard"
            btn.variant = "default"
        else:
            self._view_mode = "dashboard"
            switcher.current = "dashboard-chart"
            btn.label = "Switch to Report"
            btn.variant = "primary"

    def update_report_table(self, data: list[tuple[str, str, str]]) -> None:
        """Update the report table efficiently without re-adding columns."""
        table = self.query_one("#dashboard-report-table", DataTable)
        table.clear()
        table.add_rows(data)
