"""Profile command — View current remora and AWS profile information."""

from __future__ import annotations

import argparse

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remora.services.aws_service import AWSSession
from remora.services.config_service import ConfigService

console = Console()


def show_profile(args: argparse.Namespace) -> None:
    """Display the current remora profile and AWS session information."""
    config_service = ConfigService()
    settings = config_service.settings

    console.print()
    console.print(Panel("[bold cyan]Remora Configuration Profile[/]", expand=False))

    # Remora Settings Table
    settings_table = Table(title="Application Settings", box=None, show_header=False)
    settings_table.add_column("Property", style="bold blue")
    settings_table.add_column("Value")

    settings_table.add_row("AWS Profile", settings.aws.profile)
    settings_table.add_row("Default Region", settings.aws.region)
    settings_table.add_row("Role ARN", settings.aws.role_arn or "[dim]None[/]")
    settings_table.add_row("Cache Enabled", "[green]Yes[/]" if settings.cache.enabled else "[yellow]No[/]")
    settings_table.add_row("Cache TTL", f"{settings.cache.ttl_seconds}s")
    settings_table.add_row("UI Theme", settings.ui.theme)

    console.print(settings_table)
    console.print()

    # AWS Session Info
    console.print("[bold blue]AWS Session Identity[/]")

    session = AWSSession.get_instance(region=settings.aws.region, profile=settings.aws.profile)

    try:
        if session.validate_credentials():
            identity = session.get_caller_identity()

            identity_table = Table(box=None, show_header=False)
            identity_table.add_column("Property", style="bold green")
            identity_table.add_column("Value")

            identity_table.add_row("Account", identity["account"])
            identity_table.add_row("ARN", identity["arn"])
            identity_table.add_row("User ID", identity["user_id"])

            console.print(identity_table)
        else:
            console.print("[bold red]Error:[/] Could not validate AWS credentials.")
            console.print("[dim]Ensure your AWS profile is correctly configured in ~/.aws/credentials[/]")
            console.print("[dim]and matches the profile in remora settings.[/]")
    except Exception as e:
        console.print(f"[bold red]Error checking AWS identity:[/] {e}")


def add_profile_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add profile subparser to the argument parser."""
    parser = subparsers.add_parser(
        "profile",
        help="View current profile and AWS identity",
        description="Displays remora configuration and the active AWS caller identity.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.set_defaults(func=show_profile)
