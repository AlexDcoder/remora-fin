"""Anomalies command — Detect and display cost anomalies."""

from __future__ import annotations

import argparse
import logging

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora_fin.commands.utils import aws_command, get_common_parser, parse_dates
from remora_fin.services import AnomalyService, AWSSession

logger = logging.getLogger(__name__)

console = Console()


@aws_command
async def anomalies(args: argparse.Namespace, session: AWSSession) -> None:
    """Detect and display AWS cost anomalies."""
    start, end = parse_dates(args)

    anomaly_service = AnomalyService(session)

    monitor_arn = args.monitor_arn or None

    # Fetch data
    with Status("[bold #ffff00]Detecting anomalies...", console=console) as status:
        logger.info(f"Period: [#39ff14]{start}[/] to [#39ff14]{end}[/]")
        report_data = await anomaly_service.get_anomaly_summary_async(start, end, monitor_arn)

        status.update("[bold #4b86b4]Formatting results...")

    # Output
    if report_data.total_anomalies == 0:
        console.print("\n[bold #39ff14]No cost anomalies detected in the selected period.[/]\n")
    else:
        from rich.table import Table

        anomaly_table = Table(
            title=f"[bold #ff4500]Detected Cost Anomalies ({start} to {end})[/]",
            header_style="bold #00f3ff",
            border_style="#4b86b4",
        )
        anomaly_table.add_column("Date", style="dim")
        anomaly_table.add_column("Service/Root Cause", style="#e6f4f8")
        anomaly_table.add_column("Severity", justify="center")
        anomaly_table.add_column("Impact (USD)", justify="right", style="bold #ff4500")

        for a in report_data.anomalies:
            severity_color = (
                "#ff4500"
                if a.severity == "high" or a.severity == "critical"
                else "#ffff00"
                if a.severity == "medium"
                else "#39ff14"
            )
            top_cause = a.top_root_cause() if callable(a.top_root_cause) else a.top_root_cause
            anomaly_table.add_row(
                str(a.start_date),
                top_cause or "Unknown",
                f"[{severity_color}]{a.severity.upper()}[/]",
                f"${a.impact.total_actual_spend:,.2f}",
            )
        console.print(anomaly_table)

    summary_panel = Panel(
        f"Total Anomalies: [bold #ff4500]{report_data.total_anomalies}[/]\nPeriod:         [#00f3ff]{start} to {end}[/]",
        title="[bold #00f3ff]REMORA-FIN | Anomaly Insight[/]",
        border_style="#4b86b4",
        expand=False,
    )
    console.print(summary_panel)


def add_anomalies_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add anomalies subparser."""
    parser = subparsers.add_parser(
        "anomalies",
        help="Detect cost anomalies in your AWS account",
        description="[bold #ffff00]Detect and display AWS cost anomalies using ML-based detection.[/]",
        formatter_class=rich_argparse.RichHelpFormatter,
        parents=[get_common_parser()],
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
    parser.set_defaults(func=anomalies)
