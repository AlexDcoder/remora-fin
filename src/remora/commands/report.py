"""Report command — Generate cost reports in multiple formats."""

from __future__ import annotations

import argparse
import rich_argparse
from datetime import date, timedelta
from pathlib import Path

from rich.console import Console

from remora.schemas.report import ReportConfig, ReportFilters, ReportFormat
from remora.services import CostService, ReportService
from remora.services.aws_service import AWSSession

console = Console()


def report(args: argparse.Namespace) -> None:
    """Generate a cost report."""
    # Parse dates
    end = date.today()
    if args.end:
        end = date.fromisoformat(args.end)
    if args.days:
        start = end - timedelta(days=args.days)
    elif args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=30)

    console.print(
        f"[bold blue]📊 Cost Report[/]  "
        f"[dim]{start} → {end}[/]"
    )
    console.print()

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    cost_service = CostService(session)
    report_service = ReportService()

    # Build filters
    filters = ReportFilters(
        services=[args.service] if args.service else None,
    )

    # Parse format
    fmt = ReportFormat(args.format)

    # Build config
    config = ReportConfig(
        format=fmt,
        output_path=Path(args.output) if args.output else None,
        filters=filters,
        group_by=args.group_by,
    )

    with console.status("[cyan]Fetching cost data from AWS...[/]"):
        if args.type == "breakdown":
            data = cost_service.get_cost_by_service(
                start, end,
                metric=args.metric,
            )
        elif args.type == "trend":
            data = cost_service.get_daily_trend(start, end)
        elif args.type == "account":
            data = cost_service.get_cost_by_account(start, end)
        else:
            data = cost_service.get_cost_by_service(start, end)

    # Generate report
    content = report_service.generate_report(data, config)

    # Output
    if fmt == ReportFormat.TABLE:
        console.print(content)
    elif fmt == ReportFormat.MARKDOWN:
        console.print(content)
    else:
        console.print(content)

    if config.output_path:
        console.print(f"\n[green]✓ Report saved to {config.output_path}[/]")


def add_report_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add report subparser."""
    parser = subparsers.add_parser(
        "report",
        help="Generate cost reports (table/json/csv/markdown)",
        description="Generate AWS cost reports in various formats.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.add_argument(
        "--type", "-t",
        choices=["breakdown", "trend", "account"],
        default="breakdown",
        help="Report type (default: breakdown)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv", "markdown"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD)",
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
            "UnblendedCost", "BlendedCost", "NetUnblendedCost",
            "AmortizedCost", "UsageQuantity",
        ],
        default="UnblendedCost",
        help="Cost metric (default: UnblendedCost)",
    )
    parser.add_argument(
        "--group-by",
        choices=["SERVICE", "LINKED_ACCOUNT", "REGION", "USAGE_TYPE"],
        default=None,
        help="Group results by dimension",
    )
    parser.add_argument(
        "--service", "-s",
        default=None,
        help="Filter by AWS service",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path",
    )
    parser.add_argument(
        "--profile", "-p",
        default=None,
        help="AWS profile name",
    )
    parser.add_argument(
        "--region", "-r",
        default=None,
        help="AWS region",
    )
    parser.set_defaults(func=report)
