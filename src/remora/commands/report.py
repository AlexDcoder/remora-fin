"""Report command — Generate cost reports in multiple formats."""

from __future__ import annotations

import argparse
from pathlib import Path

import logging
from rich import print
from rich.console import Console
from rich.status import Status
from rich.panel import Panel
from remora.schemas.report import ReportFilters, ReportFormat, ReportMetadata, ReportConfig
from remora.schemas.common import DateRange
from remora.services import CostService, AWSSession, ReportService
from remora.commands.utils import parse_dates, validate_aws_session

logger = logging.getLogger(__name__)
console = Console()

def report(args: argparse.Namespace) -> None:
    """Generate a cost report."""
    start, end = parse_dates(args)

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    
    # Pre-flight check
    if not validate_aws_session(session):
        logger.error("AWS session validation failed")
        return

    cost_service = CostService(session)
    report_service = ReportService()

    # Build filters
    filters = ReportFilters(
        services=[args.service] if args.service else None,
    )

    # Fetch data
    metric = args.metric
    
    with Status(f"[bold cyan]Fetching {metric} data...", console=console) as status:
        logger.info("Period: [green]%s[/] to [green]%s[/]", start, end)
        
        if args.type == "trend":
            data = cost_service.get_daily_trend(start, end, metric=metric)
        elif args.type == "account":
            data = cost_service.get_cost_by_account(start, end, metric=metric)
        else:  # breakdown/service
            data = cost_service.get_cost_by_service(start, end, metric=metric)
        
        status.update("\n[bold magenta]Generating report...")

        # Prepare metadata
        identity = session.get_caller_identity()
        metadata = ReportMetadata(
            period=DateRange(start=start, end=end),
            generated_by=identity.get("arn"),
            account_id=identity.get("account"),
            filters_applied=filters,
        )

        # Output path logic
        fmt = ReportFormat(args.format)
        output_path = Path(args.output) if args.output else Path(f"remora_report_{args.type}.{fmt.value}")

        config = ReportConfig(
            format=fmt,
            output_path=output_path,
        )

        # Generate
        report_service.generate_report(data, config, metadata)
    
    # Final Success Message
    if fmt == ReportFormat.TABLE:
        # If it was a table, it was already printed to console by the formatter (actually generate_report returns it)
        # But ReportService.generate_report for TABLE format returns the string.
        # We should print it if it's TABLE or any text format that wasn't saved to file.
        if not args.output:
            # Re-run without output path to get content if we want to print it? 
            # Actually generate_report always returns content.
            content = report_service.generate_report(data, ReportConfig(format=fmt), metadata)
            print(content)

    success_panel = Panel(
        f"[bold green]Success![/]\n\n"
        f"Report Type: [cyan]{args.type.upper()}[/]\n"
        f"Format:      [magenta]{fmt.value.upper()}[/]\n"
        f"Location:    [blue]{output_path.absolute()}[/]",
        title="REMORA | Report Engine",
        border_style="green"
    )
    console.print(success_panel)


import rich_argparse

def add_report_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add report subparser."""
    parser = subparsers.add_parser(
        "report",
        help="Generate cost reports (pdf/table/json/csv/parquet/markdown)",
        description="[bold blue]Generate AWS cost reports in various formats.[/]\n\nSupports deep analysis by service, account, or daily trends.",
        formatter_class=rich_argparse.RichHelpFormatter,
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
