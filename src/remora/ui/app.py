"""Remora FinOps TUI — Main application.

Design Patterns: Facade + Observer
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Label,
)

from remora.services import (
    AnomalyService,
    CostService,
    ForecastService,
)
from remora.services.mock_service import (
    MockAnomalyService,
    MockCostService,
    MockForecastService,
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
        use_mock: bool = False,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        if use_mock:
            self._cost_service = MockCostService(session)
        else:
            self._cost_service = CostService(session)  # type: ignore[arg-type]

    def compose(self) -> ComposeResult:
        yield Label("[bold]💰 Cost Analysis[/]", id="title")
        yield CostChartWidget("Cost Trend", id="cost-chart")

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
            self.notify(f"Error loading cost data: {e}", severity="error")


class AnomalyScreen(Screen[None]):
    """Screen for anomaly detection."""

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
        use_mock: bool = False,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        if use_mock:
            self._anomaly_service = MockAnomalyService(session)
        else:
            self._anomaly_service = AnomalyService(session)  # type: ignore[arg-type]

    def compose(self) -> ComposeResult:
        yield Label("[bold]🔍 Anomaly Detection[/]", id="title")
        yield AnomalyPanel(id="anomaly-panel")  # type: ignore[call-arg]

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
            self.notify(f"Error loading anomalies: {e}", severity="error")


class ForecastScreen(Screen[None]):
    """Screen for cost forecasting."""

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
        use_mock: bool = False,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        if use_mock:
            self._forecast_service = MockForecastService(session)
        else:
            self._forecast_service = ForecastService(session)  # type: ignore[arg-type]

    def compose(self) -> ComposeResult:
        yield Label("[bold]📈 Cost Forecast[/]", id="title")
        yield ForecastPanel(id="forecast-panel")  # type: ignore[call-arg]

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
            self.notify(f"Error loading forecast: {e}", severity="error")


class RemoraApp(App[None]):
    """Main Remora FinOps TUI application."""

    CSS = ""  # Set dynamically based on theme

    BINDINGS: ClassVar[Sequence[tuple[str, str, str]]] = [  # type: ignore[assignment]
        ("q", "quit", "Quit"),
        ("1", "show_costs", "💰 Costs"),
        ("2", "show_anomalies", "🔍 Anomalies"),
        ("3", "show_forecast", "📈 Forecast"),
        ("d", "show_dashboard", "📊 Dashboard"),
    ]

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str = "default",
        default_days: int = 30,
        theme: str = "dark",
        use_mock: bool = False,
    ) -> None:
        super().__init__()
        self._region = region
        self._profile = profile
        self._default_days = default_days
        self._theme = theme
        self._use_mock = use_mock
        self._session: AWSSession | None = None
        self._screens_loaded: dict[str, Screen[None]] = {}

    def on_mount(self) -> None:
        # Set theme
        self.CSS = get_theme_css(self._theme)  # type: ignore[misc]

        # Initialize AWS session if not in mock mode
        if not self._use_mock:
            self._session = AWSSession.get_instance(
                region=self._region,
                profile=self._profile,
            )

        # Install and start on dashboard
        self.install_screen(
            DashboardScreen(self._session, self._default_days, use_mock=self._use_mock),
            name="dashboard"
        )
        self.push_screen("dashboard")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def action_show_costs(self) -> None:
        self.push_screen(CostScreen(self._session, self._default_days, use_mock=self._use_mock))

    def action_show_anomalies(self) -> None:
        self.push_screen(AnomalyScreen(self._session, self._default_days, use_mock=self._use_mock))

    def action_show_forecast(self) -> None:
        self.push_screen(ForecastScreen(self._session, self._default_days, use_mock=self._use_mock))

    def action_show_dashboard(self) -> None:
        self.push_screen(DashboardScreen(self._session, self._default_days, use_mock=self._use_mock))


class DashboardScreen(Screen[None]):
    """Dashboard screen with KPI overview."""

    def __init__(
        self,
        session: AWSSession | None,
        days: int = 30,
        use_mock: bool = False,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._use_mock = use_mock
        if use_mock:
            self._cost_service = MockCostService(session)
        else:
            self._cost_service = CostService(session) if session else None

    def compose(self) -> ComposeResult:
        yield Label("[bold]📊 Remora FinOps Dashboard[/]", id="title")
        yield DashboardWidget(  # type: ignore[call-arg]
            default_days=self._days,
            id="dashboard",
        )

    def on_mount(self) -> None:
        self._load_kpis()

    def _load_kpis(self) -> None:
        if not self._cost_service:
            return

        end = date.today()
        start = end - timedelta(days=self._days)

        try:
            summary = self._cost_service.get_total_cost(start, end)
            dashboard = self.query_one("#dashboard", DashboardWidget)
            dashboard.update_kpis(
                total_cost=f"${summary.total_cost:,.2f}",
                daily_avg=f"${summary.daily_average:,.2f}",
                forecast_trend="—",
            )
            
            # Update chart too
            chart = self.query_one("#dashboard-chart", CostChartWidget)
            trend = self._cost_service.get_daily_trend(start, end)
            chart.show_daily_trend([(str(p.date), float(p.cost)) for p in trend.points])
            
        except Exception:
            pass
