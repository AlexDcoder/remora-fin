"""Utilization command — Analyze AWS resource efficiency."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.services.aws_service import AWSSession
from remora_fin.services.unit_economics_service import UnitEconomicsService

console = Console()


@aws_command
async def utilization(args: argparse.Namespace, session: AWSSession) -> None:
    """Analyze and display AWS resource utilization and pricing."""
    ue_service = UnitEconomicsService(session)

    with console.status("[bold green]Analyzing EC2 efficiency..."):
        ec2_data = await ue_service.get_ec2_efficiency(days=args.days)

    table = Table(title=f"EC2 Efficiency Analysis (Last {args.days} days)", header_style="bold magenta")
    table.add_column("Instance ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Avg CPU %", justify="right")
    table.add_column("Hourly Rate", justify="right")
    table.add_column("Est. Waste (7d)", justify="right", style="bold red")

    for item in ec2_data:
        cpu_color = "red" if item["avg_cpu"] < 5 else "yellow" if item["avg_cpu"] < 15 else "green"
        table.add_row(
            item["id"],
            item["name"] or "-",
            item["type"],
            f"[{cpu_color}]{item['avg_cpu']:.1f}%[/]",
            f"${item['hourly_rate']:.4f}",
            f"${item['potential_savings_7d']:.2f}",
        )

    console.print(table)
    
    if any(i["is_underutilized"] for i in ec2_data):
        console.print(Panel(
            "[bold yellow]Insight:[/] Several instances have very low CPU utilization. "
            "Consider [bold cyan]Right-sizing[/] to a smaller instance type or using [bold cyan]Spot Instances[/].",
            title="Recommendations",
            border_style="yellow"
        ))


def add_utilization_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add utilization subparser."""
    parser = subparsers.add_parser(
        "utilization",
        help="Analyze resource utilization and unit pricing",
        description="Correlate AWS inventory with CloudWatch metrics and Pricing API.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
        parents=[get_common_parser()],
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Period for metric analysis (default: 7 days)",
    )
    parser.set_defaults(func=utilization)
