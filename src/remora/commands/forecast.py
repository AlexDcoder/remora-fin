"""Forecast command — Predict future AWS costs."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

import rich_argparse
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora.commands.utils import validate_aws_session
from remora.schemas.common import DateRange
from remora.schemas.forecast import ForecastMetric
from remora.schemas.report import ReportConfig, ReportFormat, ReportMetadata
from remora.services import AWSSession, ForecastService, ReportService

logger = logging.getLogger(__name__)


def forecast_cmd(args: argparse.Namespace) -> None:

    """Predict future AWS costs."""
    # Parse forecast period (forecast usually starts tomorrow)
    default_start = date.today() + timedelta(days=1)

    start = date.fromisoformat(args.start) if args.start else default_start

    if args.days:
        end = start + timedelta(days=args.days)
    elif args.end:
        end = date.fromisoformat(args.end)
    else:
        end = start + timedelta(days=30)

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )

    # Pre-flight check
    if not validate_aws_session(session):
        logger.error("AWS session validation failed")
        return

    forecast_service = ForecastService(session)
    report_service = ReportService()
    console = Console()

    # Fetch data
    with Status("[bold magenta]Calculating forecast...", console=console) as status:
        logger.info("Period: [green]%s[/] to [green]%s[/]", start, end)
        result = forecast_service.get_forecast(
            start=start,
            end=end,
            metric=ForecastMetric(args.metric),
            granularity=args.granularity,
            group_by_type=args.group_by_type,
            group_by_key=args.group_by_key,
        )

        status.update("[bold magenta]Formatting results...")

        # Prepare metadata
        identity = session.get_caller_identity()
        metadata = ReportMetadata(
            period=DateRange(start=start, end=end),
            generated_by=identity.get("arn"),
            account_id=identity.get("account"),
        )

    # Output
    if args.json:
        config = ReportConfig(format=ReportFormat.JSON)
        print(report_service.generate_report(result, config, metadata))
    else:
        config = ReportConfig(format=ReportFormat.TABLE)
        print(report_service.generate_report(result, config, metadata))

    # Scenario analysis if requested (kept as extra CLI output)
    if args.scenarios and not args.json:
        from rich.table import Table

        print()
        variations = {
            "optimistic": -0.10,
            "baseline": 0.0,
            "pessimistic": 0.15,
        }
        scenarios = forecast_service.scenario_analysis(result, variations)

        scenario_table = Table(
            show_lines=True,
            header_style="bold magenta",
            title="Forecast Scenario Analysis",
            title_style="bold cyan"
        )
        scenario_table.add_column("Scenario", style="cyan")
        scenario_table.add_column("Total Cost", justify="right", style="green")
        scenario_table.add_column("vs Baseline", justify="right", style="yellow")

        baseline_total = result.total_predicted_cost
        for name, scenario_result in scenarios.items():
            total = scenario_result.total_predicted_cost
            diff = float((total - baseline_total) / baseline_total * 100) if baseline_total > 0 else 0
            scenario_table.add_row(
                name.capitalize(),
                f"${total:,.2f}",
                f"{diff:+.1f}%",
            )
        print(scenario_table)

    summary_panel = Panel(
        f"Total Predicted: [bold green]${result.total_predicted_cost:,.2f}[/]\n"
        f"Model Used:     [cyan]{result.model_used.value}[/]",
        title="REMORA | Forecast Engine",
        border_style="magenta",
        expand=False
    )
    console.print(summary_panel)



def add_forecast_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add forecast subparser."""
    parser = subparsers.add_parser(
        "forecast",
        help="Forecast future AWS costs",
        description="[bold magenta]Predict future AWS costs using ML-based forecasting.[/]",
        formatter_class=rich_argparse.RichHelpFormatter,
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Number of days to forecast (default: 30, max 365)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Forecast start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--metric",
        choices=[
            "UnblendedCost",
            "BlendedCost",
            "NetUnblendedCost",
            "AmortizedCost",
            "UsageQuantity",
        ],
        default="UnblendedCost",
        help="Cost metric to forecast (default: UnblendedCost)",
    )
    parser.add_argument(
        "--granularity",
        choices=["DAILY", "MONTHLY"],
        default="DAILY",
        help="Forecast granularity (default: DAILY)",
    )
    parser.add_argument(
        "--group-by-type",
        choices=["DIMENSION", "TAG", "COST_CATEGORY"],
        default=None,
        help="Group forecast by type",
    )
    parser.add_argument(
        "--group-by-key",
        choices=[
            "SERVICE",
            "LINKED_ACCOUNT",
            "REGION",
            "USAGE_TYPE",
            "INSTANCE_TYPE",
            "PLATFORM",
        ],
        default=None,
        help="Group forecast by key",
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Show what-if scenario analysis",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=None,
        help="AWS profile name",
    )
    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region",
    )
    parser.set_defaults(func=forecast_cmd)
