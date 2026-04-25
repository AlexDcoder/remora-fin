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
from textwrap import dedent

import rich_argparse

from remora.commands.anomalies import add_anomalies_parser
from remora.commands.dashboard import add_dashboard_parser
from remora.commands.forecast import add_forecast_parser
from remora.commands.login import add_login_parser
from remora.commands.report import add_report_parser
from remora.ui.app import RemoraApp


def demo(args: argparse.Namespace) -> None:
    """Launch the dashboard in demo mode with mock data."""
    from rich.console import Console
    console = Console()
    console.print("[bold green]🧪 Launching Remora in Demo Mode (Mock Data)[/]")
    
    app = RemoraApp(
        region="us-east-1",
        profile="demo",
        default_days=args.days or 30,
        theme=args.theme or "dark",
        use_mock=True,
    )
    app.run()


def add_demo_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "demo",
        help="Launch dashboard with mock data for UI testing",
        description="Launch the interactive terminal UI with simulated AWS data.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="UI theme",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Default period in days",
    )
    parser.set_defaults(func=demo)


ASCII_ART = r"""
            __________
            ╲______   ╲____   _____   ________________
            │       _╱╱ __ ╲ ╱     ╲ ╱  _ ╲_  __ ╲__  ╲
            │    │   ╲  ___╱│  Y Y  (  <_> )  │ ╲╱╱ __ ╲_
            │____│_  ╱╲___  >__│_│  ╱╲____╱│__│  (____  ╱
                    ╲╱     ╲╱     ╲╱                  ╲╱
"""


def execute_cli() -> None:
    """Main CLI entry point."""
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
    add_demo_parser(subparsers)

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
