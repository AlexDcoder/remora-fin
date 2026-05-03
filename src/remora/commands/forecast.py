"""Forecast command — Predict future AWS costs."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from remora.schemas.forecast import ForecastMetric
from remora.schemas.report import ReportFormat
from remora.services import ForecastService, AWSSession
from remora.commands.utils import parse_dates, print_report


def forecast_cmd(args: argparse.Namespace) -> None:
    """Predict future AWS costs."""
    # Parse forecast period (forecast usually starts tomorrow)
    default_start = date.today() + timedelta(days=1)
    
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = default_start

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
    forecast_service = ForecastService(session)

    # Fetch data using the service's automatic fallback logic
    result = forecast_service.get_forecast(
        start=start,
        end=end,
        metric=ForecastMetric(args.metric),
        granularity=args.granularity,
        group_by_type=args.group_by_type,
        group_by_key=args.group_by_key,
    )

    # Output
    fmt = ReportFormat.JSON if args.json else ReportFormat.TABLE
    print_report(
        result,
        fmt=fmt,
        output_path=Path(args.output) if hasattr(args, "output") and args.output else None,
    )

    # Scenario analysis if requested (kept as extra CLI output)
    if args.scenarios and not args.json:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        
        console.print()
        console.print("[bold]Scenario Analysis:[/]")
        variations = {
            "optimistic": -0.10,
            "baseline": 0.0,
            "pessimistic": 0.15,
        }
        scenarios = forecast_service.scenario_analysis(result, variations)
        scenario_table = Table(show_lines=True)
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
        console.print(scenario_table)


def add_forecast_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add forecast subparser."""
    parser = subparsers.add_parser(
        "forecast",
        help="Forecast future AWS costs",
        description="Predict future AWS costs using ML-based forecasting.",
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
