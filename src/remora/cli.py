"""CLI entry point — remora command-line interface.

Usage:
    remora --help
    remora report --days 30
    remora anomalies --detail
    remora forecast --days 30
    remora dashboard
    remora login --test
"""

from __future__ import annotations

import argparse
import sys
import logging
from textwrap import dedent

import rich_argparse

from remora.commands.anomalies import add_anomalies_parser
from remora.commands.dashboard import add_dashboard_parser
from remora.commands.forecast import add_forecast_parser
from remora.commands.login import add_login_parser
from remora.commands.report import add_report_parser
from remora.ui.app import RemoraApp


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
            __________
            ╲______   ╲____   _____   ____  __________
            │       _╱╱ __ ╲ ╱     ╲ ╱  _ ╲│  __ ╲__  ╲
            │    │   ╲  ___╱│  Y Y  (  <_> )  │ ╲╱╱ __ ╲_
            │____│_  ╱╲___  >__│_│  ╱╲____╱│__│  (____  ╱
                    ╲╱     ╲╱     ╲╱                  ╲╱
"""


def execute_cli() -> None:
    """Main CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        prog="remora",
        epilog="Remora-Fin: AWS FinOps (CLI)",
        description=dedent(
            f"""
            [bold blue]{ASCII_ART}[/]

    [italic blue]Remora[/] is a lightweight, high-performance FinOps toolkit for AWS.
            """
        ),
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="[blue]remora[/] [bold green]v0.1.0[/]",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all command parsers
    add_report_parser(subparsers)
    add_anomalies_parser(subparsers)
    add_forecast_parser(subparsers)
    add_dashboard_parser(subparsers)
    add_login_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Execute the command
    if hasattr(args, "func"):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(130)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    execute_cli()
