"""Report command — Generate cost reports in multiple formats."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora_fin.commands.utils import parse_dates, validate_aws_session
from remora_fin.schemas.common import DateRange
from remora_fin.schemas.cost import CostBreakdown, CostTrend
from remora_fin.schemas.report import ReportConfig, ReportFilters, ReportFormat, ReportMetadata
from remora_fin.services import AWSSession, CostService, ReportService
from remora_fin.services.config_service import ConfigService

logger = logging.getLogger(__name__)
console = Console()


def report(args: argparse.Namespace) -> None:
    """Generate a cost report."""
    start, end = parse_dates(args)

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

    cost_service = CostService(session)
    report_service = ReportService()

    # Build filters
    filters = ReportFilters(
        services=[args.service] if args.service else None,
    )

    # Fetch data
    metric = args.metric
    data: CostBreakdown | CostTrend

    with Status(f"[bold #00f3ff]Fetching {metric} data...\n", console=console) as status:
        logger.info("Period: [#39ff14]%s[/] to [#39ff14]%s[/]", start, end)

        if args.type == "trend":
            data = cost_service.get_daily_trend(start, end, metric=metric)
        elif args.type == "account":
            data = cost_service.get_cost_by_account(start, end, metric=metric)
        else:  # breakdown/service
            data = cost_service.get_cost_by_service(start, end, metric=metric)

        status.update("\n[bold #4b86b4]Generating report...\n")

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
        account_id = identity.get("account", "unknown")
        region = session._region
        output_path = (
            Path(args.output)
            if args.output
            else Path(f"docs\\remora_report_{args.type}_{account_id}_{region}.{fmt.value}")
        )

        config = ReportConfig(
            format=fmt,
            output_path=output_path,
        )

        # Generate
        report_service.generate_report(data, config, metadata)

        # Final Success Message
        if fmt == ReportFormat.TABLE and not args.output:
            content = report_service.generate_report(data, ReportConfig(format=fmt), metadata)
            console.print(content)

    success_panel = Panel(
        f"[bold #39ff14]Success![/]\n\n"
        f"Report Type: [#00f3ff]{args.type.upper()}[/]\n"
        f"Format:      [#4b86b4]{fmt.value.upper()}[/]\n"
        f"Location:    [#e6f4f8]{output_path.absolute()}[/]",
        title="[bold #00f3ff]REMORA-FIN | Report Engine[/]",
        border_style="#00f3ff",
    )
    console.print(success_panel)


def add_report_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add report subparser."""
    parser = subparsers.add_parser(
        "report",
        help="Generate cost reports (pdf/table/json/csv/parquet/markdown)",
        description="[bold #4b86b4]Generate AWS cost reports in various formats.[/]\n\nSupports deep analysis by service, account, or daily trends.",
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
