"""Cost allocation and showback commands."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.services import AWSSession, CostService, FinOpsLocalStore

console = Console()


@aws_command
async def allocation_report(args: argparse.Namespace, session: AWSSession) -> None:
    end = date.today()
    start = end - timedelta(days=args.days)
    breakdown = await CostService(session).get_cost_by_service_async(start, end)
    entries = FinOpsLocalStore.allocate_by_service(
        [(group.key, group.cost) for group in breakdown.groups], Decimal(str(breakdown.total_cost))
    )
    table = Table(title=f"Cost Allocation ({start} to {end})")
    table.add_column("Classification")
    table.add_column("Source")
    table.add_column("Cost", justify="right")
    table.add_column("Share", justify="right")
    for item in entries:
        table.add_row(item.key, item.source, f"${item.cost:,.2f}", f"{item.percentage}%")
    console.print(table)
    console.print(
        "[dim]Service allocation is a showback baseline; tag-based allocation can be added when tag cost groups are configured.[/]"
    )


def add_allocation_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "allocation",
        help="Show cost attribution",
        formatter_class=rich_argparse.RichHelpFormatter,
        parents=[get_common_parser()],
    )
    parser.add_argument("--days", type=int, default=30)
    parser.set_defaults(func=allocation_report)
