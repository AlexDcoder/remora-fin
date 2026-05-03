"""CLI Command Utilities — Shared logic for CLI commands."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from typing import Any

from rich.console import Console

from remora.schemas.report import ReportConfig, ReportFormat
from remora.services.report_service import ReportService

console = Console()


def parse_dates(args: argparse.Namespace, default_days: int = 30) -> tuple[date, date]:
    """Parse start and end dates from CLI arguments."""
    end = date.today()
    if hasattr(args, "end") and args.end:
        end = date.fromisoformat(args.end)

    if hasattr(args, "days") and args.days:
        start = end - timedelta(days=args.days)
    elif hasattr(args, "start") and args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=default_days)

    return start, end


def print_report(
    data: Any,
    fmt: str | ReportFormat = ReportFormat.TABLE,
    output_path: Any = None,
    **kwargs: Any,
) -> None:
    """Generate and print a report using ReportService."""
    report_service = ReportService()
    
    if isinstance(fmt, str):
        fmt = ReportFormat(fmt)

    config = ReportConfig(
        format=fmt,
        output_path=output_path,
        **kwargs
    )

    content = report_service.generate_report(data, config)

    if isinstance(content, bytes):
        if not output_path:
            console.print(f"[yellow]⚠ Binary report generated but no output path provided.[/]")
    else:
        console.print(content)
