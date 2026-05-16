"""Login command — Configure AWS credentials."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.prompt import Prompt

from remora.services.aws_service import AWSSession

console = Console()


def login(args: argparse.Namespace) -> None:
    """Configure and validate AWS credentials."""
    console.print("[bold blue]AWS Credential Configuration[/]")
    console.print()

    if args.test:
        # Just test existing credentials
        console.print("Testing existing AWS credentials...")
        session = AWSSession.get_instance(
            region=args.region or os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            profile=args.profile or os.getenv("AWS_PROFILE", "default"),
        )
        valid = session.validate_credentials()
        if valid:
            identity = session.get_caller_identity()
            console.print("[green]Credentials are valid![/]")
            console.print(f"  Account: {identity['account']}")
            console.print(f"  ARN: {identity['arn']}")
        else:
            console.print("[red]Credentials are invalid or not found.[/]")
            console.print()
            console.print("Configure with: [cyan]remora login --configure[/]")
        return

    # Interactive configuration
    console.print("Configure AWS credentials:")
    console.print()

    profile = Prompt.ask(
        "AWS Profile name",
        default=args.profile or "default",
    )
    region = Prompt.ask(
        "AWS Region",
        default=args.region or "us-east-1",
    )

    # Write to ~/.aws/credentials
    aws_dir = Path.home() / ".aws"
    aws_dir.mkdir(exist_ok=True)
    creds_file = aws_dir / "config"

    config_content = f"""[profile {profile}]
region = {region}
"""
    creds_file.write_text(config_content)
    console.print(f"[green]Profile '{profile}' saved to {creds_file}[/]")

    # Test the credentials
    console.print()
    console.print("Testing credentials...")
    session = AWSSession.get_instance(region=region, profile=profile)
    valid = session.validate_credentials()

    if valid:
        identity = session.get_caller_identity()
        console.print("[green]Credentials are valid![/]")
        console.print(f"  Account: {identity['account']}")
        console.print(f"  ARN: {identity['arn']}")
    else:
        console.print("[yellow]Could not validate credentials.[/]")
        console.print("  Make sure AWS access keys are configured for this profile.")
        console.print("  See: [link]https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html[/]")


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
