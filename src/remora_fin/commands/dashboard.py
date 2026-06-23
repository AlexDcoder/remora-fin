"""Dashboard command — Launch the interactive TUI."""

from __future__ import annotations

import argparse

import rich_argparse
from rich.console import Console

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.services import AWSSession, ConfigService
from remora_fin.ui.app import RemoraApp

console = Console()


@aws_command
async def dashboard(args: argparse.Namespace, session: AWSSession) -> None:
    """Launch the interactive FinOps dashboard (TUI)."""

    config = ConfigService()
    settings = config.settings

    from rich.panel import Panel
    from rich.text import Text

    welcome_text = Text.assemble(
        ("Launching Remora-Fin FinOps Dashboard\n", "bold #00f3ff"),
        ("\nProfile: ", "dim #4b86b4"),
        (f"{session.profile}", "#00f3ff"),
        ("\nRegion:  ", "dim #4b86b4"),
        (f"{session.region}", "#00f3ff"),
        ("\nTheme:   ", "dim #4b86b4"),
        (f"{settings.ui.theme}", "#00f3ff"),
        ("\n\nStarting Textual TUI...", "italic dim #4b86b4"),
    )
    console.print(Panel(welcome_text, border_style="#00f3ff", expand=False))

    # Launch the Textual app
    app = RemoraApp(
        region=session.region,
        profile=session.profile,
        default_days=settings.ui.default_period_days,
        theme=settings.ui.theme,
    )
    try:
        await app.run_async()
    except Exception as e:
        console.print(f"\n[bold #ff4500]Error running dashboard:[/] {e}")
        console.print("[dim #4b86b4]Try checking your AWS credentials with 'remora-fin login'[/]")


def add_dashboard_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add dashboard subparser."""
    parser = subparsers.add_parser(
        "dashboard",
        help="Open interactive FinOps dashboard (TUI)",
        description="Launch the interactive terminal UI for AWS FinOps.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
        parents=[get_common_parser()],
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
