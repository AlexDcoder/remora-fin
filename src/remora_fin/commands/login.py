"""Login command — Configure AWS credentials."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table

from remora_fin.services import AWSSession, ConfigBuilder, ConfigService

logger = logging.getLogger(__name__)
console = Console()

COMMON_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "sa-east-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ca-central-1",
]


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


def interactive_select(label: str, choices: list[str], default: str | None = None) -> str:
    """A visual select list using rich."""
    console.print(f"\n [bold #4b86b4]»[/] [#e6f4f8]{label}[/]")

    for i, choice in enumerate(choices, 1):
        style = "bold #00f3ff" if choice == default else "#e6f4f8"
        console.print(f"   [#00f3ff]{i}.[/] [{style}]{choice}[/]")

    choice_map = {str(i): c for i, c in enumerate(choices, 1)}

    default_idx = "1"
    if default and default in choices:
        default_idx = str(choices.index(default) + 1)

    selected_idx = IntPrompt.ask(
        "\n [dim #4b86b4]Enter selection number[/]",
        choices=list(choice_map.keys()),
        default=int(default_idx),
        show_choices=False,
    )

    return choice_map[str(selected_idx)]


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
            "Choose Target AWS Region", COMMON_REGIONS, current_region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
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
