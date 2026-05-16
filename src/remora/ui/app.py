"""Remora FinOps TUI — Main application.

Design Patterns: Facade + Observer
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar

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

from remora.services import (
    AnomalyService,
    CostService,
    ForecastService,
)
from remora.services.aws_service import AWSSession
from remora.ui.styles.theme import get_theme_css
from remora.ui.widgets.anomaly_panel import AnomalyPanel
from remora.ui.widgets.cost_chart import CostChartWidget
from remora.ui.widgets.dashboard import DashboardWidget
from remora.ui.widgets.forecast_panel import ForecastPanel


class CostScreen(Screen[None]):
    """Screen for cost analysis."""

    DEFAULT_CSS = """
    CostScreen {
        padding: 1 2;
    }
    """

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._cost_service = CostService(session)

    def compose(self) -> ComposeResult:
        yield Label("[bold]Cost Analysis[/]", id="title")
        yield CostChartWidget("Cost Trend", id="cost-chart")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        """Load cost data."""
        end = date.today()
        start = end - timedelta(days=self._days)

        try:
            trend = self._cost_service.get_daily_trend(start, end)

            # Update chart
            chart = self.query_one("#cost-chart", CostChartWidget)
            chart.show_daily_trend([(str(p.date), float(p.cost)) for p in trend.points])

        except Exception as e:
            self.notify(f"Error loading cost data: {e}", severity="error", markup=False)


class AnomalyScreen(Screen[None]):
    """Screen for anomaly detection."""

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._anomaly_service = AnomalyService(session)

    def compose(self) -> ComposeResult:
        yield Label("[bold]Anomaly Detection[/]", id="title")
        yield AnomalyPanel(id="anomaly-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        end = date.today()
        start = end - timedelta(days=min(self._days, 90))

        try:
            report = self._anomaly_service.get_anomaly_summary(start, end)
            panel = self.query_one("#anomaly-panel", AnomalyPanel)
            panel.update_report(report)
        except Exception as e:
            self.notify(f"Error loading anomalies: {e}", severity="error", markup=False)


class ForecastScreen(Screen[None]):
    """Screen for cost forecasting."""

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._forecast_service = ForecastService(session)

    def compose(self) -> ComposeResult:
        yield Label("[bold]Cost Forecast[/]", id="title")
        yield ForecastPanel(id="forecast-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=self._days)

        try:
            result = self._forecast_service.get_aws_native_forecast(
                start=start,
                end=end,
            )
            panel = self.query_one("#forecast-panel", ForecastPanel)
            panel.update_forecast(result)
        except Exception as e:
            self.notify(f"Error loading forecast: {e}", severity="error", markup=False)


class RemoraApp(App[None]):
    """Main application facade."""

    CSS = ""  # Set dynamically based on theme

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
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
        self._screens_loaded: dict[str, Screen[None]] = {}

    def on_mount(self) -> None:
        # Set theme
        type(self).CSS = get_theme_css(self._theme)

        # Initialize AWS session
        self._session = AWSSession.get_instance(
            region=self._region,
            profile=self._profile,
        )

        # Install screens for quick switching
        self.install_screen(DashboardScreen(self._session, self._default_days), name="dashboard")
        self.push_screen("dashboard")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def action_show_costs(self) -> None:
        self.push_screen(CostScreen(self._session, self._default_days))

    def action_show_anomalies(self) -> None:
        self.push_screen(AnomalyScreen(self._session, self._default_days))

    def action_show_forecast(self) -> None:
        self.push_screen(ForecastScreen(self._session, self._default_days))

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
        session: AWSSession | None,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._selected_service = "All Services"
        self._cost_service = CostService(session) if session else None
        self._anomaly_service = AnomalyService(session) if session else None

    def compose(self) -> ComposeResult:
        yield Label("[bold]Remora FinOps Dashboard[/]", id="title")
        yield DashboardWidget(
            default_days=self._days,
            id="dashboard",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_services()
        self._refresh_data()

    def _load_services(self) -> None:
        """Fetch available services to populate selector."""
        if not self._cost_service:
            return

        end = date.today()
        start = end - timedelta(days=self._days)

        try:
            breakdown = self._cost_service.get_cost_by_service(start, end)
            services = ["All Services", *sorted([g.key for g in breakdown.groups if g.key])]

            selector = self.query_one("#service-selector", Select)
            selector.set_options([(s, s) for s in services])
        except Exception:
            pass

    def _refresh_data(self) -> None:
        """Load and update all dashboard components."""
        if not self._cost_service:
            return

        end = date.today()
        start = end - timedelta(days=self._days)

        try:
            # 1. Update KPIs
            summary = self._cost_service.get_total_cost(start, end)

            # If a specific service is selected, we should ideally filter the summary
            # For now, let's just get the breakdown and filter manually if needed
            breakdown = self._cost_service.get_cost_by_service(start, end)

            anomalies = 0
            if self._anomaly_service:
                anomaly_report = self._anomaly_service.get_anomaly_summary(start, end)
                anomalies = anomaly_report.total_anomalies

            dashboard = self.query_one("#dashboard", DashboardWidget)

            # Calculate metrics based on selection
            if self._selected_service == "All Services":
                display_total = summary.total_cost
                display_avg = summary.daily_average
            else:
                # Find the specific service in groups
                service_group = next((g for g in breakdown.groups if g.key == self._selected_service), None)
                display_total = service_group.cost if service_group else Decimal("0")
                display_avg = display_total / self._days

            dashboard.update_kpis(
                total_cost=f"${display_total:,.2f}",
                daily_avg=f"${display_avg:,.2f}",
                anomaly_count=anomalies,
                forecast_trend="—",
            )

            # 2. Update Chart
            chart = self.query_one("#dashboard-chart", CostChartWidget)
            # If service filtered, we need trend for that service specifically

            if self._selected_service == "All Services":
                trend = self._cost_service.get_daily_trend(start, end)
                chart_data = [(str(p.date), float(p.cost)) for p in trend.points]
            else:
                # Filter entries for the specific service
                service_entries = [e for e in breakdown.entries if e.service == self._selected_service]
                # Group by date
                daily_data: dict[str, float] = {}
                for e in service_entries:
                    daily_data[str(e.date)] = daily_data.get(str(e.date), 0.0) + float(e.unblended_cost)
                chart_data = sorted(daily_data.items())

            chart.show_daily_trend(chart_data)

            # 3. Update Report Table
            table_data = []
            if self._selected_service == "All Services":
                # Show top services
                for g in breakdown.groups[:50]:
                    table_data.append(("-", g.key, f"${g.cost:,.2f}"))
            else:
                # Show daily breakdown for that service
                service_entries = sorted(
                    [e for e in breakdown.entries if e.service == self._selected_service],
                    key=lambda x: x.date,
                    reverse=True,
                )
                for e in service_entries:
                    table_data.append((str(e.date), e.service, f"${e.unblended_cost:,.2f}"))

            dashboard.update_report_table(table_data)

        except Exception as e:
            self.notify(f"Error refreshing dashboard: {e}", severity="error", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-toggle":
            dashboard = self.query_one("#dashboard", DashboardWidget)
            dashboard.toggle_view()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "service-selector":
            self._selected_service = str(event.value)
            self._refresh_data()
