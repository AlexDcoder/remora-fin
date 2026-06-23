"""CLI Command Utilities — Shared logic for CLI commands."""

from __future__ import annotations

import argparse
import functools
import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, TypeVar

from rich.console import Console

from remora_fin.services import AWSSession, ConfigService

logger = logging.getLogger(__name__)
console = Console()

T = TypeVar("T")


def validate_aws_session(session: AWSSession) -> bool:
    """Check if AWS credentials are valid and print error if not."""
    if not session.validate_credentials():
        console.print("\n[bold #ff4500]AUTHENTICATION ERROR[/]")
        console.print("[#e6f4f8]No valid AWS credentials found or session has expired.[/]")
        console.print("\n[bold #ffff00]RECOMMENDED ACTION[/]")
        console.print("Run [bold #00f3ff]remora-fin login[/] to set up your credentials interactively.")
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


def get_common_parser() -> argparse.ArgumentParser:
    """Create a parser with common AWS arguments."""
    parser = argparse.ArgumentParser(add_help=False)
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
    return parser


def aws_command(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle AWS session initialization and validation for commands."""

    @functools.wraps(func)
    async def wrapper(args: argparse.Namespace, *args_tail: Any, **kwargs: Any) -> Any:
        config_service = ConfigService()
        settings = config_service.settings

        # Initialize session
        session = AWSSession.get_instance(
            region=getattr(args, "region", None) or settings.aws.region,
            profile=getattr(args, "profile", None) or settings.aws.profile,
        )

        # Pre-flight check
        if not validate_aws_session(session):
            return

        # Inject session into arguments or call directly
        if "session" in func.__code__.co_varnames:
            return await func(args, session, *args_tail, **kwargs)
        return await func(args, *args_tail, **kwargs)

    return wrapper
