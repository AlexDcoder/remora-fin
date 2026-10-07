"""CLI command for prioritized, read-only FinOps recommendations."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remora_fin.commands.utils import aws_command, get_common_parser
from remora_fin.schemas import RecommendationSummary
from remora_fin.services import AWSSession, RecommendationService

console = Console()


def _to_markdown(summary: RecommendationSummary) -> str:
    lines = [
        "# FinOps Recommendations",
        "",
        f"**Analysis window:** {summary.analysis_days} days  ",
        f"**Findings:** {summary.total_findings}  ",
        f"**Estimated monthly savings:** ${summary.total_estimated_monthly_savings:,.2f}",
        "",
        "| Service | Severity | Resource | Finding | Est. monthly savings |",
        "|---|---|---|---|---:|",
    ]
    for item in summary.recommendations:
        savings = (
            f"${item.estimated_monthly_savings:,.2f}" if item.estimated_monthly_savings is not None else "Not estimated"
        )
        lines.append(f"| {item.service} | {item.severity.value} | {item.resource_id} | {item.title} | {savings} |")
        lines.append(f"\n**Evidence:** {'; '.join(item.evidence)}  ")
        lines.append(f"**Suggested action:** {item.suggested_action}\n")
    if summary.partial_failures:
        lines.extend(["", "## Partial failures", ""])
        lines.extend(f"- {failure}" for failure in summary.partial_failures)
    return "\n".join(lines)


@aws_command
async def recommendations(args: argparse.Namespace, session: AWSSession) -> None:
    """Analyze AWS signals and display safe, prioritized actions."""
    service = RecommendationService(session)
    summary = await service.get_recommendations(days=args.days, services=args.service)
    if args.severity:
        filtered = [item for item in summary.recommendations if item.severity.value == args.severity]
        summary = summary.model_copy(
            update={
                "recommendations": filtered,
                "total_estimated_monthly_savings": sum(
                    (item.estimated_monthly_savings or Decimal("0") for item in filtered), Decimal("0")
                ),
            }
        )

    if args.format == "json":
        output = summary.model_dump_json(indent=2)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
            console.print(f"[bold #39ff14]Recommendations saved to {path.absolute()}[/]")
        else:
            console.print_json(output)
        return
    if args.format == "markdown":
        output = _to_markdown(summary)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
            console.print(f"[bold #39ff14]Recommendations saved to {path.absolute()}[/]")
        else:
            console.print(output, markup=False)
        return

    table = Table(title=f"FinOps Recommendations ({args.days} days)", header_style="bold #00f3ff")
    table.add_column("Service", style="#00f3ff")
    table.add_column("Severity")
    table.add_column("Resource", overflow="fold")
    table.add_column("Finding / Evidence")
    table.add_column("Est. monthly", justify="right")
    for item in summary.recommendations:
        savings = f"${item.estimated_monthly_savings:,.2f}" if item.estimated_monthly_savings is not None else "—"
        detail = f"{item.title}\n[dim]{'; '.join(item.evidence)}[/]\n[italic]{item.suggested_action}[/]"
        table.add_row(item.service, item.severity.value.upper(), item.resource_id, detail, savings)
    console.print(table)
    console.print(
        Panel(
            f"Findings: [bold]{summary.total_findings}[/]\n"
            f"Estimated monthly savings: [bold #39ff14]${summary.total_estimated_monthly_savings:,.2f}[/]\n"
            "[dim]Read-only analysis. Validate every recommendation before changing AWS resources.[/]",
            title="REMORA-FIN | Action Center",
            border_style="#4b86b4",
        )
    )
    for failure in summary.partial_failures:
        console.print(f"[yellow]Partial analysis failure:[/] {failure}")


def add_recommendations_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the recommendations command."""
    parser = subparsers.add_parser(
        "recommendations",
        help="Prioritize savings, governance, and resource-hygiene actions",
        description="Generate evidence-based, read-only AWS FinOps recommendations.",
        formatter_class=rich_argparse.RichHelpFormatter,
        parents=[get_common_parser()],
    )
    parser.add_argument("--days", "-d", type=int, default=14, choices=range(1, 366), metavar="1-365")
    parser.add_argument(
        "--service",
        "-s",
        nargs="+",
        choices=["ec2", "rds", "lambda", "s3", "governance", "tags"],
        default=None,
    )
    parser.add_argument("--severity", choices=["low", "medium", "high"], default=None)
    parser.add_argument("--format", "-f", choices=["table", "json", "markdown"], default="table")
    parser.add_argument("--output", "-o", default=None, help="Output path for JSON or Markdown")
    parser.set_defaults(func=recommendations)
