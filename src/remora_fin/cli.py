"""CLI entry point — remora-fin command-line interface.

Usage:
    remora-fin --help
    remora-fin report --days 30
    remora-fin anomalies --detail
    remora-fin forecast --days 30
    remora-fin dashboard
    remora-fin login --test
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import logging
import sys
from textwrap import dedent

import rich_argparse

from remora_fin.commands import (
    add_anomalies_parser,
    add_cache_parser,
    add_dashboard_parser,
    add_forecast_parser,
    add_login_parser,
    add_profile_parser,
    add_report_parser,
    add_utilization_parser
)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging using RichHandler for better visual feedback."""
    from rich.logging import RichHandler

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )


ASCII_ART = r"""
 [bold #00f3ff]
    ____                                        _______     
   / __ \___  ____ ___  ____  _________ _      / ____(_)___ 
  / /_/ / _ \/ __ `__ \/ __ \/ ___/ __ `/_____/ /_  / / __ \
 / _, _/  __/ / / / / / /_/ / /  / /_/ /_____/ __/ / / / / /
/_/ |_|\___/_/ /_/ /_/\____/_/   \__,_/     /_/   /_/_/ /_/ 
                                                                
 [/]
 [bold #4b86b4]>> DEPTH STATUS: OPTIMAL[/]
 [bold #4b86b4]>> BIOLUMINESCENT STREAM: ACTIVE[/]
"""


def execute_cli() -> None:
    """Main CLI entry point."""
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    setup_logging()
    logger = logging.getLogger("remora_fin.cli")

    parser = argparse.ArgumentParser(
        prog="remora-fin",
        description=dedent(
            f"""
            {ASCII_ART}

    [italic #00f3ff]Remora-Fin[/] — [bold #39ff14]Deep Sea FinOps Intelligence[/]
    [dim #4b86b4]Autonomous AWS Cost Navigation & Governance[/]
            """
        ),
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )

    try:
        from importlib.metadata import version as get_version
        pkg_version = get_version("remora-fin")
    except Exception:
        pkg_version = "1.0.4"

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"[bold #00f3ff]remora-fin[/] [bold #39ff14]v{pkg_version}[/] [dim #4b86b4][DEEP-BLUE-RELEASE][/]",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all command parsers
    add_report_parser(subparsers)
    add_cache_parser(subparsers)
    add_anomalies_parser(subparsers)
    add_forecast_parser(subparsers)
    add_dashboard_parser(subparsers)
    add_login_parser(subparsers)
    add_profile_parser(subparsers)
    add_utilization_parser(subparsers)
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Enforce mandatory setup/login for all commands except 'login' and 'help'
    from remora_fin.services.config_service import ConfigService
    from rich import print as rprint

    config_service = ConfigService()
    if args.command != "login" and not config_service.is_configured():
        rprint("\n[bold #ff4500]INITIAL SETUP REQUIRED[/]")
        rprint("[#e6f4f8]To ensure consistent session management and caching, you must initialize Remora-Fin first.[/]")
        rprint("\n[bold #00f3ff]Please run:[/]")
        rprint("  [bold #39ff14]remora-fin login[/]\n")
        sys.exit(1)

    # Execute the command
    if hasattr(args, "func"):
        try:
            if inspect.iscoroutinefunction(args.func):
                asyncio.run(args.func(args))
            else:
                args.func(args)
        except KeyboardInterrupt:
            from rich import print as rprint
            rprint("\n[bold #ffff00]Session Aborted.[/]")
            sys.exit(130)
        except Exception as e:
            from rich import print as rprint
            logger.exception("Command failed")
            rprint(f"[bold #ff4500]CRITICAL ERROR:[/] {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    execute_cli()