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
import sys
import logging
from textwrap import dedent

import rich_argparse

from remora_fin.commands.anomalies import add_anomalies_parser
from remora_fin.commands.dashboard import add_dashboard_parser
from remora_fin.commands.forecast import add_forecast_parser
from remora_fin.commands.login import add_login_parser
from remora_fin.commands.profile import add_profile_parser
from remora_fin.commands.report import add_report_parser
from remora_fin.ui.app import RemoraApp


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

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="[bold #00f3ff]remora-fin[/] [bold #39ff14]v1.0.0[/] [dim #4b86b4][DEEP-BLUE-RELEASE][/]",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all command parsers
    add_report_parser(subparsers)
    add_anomalies_parser(subparsers)
    add_forecast_parser(subparsers)
    add_dashboard_parser(subparsers)
    add_login_parser(subparsers)
    add_profile_parser(subparsers)

    # Enable argcomplete support
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Execute the command
    if hasattr(args, "func"):
        import asyncio
        import inspect

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
