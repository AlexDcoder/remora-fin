"""Forecast command — Predict future AWS costs."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora_fin.commands.utils import validate_aws_session
from remora_fin.schemas.forecast import ForecastMetric
from remora_fin.services import AWSSession, ForecastService
from remora_fin.services.config_service import ConfigService

logger = logging.getLogger(__name__)


async def forecast_cmd(args: argparse.Namespace) -> None:
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

    config_service = ConfigService()
    settings = config_service.settings

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or settings.aws.region,
        profile=args.profile or settings.aws.profile,
    )

    # Pre-flight check
    if not validate_aws_session(session):
        logger.error("AWS session validation failed")
        return

    forecast_service = ForecastService(session)
    console = Console()

    # Fetch data
    with Status("[bold #39ff14]Calculating forecast...", console=console) as status:
        logger.info("Period: [#39ff14]%s[/] to [#39ff14]%s[/]", start, end)
        # Use async version if it's native ARIMA, fallback to sync otherwise
        try:
            result = await forecast_service.get_aws_native_forecast_async(
                start=start,
                end=end,
                metric=ForecastMetric(args.metric),
                granularity=args.granularity,
            )
        except Exception as e:
            logger.warning("AWS native async forecast failed, using sync fallback: %s", e)
            result = forecast_service.get_forecast(
                start=start,
                end=end,
                metric=ForecastMetric(args.metric),
                granularity=args.granularity,
                group_by_type=args.group_by_type,
                group_by_key=args.group_by_key,
            )

        status.update("[bold #4b86b4]Formatting results...")

    # Output
    from rich.table import Table

    result_table = Table(
        title=f"[bold #39ff14]Forecasted Spend ({start} to {end})[/]",
        header_style="bold #00f3ff",
        border_style="#4b86b4",
    )
    result_table.add_column("Date", style="dim")
    result_table.add_column("Predicted Cost (USD)", justify="right", style="bold #39ff14")

    for p in result.predictions[:15]:  # Show first 15 days
        result_table.add_row(str(p.date), f"${p.predicted_cost:,.2f}")

    if len(result.predictions) > 15:
        result_table.add_row("...", "...")

    console.print(result_table)

    # Scenario analysis if requested
    if args.scenarios:
        console.print()
        variations = {
            "optimistic": -0.10,
            "baseline": 0.0,
            "pessimistic": 0.15,
        }
        scenarios = forecast_service.scenario_analysis(result, variations)

        scenario_table = Table(
            show_lines=True,
            header_style="bold #00f3ff",
            title="[bold #39ff14]» FORECAST SCENARIO ANALYSIS[/]",
            border_style="#4b86b4",
        )
        scenario_table.add_column("Scenario", style="#e6f4f8")
        scenario_table.add_column("Total Cost", justify="right", style="bold #39ff14")
        scenario_table.add_column("vs Baseline", justify="right", style="#ffff00")

        baseline_total = result.total_predicted_cost
        for name, scenario_result in scenarios.items():
            total = scenario_result.total_predicted_cost
            diff = float((total - baseline_total) / baseline_total * 100) if baseline_total > 0 else 0
            scenario_table.add_row(
                name.capitalize(),
                f"${total:,.2f}",
                f"{diff:+.1f}%",
            )
        console.print(scenario_table)

    summary_panel = Panel(
        f"Total Predicted: [bold #39ff14]${result.total_predicted_cost:,.2f}[/]\n"
        f"Model Used:     [#e6f4f8]{result.model_used.value}[/]",
        title="[bold #00f3ff]REMORA-FIN | Forecast Engine[/]",
        border_style="#39ff14",
        expand=False,
    )
    console.print(summary_panel)


def add_forecast_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add forecast subparser."""
    parser = subparsers.add_parser(
        "forecast",
        help="Forecast future AWS costs",
        description="[bold #39ff14]Predict future AWS costs using ML-based forecasting.[/]",
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
