"""Local cost history commands."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.schemas import HistorySnapshot
from remora_fin.services import AWSSession, CostService, FinOpsLocalStore

console = Console()


def _show(args: argparse.Namespace) -> None:
    table = Table(title="Local Cost History")
    for column in ("Captured", "Period", "Account", "Total"):
        table.add_column(column)
    for item in FinOpsLocalStore().list_history()[-args.limit :]:
        table.add_row(
            str(item.captured_at.date()),
            f"{item.period_start} - {item.period_end}",
            item.account_id,
            f"${item.total_cost:,.2f}",
        )
    console.print(table)


@aws_command
async def _capture(args: argparse.Namespace, session: AWSSession) -> None:
    end = date.today()
    start = end - timedelta(days=args.days)
    service = CostService(session)
    breakdown = await service.get_cost_by_service_async(start, end)
    identity = session.get_caller_identity()
    snapshot = HistorySnapshot(
        captured_at=datetime.now(),
        period_start=start,
        period_end=end,
        profile=session.profile,
        account_id=identity["account"],
        region=session.region,
        total_cost=Decimal(str(breakdown.total_cost)),
        by_service={group.key: group.cost for group in breakdown.groups},
    )
    FinOpsLocalStore().save_snapshot(snapshot)
    console.print(f"[green]Snapshot saved:[/] ${snapshot.total_cost:,.2f}")


def _export(args: argparse.Namespace) -> None:
    rows = [item.model_dump(mode="json") for item in FinOpsLocalStore().list_history()]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        import json

        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        lines = ["captured_at,period_start,period_end,profile,account_id,region,total_cost"]
        lines.extend(
            ",".join(
                str(item[key])
                for key in (
                    "captured_at",
                    "period_start",
                    "period_end",
                    "profile",
                    "account_id",
                    "region",
                    "total_cost",
                )
            )
            for item in rows
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[green]History exported to {path}[/]")


def add_history_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "history", help="Inspect local cost history", formatter_class=rich_argparse.RichHelpFormatter
    )
    actions = parser.add_subparsers(dest="history_action", required=True)
    show = actions.add_parser("show", help="Show captured snapshots")
    show.add_argument("--limit", type=int, default=12)
    show.set_defaults(func=_show)
    capture = actions.add_parser("capture", help="Capture a current AWS cost snapshot", parents=[get_common_parser()])
    capture.add_argument("--days", type=int, default=30)
    capture.set_defaults(func=_capture)
    export = actions.add_parser("export", help="Export snapshots")
    export.add_argument("--format", choices=["csv", "json"], default="csv")
    export.add_argument("--output", required=True)
    export.set_defaults(func=_export)
