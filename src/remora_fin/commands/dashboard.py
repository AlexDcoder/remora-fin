"""Dashboard command — Launch the interactive TUI."""

from __future__ import annotations

import argparse

import rich_argparse
from rich.console import Console

from remora_fin.commands.utils import validate_aws_session
from remora_fin.services import AWSSession
from remora_fin.services.config_service import ConfigService
from remora_fin.ui.app import RemoraApp

console = Console()


def dashboard(args: argparse.Namespace) -> None:
    """Launch the interactive FinOps dashboard (TUI)."""

    config = ConfigService()
    settings = config.settings

    region = args.region or settings.aws.region
    profile = args.profile or settings.aws.profile

    # Pre-flight check
    session = AWSSession.get_instance(region=region, profile=profile)
    if not validate_aws_session(session):
        return

    from rich.panel import Panel
    from rich.text import Text

    welcome_text = Text.assemble(
        ("Launching Remora-Fin FinOps Dashboard\n", "bold #00f3ff"),
        ("\nProfile: ", "dim #4b86b4"),
        (f"{profile}", "#00f3ff"),
        ("\nRegion:  ", "dim #4b86b4"),
        (f"{region}", "#00f3ff"),
        ("\nTheme:   ", "dim #4b86b4"),
        (f"{settings.ui.theme}", "#00f3ff"),
        ("\n\nStarting Textual TUI...", "italic dim #4b86b4"),
    )
    console.print(Panel(welcome_text, border_style="#00f3ff", expand=False))

    # Launch the Textual app
    app = RemoraApp(
        region=region,
        profile=profile,
        default_days=settings.ui.default_period_days,
        theme=settings.ui.theme,
    )
    app.run()


def add_dashboard_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
