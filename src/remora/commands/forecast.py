"""Forecast command — Predict future AWS costs."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora.schemas.forecast import ForecastMetric
from remora.services import ForecastService
from remora.services.aws_service import AWSSession

console = Console()


def forecast_cmd(args: argparse.Namespace) -> None:
    """Predict future AWS costs."""
    # Parse forecast period
    start = date.today() + timedelta(days=1)
    if args.start:
        start = date.fromisoformat(args.start)

    if args.days:
        end = start + timedelta(days=args.days)
    elif args.end:
        end = date.fromisoformat(args.end)
    else:
        end = start + timedelta(days=30)  # Default 30 days forecast

    console.print(f"[bold blue]📈 Cost Forecast[/]  [dim]{start} → {end} ({(end - start).days} days)[/]")
    console.print()

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    forecast_service = ForecastService(session)

    # Parse metric
    metric = ForecastMetric(args.metric)

    with console.status("[cyan]Fetching forecast from AWS...[/]"):
        try:
            # Try native AWS forecast first
            result = forecast_service.get_aws_native_forecast(
                start=start,
                end=end,
                metric=metric,
                granularity=args.granularity,
                group_by_type=args.group_by_type,
                group_by_key=args.group_by_key,
            )
        except Exception as e:
            console.print(f"[yellow]⚠ Native forecast unavailable, using local fallback: {e}[/]")
            # Fallback to moving average
            from remora.services.cost_service import CostService
            from remora.services.forecast_service import MovingAverageForecast

            cost_service = CostService(session)
            hist_start = start - timedelta(days=60)
            trend = cost_service.get_daily_trend(hist_start, start)

            import polars as pl

            df = pl.DataFrame([{"date": p.date, "unblended_cost": p.cost} for p in trend.points])

            strategy = MovingAverageForecast(window=7)
            result = strategy.predict(
                historical_data=df,
                start=start,
                end=end,
                metric=metric,
            )

    # Display results
    console.print(
        f"[bold]Model:[/] {result.model_used.value}  "
        f"[bold]Total Predicted:[/] [green]${result.total_predicted_cost:,.2f}[/]"
    )
    console.print()

    # Forecast table
    forecast_table = Table(title="Daily Forecast", show_lines=True)
    forecast_table.add_column("Date", style="cyan")
    forecast_table.add_column("Predicted Cost", justify="right", style="green")

    # Show first 30 days
    for p in result.predictions[:30]:
        marker = "🔮" if p.is_predicted else "📊"
        forecast_table.add_row(
            f"{marker} {p.date}",
            f"${p.predicted_cost:,.2f}",
        )

    if len(result.predictions) > 30:
        forecast_table.add_row(
            f"... +{len(result.predictions) - 30} more days",
            "[dim](use --json for full output)[/]",
        )

    console.print(forecast_table)

    # Scenario analysis if requested
    if args.scenarios:
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

    # JSON output
    if args.json:
        console.print()
        console.print("[bold]JSON Output:[/]")
        import json

        console.print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


def add_forecast_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add forecast subparser."""
    parser = subparsers.add_parser(
        "forecast",
        help="Forecast future AWS costs",
        description="Predict future AWS costs using ML-based forecasting.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
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
        help="Forecast end date (YYYY-MM-DD)",
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
