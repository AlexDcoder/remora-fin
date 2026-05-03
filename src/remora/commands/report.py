"""Report command — Generate cost reports in multiple formats."""

from __future__ import annotations

import argparse
from pathlib import Path

from remora.schemas.report import ReportFilters, ReportFormat
from remora.services import CostService, AWSSession
from remora.commands.utils import parse_dates, print_report


def report(args: argparse.Namespace) -> None:
    """Generate a cost report."""
    start, end = parse_dates(args)

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    cost_service = CostService(session)

    # Build filters
    filters = ReportFilters(
        services=[args.service] if args.service else None,
    )

    # Fetch data
    metric = args.metric
    if args.type == "trend":
        data = cost_service.get_daily_trend(start, end, metric=metric)
    elif args.type == "account":
        data = cost_service.get_cost_by_account(start, end, metric=metric)
    else:  # breakdown/service
        data = cost_service.get_cost_by_service(start, end, metric=metric)

    # Generate and print report
    print_report(
        data,
        fmt=args.format,
        output_path=Path(args.output) if args.output else None,
        filters=filters,
        group_by=args.group_by,
    )


def add_report_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add report subparser."""
    parser = subparsers.add_parser(
        "report",
        help="Generate cost reports (pdf/table/json/csv/parquet/markdown)",
        description="Generate AWS cost reports in various formats.",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["breakdown", "trend", "account"],
        default="breakdown",
        help="Report type (default: breakdown)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["pdf", "table", "json", "csv", "parquet", "markdown"],
        default="pdf",
        help="Output format (default: pdf)",
    )
    parser.add_argument(
        "--days",
        "-d",
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
            "UnblendedCost",
            "BlendedCost",
            "NetUnblendedCost",
            "AmortizedCost",
            "UsageQuantity",
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
        "--service",
        "-s",
        default=None,
        help="Filter by AWS service",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path",
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
    parser.set_defaults(func=report)
