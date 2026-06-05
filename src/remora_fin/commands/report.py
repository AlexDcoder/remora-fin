"""Report command — Generate cost reports in multiple formats."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from remora_fin.commands.utils import parse_dates, validate_aws_session
from remora_fin.schemas.common import DateRange
from remora_fin.schemas.cost import CostBreakdown, CostTrend
from remora_fin.schemas.report import FullReport, ReportConfig, ReportFilters, ReportFormat, ReportMetadata
from remora_fin.services import AWSSession, CostService, DashboardService, ForecastService, ReportService
from remora_fin.services.config_service import ConfigService

logger = logging.getLogger(__name__)
console = Console()


async def report(args: argparse.Namespace) -> None:
    """Generate a cost report."""
    start, end = parse_dates(args)

    config_service = ConfigService()
    settings = config_service.settings

    # Initialize services
    session = AWSSession.get_instance(
        region=args.region or settings.aws.region,
        profile=args.profile or settings.aws.profile,
    )

    # Pre-flight check
    if not validate_aws_session(session):
        logger.error("AWS session validation failed")
        return

    cost_service = CostService(session)
    report_service = ReportService()

    # Build filters
    filters = ReportFilters(
        services=args.service if args.service else None,
    )

    # Fetch data
    metric = args.metric
    fmt = ReportFormat(args.format)
    service_filters = [s.lower() for s in args.service] if args.service else []

    # Mapping common aliases to AWS display names for better filtering
    service_aliases = {
        "s3": "simple storage service",
        "ec2": "elastic compute cloud",
        "rds": "relational database service",
        "lambda": "lambda",
        "dynamodb": "dynamodb",
        "cloudfront": "cloudfront",
        "redshift": "redshift",
        "elasticache": "elasticache",
        "sagemaker": "sagemaker",
    }

    def _matches_service(aws_service_name: str) -> bool:
        if not service_filters:
            return True
        aws_name_lower = aws_service_name.lower()
        for s in service_filters:
            # Check direct match
            if s in aws_name_lower:
                return True
            # Check alias match
            alias = service_aliases.get(s)
            if alias and alias in aws_name_lower:
                return True
        return False

    data: CostBreakdown | CostTrend | FullReport

    with Status(f"[bold #00f3ff]Fetching {metric} data...\n", console=console) as status:
        logger.info("Period: [#39ff14]%s[/] to [#39ff14]%s[/]", start, end)

        if args.type == "full":
            dashboard_service = DashboardService(session)
            forecast_service = ForecastService(session)

            # Fetch summary (or dedicated service summary)
            summary_data = await dashboard_service.get_summary_parallel(days=args.days)

            # Fetch detailed breakdown
            breakdown = await cost_service.get_cost_by_service_async(start, end, metric=metric)
            if service_filters:
                # Filter breakdown entries and groups for the specific services
                filtered_entries = [e for e in breakdown.entries if _matches_service(e.service)]
                filtered_groups = [g for g in breakdown.groups if _matches_service(g.key)]

                new_summary = None
                if breakdown.summary:
                    # Recalculate summary for the specific services
                    svc_cost = sum((g.cost for g in filtered_groups), Decimal("0"))
                    new_summary = breakdown.summary.model_copy(update={"total_cost": svc_cost})

                breakdown = breakdown.model_copy(
                    update={"entries": filtered_entries, "groups": filtered_groups, "summary": new_summary}
                )

            # Fetch forecast
            try:
                forecast = await forecast_service.get_aws_native_forecast_async(
                    start=date.today(), end=date.today() + timedelta(days=args.days)
                )
            except Exception:
                forecast = None

            # Filter anomalies for the specific services
            anomalies = summary_data.get("anomalies")
            if service_filters and anomalies:
                filtered_anomalies = [
                    a for a in anomalies.anomalies if a.top_root_cause and _matches_service(a.top_root_cause)
                ]
                anomalies = anomalies.model_copy(
                    update={"anomalies": filtered_anomalies, "total_anomalies": len(filtered_anomalies)}
                )

            # Map infrastructure counts safely
            infra_data = summary_data.get("infrastructure", {})
            infra_counts = infra_data.get("counts") if isinstance(infra_data, dict) else {}

            if service_filters:
                # Keep only the requested services in the summary
                counts_items = infra_counts.items() if isinstance(infra_counts, dict) else {}
                infra_counts = {
                    k: v for k, v in counts_items if any(s in k.lower() for s in service_filters) or _matches_service(k)
                }

            data = FullReport(
                cost_breakdown=breakdown,
                cost_trend=summary_data.get("cost_trend"),
                anomalies=anomalies,
                forecast=forecast,
                infrastructure_summary=infra_counts,
                governance=summary_data.get("governance"),
            )
        elif args.type == "trend":
            data = await cost_service.get_daily_trend_async(start, end, metric=metric)
        elif args.type == "account":
            data = cost_service.get_cost_by_account(start, end, metric=metric)
        else:  # breakdown/service
            data = await cost_service.get_cost_by_service_async(start, end, metric=metric)
            if service_filters:
                filtered_entries = [e for e in data.entries if _matches_service(e.service)]
                filtered_groups = [g for g in data.groups if _matches_service(g.key)]
                data = data.model_copy(update={"entries": filtered_entries, "groups": filtered_groups})

        status.update("\n[bold #4b86b4]Generating report...\n")

        # Prepare metadata
        identity = session.get_caller_identity()
        metadata = ReportMetadata(
            period=DateRange(start=start, end=end),
            generated_by=identity.get("arn"),
            account_id=identity.get("account"),
            filters_applied=filters,
        )

        # Output path
        output_ext = "xlsx" if fmt == ReportFormat.EXCEL else fmt.value
        if not args.output:
            svc_tag = f"_{'_'.join([s.lower() for s in args.service])}" if args.service else ""
            filename = (
                f"remora_report_{args.type}{svc_tag}_{metadata.account_id or 'unknown'}_{session.region}.{output_ext}"
            )
            output_path = Path.cwd() / "docs" / filename
        else:
            output_path = Path(args.output)

        config = ReportConfig(
            format=fmt,
            output_path=output_path,
        )

        # Generate
        report_service.generate_report(data, config, metadata)

    success_panel = Panel(
        f"[bold #39ff14]Success![/]\n\n"
        f"Report Type: [#00f3ff]{args.type.upper()}[/]\n"
        f"Format:      [#4b86b4]{fmt.value.upper()}[/]\n"
        f"Location:    [#e6f4f8]{output_path.absolute()}[/]",
        title="[bold #00f3ff]REMORA-FIN | Report Engine[/]",
        border_style="#00f3ff",
    )
    console.print(success_panel)


def add_report_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add report subparser."""
    parser = subparsers.add_parser(
        "report",
        help="Generate FinOps reports (PDF, Excel, JSON, etc.)",
        description=(
            "[bold #4b86b4]Generate comprehensive AWS cost and governance reports.[/]\n\n"
            "Includes Cost Breakdown, Daily Trends, Anomaly Detection, Forecasts, "
            "Infrastructure Inventory, and Tag Compliance (Governance)."
        ),
        formatter_class=rich_argparse.RichHelpFormatter,
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["breakdown", "trend", "account", "full"],
        default="full",
        help="Report depth level (default: full)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["pdf", "excel", "csv", "markdown"],
        default="pdf",
        help="Output file format (default: pdf).",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--metric",
        choices=[
            "UnblendedCost",
            "BlendedCost",
            "NetUnblendedCost",
            "AmortizedCost",
            "UsageQuantity",
        ],
        default="UnblendedCost",
        help="Cost metric (default: UnblendedCost)",
    )
    parser.add_argument(
        "--group-by",
        choices=["SERVICE", "LINKED_ACCOUNT", "REGION", "USAGE_TYPE"],
        default=None,
        help="Group results by dimension",
    )
    parser.add_argument(
        "--service",
        "-s",
        nargs="+",
        default=None,
        help="Filter by one or more AWS services (e.g., --service ec2 s3)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=None,
        help="AWS profile name",
    )
    parser.add_argument(
        "--region",
        "-r",
        default=None,
        help="AWS region",
    )
    parser.set_defaults(func=report)
