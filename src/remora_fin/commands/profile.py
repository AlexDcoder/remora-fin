"""Profile command — View current remora-fin and AWS profile information."""

from __future__ import annotations

import argparse

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.config_service import ConfigService

console = Console()


def show_profile(args: argparse.Namespace) -> None:
    """Display the current remora-fin profile and AWS session information."""
    config_service = ConfigService()
    settings = config_service.settings

    console.print()
    console.print(
        Panel(
            "[bold #00f3ff]Remora-Fin Configuration Profile[/]",
            expand=False,
            border_style="#00f3ff",
        )
    )

    # Remora-Fin Settings Table
    settings_table = Table(
        title="[bold #4b86b4]» APPLICATION SETTINGS[/]",
        box=None,
        show_header=False,
        title_justify="left",
    )
    settings_table.add_column("Property", style="bold #4b86b4")
    settings_table.add_column("Value", style="#e6f4f8")

    settings_table.add_row("AWS Profile", settings.aws.profile)
    settings_table.add_row("Default Region", settings.aws.region)
    settings_table.add_row("Role ARN", settings.aws.role_arn or "[dim #4b86b4]None[/]")
    settings_table.add_row(
        "Cache Enabled",
        "[#39ff14]Yes[/]" if settings.cache.enabled else "[#ffff00]No[/]",
    )
    settings_table.add_row("Cache TTL", f"{settings.cache.ttl_seconds}s")
    settings_table.add_row("UI Theme", f"[bold #00f3ff]{settings.ui.theme}[/]")

    console.print(settings_table)
    console.print()

    # AWS Session Info
    console.print("[bold #4b86b4]» AWS SESSION IDENTITY[/]")

    session = AWSSession.get_instance(region=settings.aws.region, profile=settings.aws.profile)

    try:
        if session.validate_credentials():
            identity = session.get_caller_identity()

            # Check billing access
            billing_access = "[bold #ff4500]Denied[/]"
            try:
                ce = session.cost_explorer()
                ce.get_cost_and_usage(
                    TimePeriod={"Start": "2024-01-01", "End": "2024-01-02"},
                    Granularity="DAILY",
                    Metrics=["UnblendedCost"],
                )
                billing_access = "[bold #39ff14]Active[/]"
            except Exception as e:
                if "InvalidParameterException" in str(e) or "ValidationException" in str(e):
                    billing_access = "[bold #39ff14]Active[/]"

            identity_table = Table(box=None, show_header=False)
            identity_table.add_column("Property", style="bold #39ff14")
            identity_table.add_column("Value", style="#e6f4f8")

            identity_table.add_row("Account", identity["account"])
            identity_table.add_row("ARN", identity["arn"])
            identity_table.add_row("Billing Access", billing_access)
            identity_table.add_row("User ID", identity["user_id"])

            console.print(identity_table)
        else:
            console.print("[bold #ff4500]Error:[/] Could not validate AWS credentials.")
            console.print("[dim #4b86b4]Ensure your AWS profile is correctly configured in ~/.aws/credentials[/]")
            console.print("[dim #4b86b4]and matches the profile in remora-fin settings.[/]")
    except Exception as e:
        console.print(f"[bold #ff4500]Error checking AWS identity:[/] {e}")


def add_profile_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add profile subparser to the argument parser."""
    parser = subparsers.add_parser(
        "profile",
        help="View current profile and AWS identity",
        description="Displays remora-fin configuration and the active AWS caller identity.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.set_defaults(func=show_profile)
