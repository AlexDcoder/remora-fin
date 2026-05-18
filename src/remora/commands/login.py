"""Login command — Configure AWS credentials."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

from remora.services.aws_service import AWSSession
from remora.services.governance_service import GovernanceService

console = Console()

COMMON_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "sa-east-1", "eu-central-1", "eu-west-1", "eu-west-2",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
    "ca-central-1"
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
    console.print(f"\n [bold blue]❯[/] [white]{label}[/]")
    
    for i, choice in enumerate(choices, 1):
        style = "bold cyan" if choice == default else "white"
        console.print(f"   [cyan]{i}.[/] [{style}]{choice}[/]")

    choice_map = {str(i): c for i, c in enumerate(choices, 1)}
    
    default_idx = "1"
    if default and default in choices:
        default_idx = str(choices.index(default) + 1)

    selected_idx = IntPrompt.ask(
        "\n [dim]Enter selection number[/]",
        choices=list(choice_map.keys()),
        default=int(default_idx),
        show_choices=False
    )
    
    return choice_map[str(selected_idx)]


def login(args: argparse.Namespace) -> None:
    """Configure and validate AWS credentials interactively with select lists."""
    console.print()
    console.print(Panel(
        "[bold cyan]REMORA | AWS Quick Login[/]",
        subtitle="[dim]FinOps Intelligence Hub[/]",
        expand=False,
        border_style="cyan"
    ))

    profiles = get_available_profiles()
    
    # Step 1: Profile Selection
    if args.profile and args.profile in profiles:
        selected_profile = args.profile
    else:
        selected_profile = interactive_select("Select AWS Identity (Profile)", profiles, "default")

    # Step 2: Region Selection
    if args.region:
        region = args.region
    else:
        region = interactive_select("Choose Target AWS Region", COMMON_REGIONS, os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    console.print(f"\n [bold blue]❯[/] [white]Step 3: Validating Access...[/]")
    
    with console.status("[bold blue]Connecting to AWS Global Infrastructure...", spinner="dots"):
        session = AWSSession.get_instance(region=region, profile=selected_profile)
        is_valid = session.validate_credentials()
    
    if is_valid:
        identity = session.get_caller_identity()
        
        # Check for Root/Organization status
        is_root = False
        org_info = "Standalone Account"
        try:
            org_client = session.organizations()
            org_desc = org_client.describe_organization()
            is_root = org_desc["Organization"]["MasterAccountId"] == identity["account"]
            org_info = f"AWS Organization ([bold white]{org_desc['Organization']['Id']}[/])"
        except Exception:
            pass

        # Success Display
        status_color = "bold gold1" if is_root else "bold green"
        account_type = "ROOT / MANAGEMENT" if is_root else "MEMBER / STANDALONE"
        
        success_table = Table(box=None, show_header=False, padding=(0, 2))
        success_table.add_column("Key", style="dim")
        success_table.add_column("Value")
        
        success_table.add_row("Account ID", f"[bold white]{identity['account']}[/]")
        success_table.add_row("Identity Type", f"[{status_color}]{account_type}[/]")
        success_table.add_row("Active Region", f"[bold cyan]{region}[/]")
        success_table.add_row("Organization", org_info)
        success_table.add_row("User ARN", f"[dim]{identity['arn']}[/]")

        console.print()
        console.print(Panel(
            success_table, 
            title="[bold green]✓ ACCESS GRANTED[/]", 
            border_style="green",
            expand=False
        ))
        
        if is_root:
            console.print("\n[bold gold1]✨ ROOT PRIVILEGES DETECTED[/]")
            console.print("   [dim]Full access to organization-wide billing and analytics.[/]")
            console.print("   [bold cyan]Next Step:[/] Run [italic]remora report --type account[/] to see all accounts.")
            
        console.print("\n[dim]Ready for analysis. Use 'remora --help' to see all modules.[/]\n")
    else:
        console.print(Panel(
            "[bold red]AUTHENTICATION ERROR[/]\n\n"
            "The credentials for profile '[cyan]" + selected_profile + "[/]' are invalid.\n"
            "[dim]Check your ~/.aws/credentials or SSO session status.[/]",
            title="Critical",
            border_style="red",
            expand=False
        ))


def add_login_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add login subparser to the argument parser."""
    parser = subparsers.add_parser(
        "login",
        help="Configure AWS credentials",
        description="Set up or test AWS credential profiles.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        "-p",
        default="default",
        help="AWS profile name (default: default)",
    )
    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Test existing credentials without configuring",
    )
    parser.add_argument(
        "--configure",
        "-c",
        action="store_true",
        help="Interactive credential configuration",
    )
    parser.set_defaults(func=login)
