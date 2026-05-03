"""Anomalies command — Detect and display cost anomalies."""

from __future__ import annotations

import argparse
from pathlib import Path

from remora.schemas.report import ReportFormat
from remora.services import AnomalyService, AWSSession
from remora.commands.utils import parse_dates, print_report


def anomalies(args: argparse.Namespace) -> None:
    """Detect and display AWS cost anomalies."""
    start, end = parse_dates(args)

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    anomaly_service = AnomalyService(session)

    monitor_arn = args.monitor_arn or None

    # Fetch data
    report_data = anomaly_service.get_anomaly_summary(start, end, monitor_arn)

    # Output
    fmt = ReportFormat.JSON if args.json else ReportFormat.TABLE
    print_report(
        report_data,
        fmt=fmt,
        output_path=Path(args.output) if hasattr(args, "output") and args.output else None,
    )


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
