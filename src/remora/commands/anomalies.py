"""Anomalies command — Detect and display cost anomalies."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora.services import AnomalyService
from remora.services.aws_service import AWSSession

console = Console()


def anomalies(args: argparse.Namespace) -> None:
    """Detect and display AWS cost anomalies."""
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

    console.print(f"[bold blue]🔍 Cost Anomaly Detection[/]  [dim]{start} → {end}[/]")
    console.print()

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or "us-east-1",
        profile=args.profile or "default",
    )
    anomaly_service = AnomalyService(session)

    monitor_arn = args.monitor_arn or None

    with console.status("[cyan]Fetching anomaly data from AWS...[/]"):
        report = anomaly_service.get_anomaly_summary(start, end, monitor_arn)

    if report.total_anomalies == 0:
        console.print("[green]✓ No cost anomalies detected in this period.[/]")
        return

    # Summary
    console.print(
        f"[bold]{report.total_anomalies} anomalies detected[/]  "
        f"[dim](Net impact: ${report.net_financial_impact:,.2f})[/]"
    )
    console.print()

    # By severity
    severity_table = Table(title="By Severity", show_lines=True)
    severity_table.add_column("Severity", style="cyan")
    severity_table.add_column("Count", justify="right", style="green")

    severity_colors = {
        "low": "green",
        "medium": "yellow",
        "high": "red",
        "critical": "bold red",
    }

    for sev_key in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        sev_lower = sev_key.lower()
        from remora.schemas.anomaly import AnomalySeverity

        count = report.by_severity.get(AnomalySeverity(sev_lower), 0)
        if count > 0:
            sev_color = severity_colors.get(sev_lower, "white")
            severity_table.add_row(
                f"[{sev_color}]{sev_key}[/{sev_color}]",
                str(count),
            )

    console.print(severity_table)
    console.print()

    # Detail table
    if args.detail or args.format == "json":
        detail_table = Table(title="Anomaly Details", show_lines=True)
        detail_table.add_column("ID", style="cyan", max_width=20)
        detail_table.add_column("Service", style="white")
        detail_table.add_column("Severity", justify="center")
        detail_table.add_column("Actual", justify="right", style="green")
        detail_table.add_column("Expected", justify="right", style="yellow")
        detail_table.add_column("Variance", justify="right", style="red")

        # Filter by severity if requested
        anomalies_list = report.anomalies
        if args.severity:
            anomalies_list = [a for a in anomalies_list if a.severity.value == args.severity.lower()]

        for a in anomalies_list[:50]:
            sev_color = severity_colors.get(a.severity.value, "white")
            detail_table.add_row(
                a.id[:18],
                a.top_root_cause or "Unknown",
                f"[{sev_color}]{a.severity.value.upper()}[/{sev_color}]",
                f"${a.impact.total_actual_spend:,.2f}",
                f"${a.impact.total_expected_spend:,.2f}",
                f"{a.variance_percentage:.1f}%",
            )

        console.print(detail_table)

    if args.json:
        import json

        console.print()
        console.print("[bold]JSON Output:[/]")
        console.print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))


def add_anomalies_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add anomalies subparser."""
    parser = subparsers.add_parser(
        "anomalies",
        help="Detect cost anomalies in your AWS account",
        description="Detect and display AWS cost anomalies using ML-based detection.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
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
        help="Show detailed anomaly list",
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
