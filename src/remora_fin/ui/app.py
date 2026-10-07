"""Remora FinOps TUI — Main application.

Design Patterns: Facade + Observer
"""

from __future__ import annotations

import logging
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Label,
    Select,
)

from remora_fin.services import AWSSession
from remora_fin.ui.facade import UIFacade
from remora_fin.ui.styles import get_theme_css
from remora_fin.ui.widgets import CostChartWidget, DashboardWidget

logger = logging.getLogger(__name__)


class RemoraApp(App[None]):
    """Main application facade."""

    CSS = ""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [  # type: ignore[assignment]
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
        # Textual reads App.CSS during startup, before on_mount runs.
        object.__setattr__(self, "CSS", get_theme_css(theme))
        super().__init__()
        self._region = region
        self._profile = profile
        self._default_days = default_days
        self._theme = theme
        self._session: AWSSession | None = None
        self._facade: UIFacade | None = None

    def on_mount(self) -> None:
        # Initialize AWS session and Facade
        self._session = AWSSession.get_instance(
            region=self._region,
            profile=self._profile,
        )
        self._facade = UIFacade(self._session)

        # The TUI presents one full-width dashboard.
        self.install_screen(DashboardScreen(self._facade, self._default_days), name="dashboard")
        self.push_screen("dashboard")

    def action_refresh(self) -> None:
        """Refresh the dashboard."""
        if isinstance(self.screen, DashboardScreen):
            self.screen._refresh_data()
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
        yield Horizontal(
            Label("ROOT / SYSTEM / DASHBOARD", classes="breadcrumbs"),
            Label("SYS: SYNC", id="system-status", classes="status-pill warning"),
            Label("AWS: PENDING", id="aws-status", classes="status-pill warning"),
            Label("ALERTS: 00", id="alert-count", classes="status-pill accent"),
            classes="status-bar",
        )
        with Vertical(classes="page-heading"):
            yield Label("FINOPS_OVERVIEW", classes="page-title")
            yield Label("AWS cost intelligence / real-time operational view", classes="page-subtitle")
        yield DashboardWidget(
            default_days=self._days,
            id="dashboard",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_services()
        self._refresh_data()

    @work(exclusive=True, group="service-options")
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

    @work(exclusive=True, group="dashboard-refresh")
    async def _refresh_data(self) -> None:
        """Refresh dashboard data via facade."""
        self.query_one("#system-status", Label).update("SYS: SYNC")
        self.query_one("#system-status", Label).set_classes("status-pill warning")
        try:
            dashboard = self.query_one("#dashboard", DashboardWidget)
            data = await self._facade.get_dashboard_data(days=self._days, selected_service=self._selected_service)

            dashboard.update_kpis(
                total_cost=data.total_cost,
                daily_avg=data.daily_avg,
                anomaly_count=data.anomaly_count,
                inventory=data.inventory,
                estimated_savings=data.estimated_savings,
            )

            dashboard.update_status_header(data.status_title, data.status_subtitle)

            # Update Chart
            chart = self.query_one("#dashboard-chart", CostChartWidget)
            chart.show_daily_trend(data.chart_data)

            # Update Report Table
            dashboard.update_report_table(data.table_data)
            dashboard.update_recommendations(data.recommendation_data)
            self.query_one("#system-status", Label).update("SYS: OK")
            self.query_one("#system-status", Label).set_classes("status-pill okay")
            self.query_one("#aws-status", Label).update("AWS: OK")
            self.query_one("#aws-status", Label).set_classes("status-pill okay")
            self.query_one("#alert-count", Label).update(f"ALERTS: {data.anomaly_count:02d}")
            self.query_one("#alert-count", Label).set_classes(
                "status-pill warning" if data.anomaly_count else "status-pill accent"
            )
            dashboard.log_event("OKAY", f"{data.status_title} refreshed / {self._days} days")

        except Exception as e:
            logger.exception("Dashboard refresh failed")
            self.query_one("#system-status", Label).update("SYS: ERR")
            self.query_one("#system-status", Label).set_classes("status-pill error")
            self.query_one("#aws-status", Label).update("AWS: ERR")
            self.query_one("#aws-status", Label).set_classes("status-pill error")
            self.query_one("#dashboard", DashboardWidget).log_event("ERR", "Dashboard refresh failed")
            self.notify(f"Error refreshing dashboard: {e}", severity="error", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-toggle":
            dashboard = self.query_one("#dashboard", DashboardWidget)
            dashboard.toggle_view()
        elif event.button.id == "recommendations-toggle":
            dashboard = self.query_one("#dashboard", DashboardWidget)
            dashboard.show_recommendations()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "service-selector":
            self._selected_service = str(event.value)
            self.query_one("#dashboard", DashboardWidget).log_event("INFO", f"Service filter: {self._selected_service}")
            self._refresh_data()
