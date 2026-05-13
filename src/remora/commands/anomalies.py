"""Anomalies command — Detect and display cost anomalies."""

from __future__ import annotations

import argparse
from pathlib import Path

import logging
from rich import print
from remora.schemas.report import ReportFormat, ReportConfig, ReportMetadata
from remora.schemas.common import DateRange
from remora.services import AnomalyService, AWSSession, ReportService
from remora.commands.utils import parse_dates, validate_aws_session

logger = logging.getLogger(__name__)

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
        logger.error("AWS session validation failed")
        return

    anomaly_service = AnomalyService(session)
    report_service = ReportService()

    monitor_arn = args.monitor_arn or None

    # Fetch data
    logger.info("Detecting anomalies for period [green]%s[/] to [green]%s[/]", start, end)
    report_data = anomaly_service.get_anomaly_summary(start, end, monitor_arn)

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
        logger.info("Generating [bold yellow]Anomaly Summary Table[/]")
        print(report_service.generate_report(report_data, config, metadata))
        
        if report_data.total_anomalies == 0:
            print("\n[bold green]No cost anomalies detected in the selected period.[/] ✨\n")


def add_anomalies_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add anomalies subparser."""
    parser = subparsers.add_parser(
        "anomalies",
        help="Detect cost anomalies in your AWS account",
        description="Detect and display AWS cost anomalies using ML-based detection.",
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
