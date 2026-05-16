"""Anomalies command — Detect and display cost anomalies."""

from __future__ import annotations

import argparse
import logging

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora.commands.utils import parse_dates, validate_aws_session
from remora.schemas.common import DateRange
from remora.schemas.report import ReportConfig, ReportFormat, ReportMetadata
from remora.services import AnomalyService, AWSSession, ReportService

logger = logging.getLogger(__name__)

console = Console()


def anomalies(args: argparse.Namespace) -> None:
    """Detect and display AWS cost anomalies."""
    start, end = parse_dates(args)

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )

    # Pre-flight check
    if not validate_aws_session(session):
        logger.error("[red]AWS session validation failed[/]")
        return

    anomaly_service = AnomalyService(session)
    report_service = ReportService()

    monitor_arn = args.monitor_arn or None

    # Fetch data
    with Status("[bold yellow]Detecting anomalies...", console=console) as status:
        logger.info(f"Period: [green]{start}[/] to [green]{end}[/]")
        report_data = anomaly_service.get_anomaly_summary(start, end, monitor_arn)

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
        print(report_service.generate_report(report_data, config, metadata))
    else:
        config = ReportConfig(format=ReportFormat.TABLE)
        print(report_service.generate_report(report_data, config, metadata))

        if report_data.total_anomalies == 0:
            print("\n[bold green]No cost anomalies detected in the selected period.[/] ✨\n")

        summary_panel = Panel(
            f"Total Anomalies: [bold red]{report_data.total_anomalies}[/]\nPeriod:         [cyan]{start} to {end}[/]",
            title="REMORA | Anomaly Insight",
            border_style="yellow",
            expand=False,
        )
        console.print(summary_panel)


def add_anomalies_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add anomalies subparser."""
    parser = subparsers.add_parser(
        "anomalies",
        help="Detect cost anomalies in your AWS account",
        description="[bold yellow]Detect and display AWS cost anomalies using ML-based detection.[/]",
        formatter_class=rich_argparse.RichHelpFormatter,
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Number of days to look back (default: 30, max 90)",
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
        "--severity",
        choices=["low", "medium", "high", "critical"],
        default=None,
        help="Filter by severity",
    )
    parser.add_argument(
        "--monitor-arn",
        default=None,
        help="Filter by specific anomaly monitor ARN",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show detailed anomaly list (always on in table/json output)",
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
    parser.set_defaults(func=anomalies)
