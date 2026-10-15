"""Login command — Configure AWS credentials."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from collections.abc import Iterator

import boto3
import rich_argparse
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table

from remora_fin.services import AWSSession, ConfigBuilder, ConfigService

logger = logging.getLogger(__name__)
console = Console()


def get_available_profiles() -> list[str]:
    """Fetch available AWS profiles using the AWS CLI."""
    try:
        result = subprocess.run(
            ["aws", "configure", "list-profiles"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["default"]


def get_available_regions() -> list[str]:
    """Return all EC2 regions known by the installed boto3 version."""
    session = boto3.session.Session()
    regions: set[str] = set()
    for partition in session.get_available_partitions():
        regions.update(session.get_available_regions("ec2", partition_name=partition))
    return sorted(regions)


def _keys() -> Iterator[str]:
    """Read terminal keys one at a time on Windows and POSIX terminals."""
    if os.name == "nt":
        import msvcrt

        while True:
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                key = msvcrt.getwch()
                yield {"H": "up", "P": "down", "K": "left", "M": "right"}.get(key, "")
            else:
                yield {"\r": "enter", "\x08": "backspace", "\x1b": "escape"}.get(key, key)
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                key = sys.stdin.read(1)
                if key == "\x1b":
                    sequence = sys.stdin.read(2)
                    yield {"[A": "up", "[B": "down", "[D": "left", "[C": "right"}.get(sequence, "escape")
                else:
                    yield {"\r": "enter", "\n": "enter", "\x7f": "backspace"}.get(key, key)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def interactive_select(label: str, choices: list[str], default: str | None = None) -> str:
    """Select an option with arrows, Enter, and optional text filtering."""
    if not choices:
        raise ValueError("choices must not be empty")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        default_index = choices.index(default) + 1 if default in choices else 1
        selected = IntPrompt.ask(label, choices=[str(i) for i in range(1, len(choices) + 1)], default=default_index)
        return choices[selected - 1]

    filtered = choices.copy()
    selected = filtered.index(default) if default in filtered else 0
    query = ""

    def render() -> Table:
        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column(width=2)
        table.add_column("Region")
        table.add_column("Hint", style="dim #4b86b4")
        if not filtered:
            table.add_row("", "No matching regions", "clear the filter")
            return table
        start = max(0, min(selected - 4, len(filtered) - 9))
        for index, region in enumerate(filtered[start : start + 9], start):
            active = index == selected
            table.add_row(">" if active else " ", f"[bold #00f3ff]{region}[/]" if active else region, "Enter to select" if active else "")
        return table

    console.print(f"\n [bold #4b86b4]»[/] [#e6f4f8]{label}[/]  [dim](↑/↓ navigate · type to filter · Enter select)[/]")
    with Live(render(), console=console, refresh_per_second=20, transient=True) as live:
        for key in _keys():
            if key == "enter" and filtered:
                return filtered[selected]
            if key == "escape":
                query = ""
            elif key == "backspace":
                query = query[:-1]
            elif key == "up" and filtered:
                selected = max(0, selected - 1)
            elif key == "down" and filtered:
                selected = min(len(filtered) - 1, selected + 1)
            elif len(key) == 1 and key.isprintable():
                query += key
            filtered = [choice for choice in choices if query.lower() in choice.lower()]
            selected = min(selected, len(filtered) - 1) if filtered else 0
            live.update(render())

    raise KeyboardInterrupt


def login(args: argparse.Namespace) -> None:
    """Configure and validate AWS credentials interactively with select lists."""
    config_service = ConfigService()

    console.print()
    console.print(
        Panel(
            "[bold #00f3ff]REMORA-FIN | AWS Quick Login[/]",
            subtitle="[dim #4b86b4]FinOps Intelligence Hub[/]",
            expand=False,
            border_style="#00f3ff",
        )
    )

    profiles = get_available_profiles()

    # Step 1: Profile Selection
    if args.profile and args.profile in profiles:
        selected_profile = args.profile
    else:
        # If profile provided in args but not in list, we still use it if it's not the default
        current_profile = config_service.get_aws_profile()
        selected_profile = interactive_select("Select AWS Identity (Profile)", profiles, current_profile)

    # Step 2: Region Selection
    if args.region:
        region = args.region
    else:
        current_region = config_service.get_default_region()
        region = interactive_select(
            "Choose Target AWS Region", get_available_regions(), current_region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )

    console.print("\n [bold #4b86b4]»[/] [#e6f4f8]Step 3: Validating Access...[/]")

    with console.status("[bold #4b86b4]Connecting to AWS Global Infrastructure...", spinner="dots"):
        session = AWSSession.get_instance(region=region, profile=selected_profile)
        is_valid = session.validate_credentials()
        billing_access = session.check_billing_access() if is_valid else False

    if is_valid:
        identity = session.get_caller_identity()

        # Save configuration
        new_settings = ConfigBuilder().with_aws_profile(selected_profile).with_region(region).build()
        config_service.save_config(new_settings)

        # Check for Root/Organization status
        is_root = False
        org_info = "Standalone Account"
        try:
            org_client = session.organizations()
            org_desc = org_client.describe_organization()
            is_root = org_desc["Organization"]["MasterAccountId"] == identity["account"]
            org_info = f"AWS Organization ([bold #e6f4f8]{org_desc['Organization']['Id']}[/])"
        except Exception:
            pass

        # Success Display
        status_color = "bold #ffff00" if is_root else "bold #39ff14"
        account_type = "ROOT / MANAGEMENT" if is_root else "MEMBER / STANDALONE"

        success_table = Table(box=None, show_header=False, padding=(0, 2))
        success_table.add_column("Key", style="dim #4b86b4")
        success_table.add_column("Value")

        success_table.add_row("Account ID", f"[bold #e6f4f8]{identity['account']}[/]")
        success_table.add_row("Identity Type", f"[{status_color}]{account_type}[/]")
        success_table.add_row("Active Region", f"[bold #00f3ff]{region}[/]")
        success_table.add_row("Organization", org_info)
        success_table.add_row(
            "Billing Access", "[bold #39ff14]Active[/]" if billing_access else "[bold #ff4500]Denied[/]"
        )
        success_table.add_row("User ARN", f"[dim #4b86b4]{identity['arn']}[/]")

        console.print()
        console.print(
            Panel(
                success_table,
                title="[bold #39ff14]✓ ACCESS GRANTED & SAVED[/]",
                border_style="#39ff14",
                expand=False,
            )
        )

        if not billing_access:
            console.print("\n[bold #ffff00]⚠️ BILLING ACCESS DENIED[/]")
            console.print("   [dim #4b86b4]Credentials are valid, but you lack permissions for Cost Explorer.[/]")
            console.print("   [dim #4b86b4]Ensure 'ce:GetCostAndUsage' is allowed in your IAM policy.[/]")

        if is_root:
            console.print("\n[bold #ffff00]✨ ROOT PRIVILEGES DETECTED[/]")
            console.print("   [dim #4b86b4]Full access to organization-wide billing and analytics.[/]")
            console.print(
                "   [bold #00f3ff]Next Step:[/] Run [italic]remora-fin report --type account[/] to see all accounts."
            )

        console.print("\n[dim #4b86b4]Ready for analysis. Use 'remora-fin --help' to see all modules.[/]\n")
    else:
        console.print(
            Panel(
                "[bold #ff4500]AUTHENTICATION ERROR[/]\n\n"
                "The credentials for profile '[#00f3ff]" + selected_profile + "[/]' are invalid.\n"
                "[dim #4b86b4]Check your ~/.aws/credentials or SSO session status.[/]",
                title="[bold #ff4500]CRITICAL[/]",
                border_style="#ff4500",
                expand=False,
            )
        )


def add_login_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add login subparser to the argument parser."""
    parser = subparsers.add_parser(
        "login",
        help="Configure AWS credentials interactively",
        description=(
            "[bold #00f3ff]Interactive AWS credential setup[/]\n\n"
            "This command guides you through selecting an AWS profile and region,\n"
            "validates your credentials, and saves the configuration for future use."
        ),
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=None,
        help="AWS profile name (skip interactive selection)",
    )
    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region (skip interactive selection)",
    )
    parser.set_defaults(func=login)
