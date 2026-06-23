"""Remora FinOps TUI — Main application.

Design Patterns: Facade + Observer
"""

from __future__ import annotations

import logging
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    Select,
)

from remora_fin.services import AWSSession
from remora_fin.ui.facade import UIFacade
from remora_fin.ui.styles import get_theme_css
from remora_fin.ui.widgets import (
    AnomalyPanel, 
    CostChartWidget, 
    DashboardWidget, 
    ForecastPanel
)

logger = logging.getLogger(__name__)


class CostScreen(Screen[None]):
    """Screen for cost analysis."""

    DEFAULT_CSS = """
    CostScreen {
        padding: 1 2;
    }
    """

    def __init__(
        self,
        facade: UIFacade,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._facade = facade
        self._days = days

    def compose(self) -> ComposeResult:
        yield Label("[bold #00f3ff]» COST_ANALYSIS_SUBSYSTEM[/]", id="title")
        yield CostChartWidget("Cost Trend", id="cost-chart")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load cost data async via facade."""
        try:
            chart_points = await self._facade.get_cost_data(self._days)
            chart = self.query_one("#cost-chart", CostChartWidget)
            chart.show_daily_trend(chart_points)
        except Exception as e:
            self.notify(f"Error loading cost data: {e}", severity="error", markup=False)


class AnomalyScreen(Screen[None]):
    """Screen for anomaly detection."""

    def __init__(
        self,
        facade: UIFacade,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._facade = facade
        self._days = days

    def compose(self) -> ComposeResult:
        yield Label("[bold #4b86b4]» ANOMALY_DETECTION_MATRIX[/]", id="title")
        yield AnomalyPanel(id="anomaly-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load anomalies async via facade."""
        try:
            report = await self._facade.get_anomaly_report(self._days)
            panel = self.query_one("#anomaly-panel", AnomalyPanel)
            panel.update_report(report)
        except Exception as e:
            self.notify(f"Error loading anomalies: {e}", severity="error", markup=False)


class ForecastScreen(Screen[None]):
    """Screen for cost forecasting."""

    def __init__(
        self,
        facade: UIFacade,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._facade = facade
        self._days = days

    def compose(self) -> ComposeResult:
        yield Label("[bold #39ff14]» PREDICTIVE_COST_FORECAST[/]", id="title")
        yield ForecastPanel(id="forecast-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load forecast async via facade."""
        try:
            result = await self._facade.get_forecast_result(self._days)
            panel = self.query_one("#forecast-panel", ForecastPanel)
            panel.update_forecast(result)
        except Exception as e:
            self.notify(f"Error loading forecast: {e}", severity="error", markup=False)


class RemoraApp(App[None]):
    """Main application facade."""

    CSS = ""  # Set dynamically based on theme

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("r", "refresh", "Refresh Data"),
    ]

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str = "default",
        default_days: int = 30,
        theme: str = "dark",
    ) -> None:
        super().__init__()
        self._region = region
        self._profile = profile
        self._default_days = default_days
        self._theme = theme
        self._session: AWSSession | None = None
        self._facade: UIFacade | None = None

    def on_mount(self) -> None:
        # Set theme
        type(self).CSS = get_theme_css(self._theme)

        # Initialize AWS session and Facade
        self._session = AWSSession.get_instance(
            region=self._region,
            profile=self._profile,
        )
        self._facade = UIFacade(self._session)

        # Install screens for quick switching
        self.install_screen(DashboardScreen(self._facade, self._default_days), name="dashboard")
        self.push_screen("dashboard")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def action_show_costs(self) -> None:
        if self._facade:
            self.push_screen(CostScreen(self._facade, self._default_days))

    def action_show_anomalies(self) -> None:
        if self._facade:
            self.push_screen(AnomalyScreen(self._facade, self._default_days))

    def action_show_forecast(self) -> None:
        if self._facade:
            self.push_screen(ForecastScreen(self._facade, self._default_days))

    def action_show_dashboard(self) -> None:
        if self.screen.name != "dashboard":
            self.push_screen("dashboard")

    def action_refresh(self) -> None:
        """Trigger refresh on current screen if supported."""
        if hasattr(self.screen, "_refresh_data"):
            self.screen._refresh_data()
        elif hasattr(self.screen, "_load_data"):
            self.screen._load_data()
        self.notify("Data refreshed")


class DashboardScreen(Screen[None]):
    """Dashboard screen with KPI overview."""

    def __init__(
        self,
        facade: UIFacade,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._facade = facade
        self._days = days
        self._selected_service = "All Services"

    def compose(self) -> ComposeResult:
        yield Label("[bold #00f2ff]» REMORA_CORE_DASHBOARD[/]", id="title")
        yield DashboardWidget(
            default_days=self._days,
            id="dashboard",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_services()
        self._refresh_data()

    @work(exclusive=True)
    async def _load_services(self) -> None:
        """Fetch available services via facade."""
        try:
            services = await self._facade.get_available_services(self._days)
            options = [("All Services", "All Services")] + [(s, s) for s in services]

            selector = self.query_one("#service-selector", Select)
            selector.set_options(options)
            selector.refresh()
        except Exception as e:
            logger.error(f"Failed to load services: {e}")

    @work(exclusive=True)
    async def _refresh_data(self) -> None:
        """Refresh dashboard data via facade."""
        try:
            dashboard = self.query_one("#dashboard", DashboardWidget)
            data = await self._facade.get_dashboard_data(days=self._days, selected_service=self._selected_service)

            dashboard.update_kpis(
                total_cost=data.total_cost,
                daily_avg=data.daily_avg,
                anomaly_count=data.anomaly_count,
                inventory=data.inventory,
            )

            dashboard.update_status_header(data.status_title, data.status_subtitle)

            # Update Chart
            chart = self.query_one("#dashboard-chart", CostChartWidget)
            chart.show_daily_trend(data.chart_data)

            # Update Report Table
            dashboard.update_report_table(data.table_data)

        except Exception as e:
            logger.exception("Dashboard refresh failed")
            self.notify(f"Error refreshing dashboard: {e}", severity="error", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-toggle":
            dashboard = self.query_one("#dashboard", DashboardWidget)
            dashboard.toggle_view()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "service-selector":
            self._selected_service = str(event.value)
            self._refresh_data()
