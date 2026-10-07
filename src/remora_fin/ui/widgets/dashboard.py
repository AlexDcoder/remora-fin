"""Dashboard widget — consolidated FinOps overview."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, DataTable, Label, RichLog, Select

from remora_fin.ui.widgets.common.widgets import KPICard
from remora_fin.ui.widgets.cost_chart import CostChartWidget


class DashboardWidget(Container):
    """Consolidated dashboard showing key FinOps metrics."""

    SUPPORTED_SERVICES: ClassVar[list[str]] = [
        "All Services",
        "EC2",
        "S3",
        "RDS",
        "Lambda",
        "DynamoDB",
        "CloudFront",
        "ElastiCache",
        "Redshift",
        "EMR",
        "SageMaker",
        "KMS",
        "SecretsManager",
        "SNS",
        "SQS",
        "ECS",
        "EKS",
    ]

    def __init__(
        self,
        total_cost: str = "$0.00",
        daily_avg: str = "$0.00",
        anomaly_count: int = 0,
        forecast_trend: str = "—",
        default_days: int = 30,
        estimated_savings: str = "$0.00/mo",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._total_cost = total_cost
        self._daily_avg = daily_avg
        self._anomaly_count = anomaly_count
        self._forecast_trend = forecast_trend
        self._default_days = default_days
        self._estimated_savings = estimated_savings
        self._view_mode = "dashboard"

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("SERVICE_FILTER", id="filter-label"),
            Select(
                [(s, s) for s in self.SUPPORTED_SERVICES],
                value="All Services",
                allow_blank=False,
                id="service-selector",
                prompt="Select AWS Service",
            ),
            Button("VIEW REPORT", id="view-toggle", classes="primary-action"),
            Button("ACTION CENTER", id="recommendations-toggle", classes="secondary-action"),
            id="control-row",
            classes="panel",
        )

        yield Horizontal(
            KPICard("Total Spend", self._total_cost, index="01", id="kpi-total"),
            KPICard("Daily Average", self._daily_avg, index="02", id="kpi-avg"),
            KPICard(
                "Anomalies",
                str(self._anomaly_count),
                variant="warning" if self._anomaly_count > 5 else "normal",
                index="03",
                id="kpi-anomalies",
            ),
            KPICard("Inventory", "—", index="04", id="kpi-inventory"),
            KPICard("Est. Savings", self._estimated_savings, index="05", id="kpi-savings"),
            id="kpi-row",
        )

        yield Label("RESOURCE_MONITOR / GLOBAL  ·  Comprehensive Monitoring", id="service-status-header")

        with ContentSwitcher(id="dashboard-content-switcher", initial="dashboard-chart"):
            yield CostChartWidget("Daily Cost Trend", id="dashboard-chart", classes="panel")
            yield DataTable(
                id="dashboard-report-table",
                zebra_stripes=False,
                cursor_type="row",
                cursor_background_priority="css",
            )
            yield DataTable(
                id="dashboard-recommendations-table",
                zebra_stripes=False,
                cursor_type="row",
                cursor_background_priority="css",
            )

        with Vertical(classes="log-panel"):
            yield Label("ACTIVITY_LOG", classes="log-heading")
            yield RichLog(id="activity-log", classes="log-stream", markup=False, highlight=False)

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-report-table", DataTable)
        table.add_columns("Date", "Service", "Cost")
        recommendations = self.query_one("#dashboard-recommendations-table", DataTable)
        recommendations.add_columns("Service", "Severity", "Resource", "Recommendation")
        self.log_event("INFO", "Waiting for AWS cost data")

    def log_event(self, level: str, message: str) -> None:
        """Append a compact, colored operational event to the dashboard."""
        colors = {"INFO": "#9296f5", "OKAY": "#00e676", "WARN": "#ffb300", "ERR": "#ff5252"}
        line = Text()
        line.append(datetime.now().strftime("%H:%M:%S"), style="#6e7681")
        line.append(f"  [{level}]", style=f"bold {colors.get(level, '#a0a8b6')}")
        line.append(f"  {message}", style="#a0a8b6")
        self.query_one("#activity-log", RichLog).write(line)

    def update_kpis(
        self,
        total_cost: str | None = None,
        daily_avg: str | None = None,
        anomaly_count: int | None = None,
        inventory: str | None = None,
        estimated_savings: str | None = None,
    ) -> None:
        if total_cost is not None:
            self.query_one("#kpi-total", KPICard).update_value(total_cost)
        if daily_avg is not None:
            self.query_one("#kpi-avg", KPICard).update_value(daily_avg)
        if anomaly_count is not None:
            self.query_one("#kpi-anomalies", KPICard).update_value(
                str(anomaly_count), variant="warning" if anomaly_count > 5 else "normal"
            )
        if inventory is not None:
            self.query_one("#kpi-inventory", KPICard).update_value(inventory)
        if estimated_savings is not None:
            self.query_one("#kpi-savings", KPICard).update_value(estimated_savings)

    def update_status_header(self, service_name: str, context: str) -> None:
        header = self.query_one("#service-status-header", Label)
        header.update(f"RESOURCE_MONITOR / {service_name.upper()}  ·  {context}")

    def toggle_view(self) -> None:
        switcher = self.query_one("#dashboard-content-switcher", ContentSwitcher)
        btn = self.query_one("#view-toggle", Button)

        if self._view_mode == "dashboard":
            self._view_mode = "report"
            switcher.current = "dashboard-report-table"
            btn.label = "VIEW DASHBOARD"
            btn.remove_class("primary-action")
            btn.add_class("secondary-action")
            self.log_event("INFO", "Report view opened")
        else:
            self._view_mode = "dashboard"
            switcher.current = "dashboard-chart"
            btn.label = "VIEW REPORT"
            btn.remove_class("secondary-action")
            btn.add_class("primary-action")
            self.log_event("INFO", "Monitor view opened")

    def update_report_table(self, data: list[tuple[str, str, str]]) -> None:
        table = self.query_one("#dashboard-report-table", DataTable)
        table.clear()
        table.add_rows(data)

    def show_recommendations(self) -> None:
        """Open the ranked, read-only action center."""
        switcher = self.query_one("#dashboard-content-switcher", ContentSwitcher)
        switcher.current = "dashboard-recommendations-table"
        self._view_mode = "recommendations"
        self.log_event("INFO", "Recommendation action center opened")

    def update_recommendations(self, data: list[tuple[str, str, str, str]]) -> None:
        table = self.query_one("#dashboard-recommendations-table", DataTable)
        table.clear()
        table.add_rows(data)
