"""CLI Command Utilities — Shared logic for CLI commands."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from rich.console import Console

from remora_fin.services.aws_service import AWSSession

console = Console()


def validate_aws_session(session: AWSSession) -> bool:
    """Check if AWS credentials are valid and print error if not."""
    if not session.validate_credentials():
        console.print("\n[bold #ff4500]AUTHENTICATION ERROR[/]")
        console.print("[#e6f4f8]No valid AWS credentials found or session has expired.[/]")
        console.print("\n[bold #ffff00]RECOMMENDED ACTION[/]")
        console.print("Run [bold #00f3ff]remora-fin login --configure[/] to set up your credentials.")
        return False
    return True


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
