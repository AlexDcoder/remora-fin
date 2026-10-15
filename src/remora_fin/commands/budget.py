"""Budget management commands."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.schemas import Budget, BudgetScope
from remora_fin.services import AWSSession, CostService, FinOpsLocalStore

console = Console()


def _list(args: argparse.Namespace) -> None:
    table = Table(title="FinOps Budgets")
    table.add_column("ID")
    table.add_column("Scope")
    table.add_column("Target")
    table.add_column("Monthly Limit", justify="right")
    budgets = FinOpsLocalStore().list_budgets()
    for item in budgets:
        table.add_row(item.id, item.scope.value, item.target, f"${item.monthly_limit:,.2f}")
    console.print(table)


def _set(args: argparse.Namespace) -> None:
    scope = BudgetScope(args.scope)
    target = args.target or "*"
    budget = Budget(
        id=args.id or f"{scope.value}:{target}",
        scope=scope,
        target=target,
        monthly_limit=Decimal(args.monthly),
    )
    FinOpsLocalStore().save_budget(budget)
    console.print(f"[green]Budget saved:[/] {budget.id}")


@aws_command
async def _check(args: argparse.Namespace, session: AWSSession) -> None:
    store = FinOpsLocalStore()
    end = date.today()
    start = end.replace(day=1)
    breakdown = await CostService(session).get_cost_by_service_async(start, end)
    total = Decimal(str(breakdown.total_cost))
    values: dict[tuple[BudgetScope, str], Decimal] = {(BudgetScope.TOTAL, "*"): total}
    values.update({(BudgetScope.SERVICE, group.key): group.cost for group in breakdown.groups})
    checks = store.check_budgets(values, start.strftime("%Y-%m"))
    table = Table(title=f"Budget Status ({start:%Y-%m})")
    table.add_column("Budget")
    table.add_column("Actual", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Consumed", justify="right")
    table.add_column("Status")
    for item in checks:
        table.add_row(
            item.budget.id,
            f"${item.actual:,.2f}",
            f"${item.budget.monthly_limit:,.2f}",
            f"{item.consumed_percent}%",
            item.status.value,
        )
    console.print(table)


def add_budget_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "budget", help="Manage local cost budgets", formatter_class=rich_argparse.RichHelpFormatter
    )
    actions = parser.add_subparsers(dest="budget_action", required=True)
    list_parser = actions.add_parser("list", help="List configured budgets")
    list_parser.set_defaults(func=_list)
    set_parser = actions.add_parser("set", help="Create or update a monthly budget")
    set_parser.add_argument("--scope", choices=[item.value for item in BudgetScope], default="total")
    set_parser.add_argument("--target", default="*", help="Service, account, region, or tag target")
    set_parser.add_argument("--monthly", required=True, help="Monthly limit in USD")
    set_parser.add_argument("--id", default=None)
    set_parser.set_defaults(func=_set)
    check_parser = actions.add_parser(
        "check", help="Compare current-month spend with budgets", parents=[get_common_parser()]
    )
    check_parser.set_defaults(func=_check)
