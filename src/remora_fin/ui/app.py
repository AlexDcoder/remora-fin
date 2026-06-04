"""Remora FinOps TUI — Main application.

Design Patterns: Facade + Observer
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
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

from remora_fin.services import (
    AnomalyService,
    CloudFrontService,
    CostService,
    DashboardService,
    DynamoDBService,
    EC2Service,
    ElastiCacheService,
    EMRService,
    ForecastService,
    KMSService,
    LambdaService,
    RDSService,
    RedshiftService,
    S3Service,
    SageMakerService,
    SecretsManagerService,
    SNSService,
    SQSService,
)
from remora_fin.services.aws_service import AWSSession
from remora_fin.ui.styles.theme import get_theme_css
from remora_fin.ui.widgets.anomaly_panel import AnomalyPanel
from remora_fin.ui.widgets.cost_chart import CostChartWidget
from remora_fin.ui.widgets.dashboard import DashboardWidget
from remora_fin.ui.widgets.forecast_panel import ForecastPanel

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
        session: AWSSession | None,
        days: int = 30,
    ) -> None:
        super().__init__()
        self._session = session
        self._days = days
        self._cost_service = CostService(session)

    def compose(self) -> ComposeResult:
        yield Label("[bold #00f3ff]» COST_ANALYSIS_SUBSYSTEM[/]", id="title")
        yield CostChartWidget("Cost Trend", id="cost-chart")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load cost data async."""
        end = date.today()
        start = end - timedelta(days=self._days)

        try:
            trend = await self._cost_service.get_daily_trend_async(start, end)
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
        yield Label("[bold #4b86b4]» ANOMALY_DETECTION_MATRIX[/]", id="title")
        yield AnomalyPanel(id="anomaly-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load anomalies async."""
        end = date.today()
        start = end - timedelta(days=min(self._days, 90))

        try:
            report = await self._anomaly_service.get_anomaly_summary_async(start, end)
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
        yield Label("[bold #39ff14]» PREDICTIVE_COST_FORECAST[/]", id="title")
        yield ForecastPanel(id="forecast-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(exclusive=True)
    async def _load_data(self) -> None:
        """Load forecast async."""
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=self._days)

        try:
            result = await self._forecast_service.get_aws_native_forecast_async(
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
        self._dashboard_service = DashboardService(session) if session else None

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
        """Fetch available services async and merge with integrated ones."""
        if not self._cost_service:
            return

        end = date.today()
        start = end - timedelta(days=self._days)
        region = self._session.region if self._session else None

        try:
            # Detect services from cost breakdown (filtered by region)
            breakdown = await self._cost_service.get_cost_by_service_async(start, end, region=region)
            cost_services = {g.key for g in breakdown.groups if g.key} if breakdown else set()

            # Ensure our integrated services are always available
            integrated_services = {
                "CloudFront",
                "DynamoDB",
                "EC2",
                "ElastiCache",
                "EMR",
                "KMS",
                "Lambda",
                "RDS",
                "Redshift",
                "S3",
                "SageMaker",
                "SecretsManager",
                "SNS",
                "SQS",
            }

            # Combine, sort and update selector
            all_services = sorted(list(cost_services | integrated_services))
            services = ["All Services", *all_services]

            # Fix: Use direct property update for options as per Textual 0.x Select API
            selector = self.query_one("#service-selector", Select)
            selector.options = [(s, s) for s in services]
            selector.refresh()
        except Exception as e:
            logger.error(f"Failed to load services: {e}")

    @work(exclusive=True)
    async def _refresh_data(self) -> None:
        """Load and update all dashboard components in parallel with resilience."""
        import asyncio

        if not self._dashboard_service:
            return

        region = self._session.region if self._session else None

        try:
            dashboard = self.query_one("#dashboard", DashboardWidget)

            if self._selected_service == "All Services":
                # Use the new high-performance DashboardService
                data = await self._dashboard_service.get_summary_parallel(days=self._days, region=region)

                summary = data.get("cost_summary")
                trend = data.get("cost_trend")
                anomalies = data.get("anomalies")
                infra_counts = data.get("infrastructure", {}).get("counts", {})

                # Resilient KPI formatting
                total_cost_str = f"${summary.total_cost:,.2f}" if summary else "$0.00"
                daily_avg_str = f"${summary.daily_average:,.2f}" if summary else "$0.00"
                anomaly_count = anomalies.total_anomalies if anomalies else 0
                total_resources = sum(infra_counts.values()) if infra_counts else 0

                dashboard.update_kpis(
                    total_cost=total_cost_str,
                    daily_avg=daily_avg_str,
                    anomaly_count=anomaly_count,
                    inventory=f"{total_resources} Res",
                )

                dashboard.update_status_header(f"Region: {region or 'Global'}", "Comprehensive Monitoring")

                # Update Chart
                chart = self.query_one("#dashboard-chart", CostChartWidget)
                chart.show_daily_trend([(str(p.date), float(p.cost)) for p in trend.points] if trend else [])

                # Update Report Table
                end = date.today()
                start = end - timedelta(days=self._days)

                table_data = []
                if self._cost_service:
                    breakdown = await self._cost_service.get_cost_by_service_async(start, end, region=region)
                    table_data = [("•", g.key, f"${g.cost:,.2f}") for g in breakdown.groups[:50]] if breakdown else []
                dashboard.update_report_table(table_data)

            else:
                # Handle single service view
                if not self._cost_service or not self._session:
                    return

                end = date.today()
                start = end - timedelta(days=self._days)

                tasks = [
                    self._cost_service.get_cost_by_service_async(start, end, region=region),
                    self._cost_service.get_daily_trend_async(start, end, region=region),
                ]

                # Map UI names to internal inventory tasks
                inventory_task = None
                svc = self._selected_service
                if "EC2" in svc:
                    inventory_task = EC2Service(self._session).list_instances_async()
                elif "RDS" in svc:
                    inventory_task = RDSService(self._session).list_db_instances_async()
                elif "S3" in svc:
                    inventory_task = S3Service(self._session).list_buckets_async()
                elif "Lambda" in svc:
                    inventory_task = LambdaService(self._session).list_functions_async()
                elif "SNS" in svc:
                    inventory_task = SNSService(self._session).list_topics_async()
                elif "SQS" in svc:
                    inventory_task = SQSService(self._session).list_queues_async()
                elif "DynamoDB" in svc:
                    inventory_task = DynamoDBService(self._session).list_tables_async()
                elif "CloudFront" in svc:
                    inventory_task = CloudFrontService(self._session).list_distributions_async()
                elif "ElastiCache" in svc:
                    inventory_task = ElastiCacheService(self._session).list_clusters_async()
                elif "Redshift" in svc:
                    inventory_task = RedshiftService(self._session).list_clusters_async()
                elif "EMR" in svc:
                    inventory_task = EMRService(self._session).list_clusters_async()
                elif "SageMaker" in svc:
                    inventory_task = SageMakerService(self._session).list_notebook_instances_async()
                elif "KMS" in svc:
                    inventory_task = KMSService(self._session).list_keys_async()
                elif "SecretsManager" in svc:
                    inventory_task = SecretsManagerService(self._session).list_secrets_async()

                if inventory_task:
                    tasks.append(inventory_task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                from remora_fin.schemas.cost import CostBreakdown, CostTrend

                svc_breakdown = results[0] if isinstance(results[0], CostBreakdown) else None
                results[1] if isinstance(results[1], CostTrend) else None
                inventory_data = results[2] if len(results) > 2 and not isinstance(results[2], BaseException) else None

                # Find specific service cost with partial matching
                service_group = None
                if svc_breakdown:
                    service_group = next((g for g in svc_breakdown.groups if self._selected_service in g.key), None)

                display_total = service_group.cost if service_group else Decimal("0")
                display_avg = display_total / self._days

                inventory_str = f"{len(inventory_data)} Res" if isinstance(inventory_data, list) else "—"

                dashboard.update_kpis(
                    total_cost=f"${display_total:,.2f}",
                    daily_avg=f"${display_avg:,.2f}",
                    inventory=inventory_str,
                )

                # Update Status Header with context
                svc_contexts = {
                    "EC2": "Server Fleet & Instances",
                    "RDS": "Relational Database Clusters",
                    "S3": "Object Storage Buckets",
                    "Lambda": "Serverless Function Matrix",
                    "DynamoDB": "NoSQL Table Performance",
                    "SageMaker": "ML Models & Notebooks",
                    "CloudFront": "Edge Content Delivery",
                    "ElastiCache": "In-Memory Cache Clusters",
                    "Redshift": "Data Warehouse Clusters",
                    "EMR": "Big Data Analysis",
                    "SNS": "Pub/Sub Messaging Topics",
                    "SQS": "Message Queue Latency",
                }
                context = "AWS Service Analysis"
                for key, ctx in svc_contexts.items():
                    if key in self._selected_service:
                        context = ctx
                        break

                dashboard.update_status_header(self._selected_service, context)

                # Filter entries for specific service for chart
                chart_points = []
                if svc_breakdown:
                    service_entries = [e for e in svc_breakdown.entries if self._selected_service in e.service]
                    daily_map: dict[str, float] = {}
                    for e in service_entries:
                        daily_map[str(e.date)] = daily_map.get(str(e.date), 0.0) + float(e.unblended_cost)
                    chart_points = sorted(daily_map.items())

                chart = self.query_one("#dashboard-chart", CostChartWidget)
                chart.show_daily_trend(chart_points)

                # Update table with service-specific entries
                table_data = []
                if svc_breakdown:
                    service_entries = sorted(
                        [e for e in svc_breakdown.entries if self._selected_service in e.service],
                        key=lambda x: x.date,
                        reverse=True,
                    )
                    table_data = [(str(e.date), e.service, f"${e.unblended_cost:,.2f}") for e in service_entries[:100]]

                dashboard.update_report_table(table_data)

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
