"""Dashboard command — Launch the interactive TUI."""

from __future__ import annotations

import argparse

import rich_argparse
from rich.console import Console

console = Console()


def dashboard(args: argparse.Namespace) -> None:
    """Launch the interactive FinOps dashboard (TUI)."""
    console.print("[bold blue]📊 Launching Remora FinOps Dashboard[/]")
    console.print()

    from remora.services.config_service import ConfigService

    config = ConfigService()
    settings = config.settings

    region = args.region or settings.aws.region
    profile = args.profile or settings.aws.profile

    console.print(f"  Profile: [cyan]{profile}[/]")
    console.print(f"  Region:  [cyan]{region}[/]")
    console.print(f"  Theme:   [cyan]{settings.ui.theme}[/]")
    console.print()
    console.print("[dim]Starting Textual TUI...[/]")

    # Launch the Textual app
    from remora.ui.app import RemoraApp

    app = RemoraApp(
        region=region,
        profile=profile,
        default_days=settings.ui.default_period_days,
        theme=settings.ui.theme,
    )
    app.run()


def add_dashboard_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add dashboard subparser."""
    parser = subparsers.add_parser(
        "dashboard",
        help="Open interactive FinOps dashboard (TUI)",
        description="Launch the interactive terminal UI for AWS FinOps.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
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
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default=None,
        help="UI theme",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=None,
        help="Default period in days",
    )
    parser.set_defaults(func=dashboard)
