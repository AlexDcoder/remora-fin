"""Local FinOps alert commands."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.schemas import BudgetScope
from remora_fin.services import AWSSession, CostService, FinOpsLocalStore

console = Console()


def _list(args: argparse.Namespace) -> None:
    table = Table(title="FinOps Alerts")
    for column in ("ID", "Severity", "Kind", "Status", "Title"):
        table.add_column(column)
    for item in FinOpsLocalStore().list_alerts(active_only=args.active):
        table.add_row(item.id, item.severity, item.kind, item.status.value, item.title)
    console.print(table)


def _acknowledge(args: argparse.Namespace) -> None:
    alert = FinOpsLocalStore().acknowledge_alert(args.alert_id)
    console.print(f"[green]Acknowledged {args.alert_id}[/]" if alert else f"[red]Alert not found: {args.alert_id}[/]")


@aws_command
async def _check(args: argparse.Namespace, session: AWSSession) -> None:
    store = FinOpsLocalStore()
    end = date.today()
    start = end.replace(day=1)
    breakdown = await CostService(session).get_cost_by_service_async(start, end)
    total = Decimal(str(breakdown.total_cost))
    values = {(BudgetScope.TOTAL, "*"): total}
    values.update({(BudgetScope.SERVICE, group.key): group.cost for group in breakdown.groups})
    checks = store.check_budgets(values, start.strftime("%Y-%m"))
    created = 0
    for item in checks:
        if item.status.value != "healthy":
            store.create_alert(
                "budget",
                "high" if item.status.value == "exceeded" else "medium",
                f"Budget {item.budget.id} is {item.status.value}",
                f"Actual ${item.actual:,.2f} of ${item.budget.monthly_limit:,.2f} for {item.period}.",
            )
            created += 1
    console.print(f"[green]Alert check complete:[/] {created} budget alert(s) active or created.")


def add_alerts_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "alerts", help="Inspect local FinOps alerts", formatter_class=rich_argparse.RichHelpFormatter
    )
    actions = parser.add_subparsers(dest="alerts_action", required=True)
    list_parser = actions.add_parser("list", help="List alerts")
    list_parser.add_argument("--active", action="store_true")
    list_parser.set_defaults(func=_list)
    ack = actions.add_parser("acknowledge", help="Acknowledge an alert")
    ack.add_argument("alert_id")
    ack.set_defaults(func=_acknowledge)
    check = actions.add_parser("check", help="Evaluate budgets and create local alerts", parents=[get_common_parser()])
    check.set_defaults(func=_check)
