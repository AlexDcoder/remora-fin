"""Report Service — Export cost analysis in multiple formats.

Design Patterns: Strategy + Template Method

Formats: Rich Table, JSON, CSV, Markdown
"""

from __future__ import annotations

import csv
import io
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
from rich.console import Console
from rich.table import Table as RichTable

from remora.schemas.anomaly import AnomalyReport
from remora.schemas.cost import CostBreakdown, CostTrend
from remora.schemas.forecast import ForecastResult
from remora.schemas.report import ReportConfig, ReportFilters, ReportMetadata

logger = logging.getLogger(__name__)


# -- Strategy Interface --


class ReportFormatter(ABC):
    """Strategy interface for report output formats."""

    @abstractmethod
    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        """Format cost data."""
        ...

    @abstractmethod
    def format_anomalies(self, data: AnomalyReport) -> str:
        """Format anomaly data."""
        ...

    @abstractmethod
    def format_forecast(self, data: ForecastResult) -> str:
        """Format forecast data."""
        ...


# -- Concrete Formatters --


class TableFormatter(ReportFormatter):
    """Rich Table formatter for terminal output."""

    def __init__(self, console: Console | None = None):
        self._console = console or Console()

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        table = RichTable(
            title=f"Cost Report ({data.period.start} → {data.period.end})",
            show_lines=True,
        )

        if isinstance(data, CostBreakdown):
            table.add_column("Service", style="cyan")
            table.add_column("Cost", justify="right", style="green")
            table.add_column("%", justify="right", style="yellow")

            for g in data.groups[:20]:  # Top 20
                table.add_row(g.key, f"${g.cost:,.2f}", f"{g.percentage:.1f}%")

            if data.summary:
                table.add_row(
                    "[bold]TOTAL[/bold]",
                    f"[bold green]${data.summary.total_cost:,.2f}[/]",
                    "100%",
                )

        else:  # CostTrend
            table.add_column("Date", style="cyan")
            table.add_column("Cost", justify="right", style="green")
            table.add_column("Trend", justify="right", style="yellow")

            for i, p in enumerate(data.points[-30:], 1):  # Last 30 days
                trend = ""
                if i > 1:
                    prev = data.points[-30 + i - 1]
                    if p.cost > prev.cost:
                        trend = "[red]▲[/]"
                    elif p.cost < prev.cost:
                        trend = "[green]▼[/]"
                    else:
                        trend = "[yellow]━[/]"
                table.add_row(
                    str(p.date),
                    f"${p.cost:,.2f}",
                    trend,
                )

        # Capture table output as string
        output = io.StringIO()
        temp_console = Console(file=output, force_terminal=True, width=120)
        temp_console.print(table)
        return output.getvalue()

    def format_anomalies(self, data: AnomalyReport) -> str:
        table = RichTable(
            title=f"Anomaly Report ({data.total_anomalies} detected)",
            show_lines=True,
        )
        table.add_column("ID", style="cyan", max_width=20)
        table.add_column("Service", style="white")
        table.add_column("Severity", justify="center")
        table.add_column("Actual", justify="right", style="green")
        table.add_column("Expected", justify="right", style="yellow")
        table.add_column("Variance %", justify="right", style="red")

        severity_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
            "critical": "bold red",
        }

        for a in data.anomalies[:30]:
            sev_color = severity_colors.get(a.severity.value, "white")
            table.add_row(
                a.id[:18],
                a.top_root_cause or "Unknown",
                f"[{sev_color}]{a.severity.value.upper()}[/{sev_color}]",
                f"${a.impact.total_actual_spend:,.2f}",
                f"${a.impact.total_expected_spend:,.2f}",
                f"{a.variance_percentage:.1f}%",
            )

        output = io.StringIO()
        temp_console = Console(file=output, force_terminal=True, width=120)
        temp_console.print(table)
        return output.getvalue()

    def format_forecast(self, data: ForecastResult) -> str:
        table = RichTable(
            title=f"Cost Forecast ({data.forecast_period.start} → {data.forecast_period.end})",
            show_lines=True,
        )
        table.add_column("Date", style="cyan")
        table.add_column("Predicted", justify="right", style="green")
        table.add_column("Model", style="dim")

        for p in data.predictions[:30]:  # First 30 days
            table.add_row(
                str(p.date),
                f"${p.predicted_cost:,.2f}",
                data.model_used.value,
            )

        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold green]${data.total_predicted_cost:,.2f}[/]",
            "",
        )

        output = io.StringIO()
        temp_console = Console(file=output, force_terminal=True, width=120)
        temp_console.print(table)
        return output.getvalue()


class JsonFormatter(ReportFormatter):
    """JSON formatter for machine consumption."""

    def __init__(self, indent: int = 2):
        self._indent = indent

    def _serialize(self, obj: Any) -> str:
        def default_handler(o: Any) -> Any:
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, Decimal):
                return str(o)
            if hasattr(o, "model_dump"):
                return o.model_dump(mode="json")
            raise TypeError(f"Object of type {type(o)} is not JSON serializable")

        from decimal import Decimal
        return json.dumps(obj, indent=self._indent, default=default_handler)

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_anomalies(self, data: AnomalyReport) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_forecast(self, data: ForecastResult) -> str:
        return self._serialize(data.model_dump(mode="json"))


class CsvFormatter(ReportFormatter):
    """CSV formatter for spreadsheet import."""

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        if isinstance(data, CostBreakdown):
            writer.writerow(["Service", "Cost", "Percentage"])
            for g in data.groups:
                writer.writerow([g.key, str(g.cost), f"{g.percentage}%"])
        else:
            writer.writerow(["Date", "Cost"])
            for p in data.points:
                writer.writerow([str(p.date), str(p.cost)])

        return output.getvalue()

    def format_anomalies(self, data: AnomalyReport) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Service", "Severity", "Actual Spend",
            "Expected Spend", "Variance %", "Start Date",
        ])
        for a in data.anomalies:
            writer.writerow([
                a.id,
                a.top_root_cause or "",
                a.severity.value,
                str(a.impact.total_actual_spend),
                str(a.impact.total_expected_spend),
                f"{a.variance_percentage:.2f}",
                str(a.start_date),
            ])
        return output.getvalue()

    def format_forecast(self, data: ForecastResult) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Predicted Cost"])
        for p in data.predictions:
            writer.writerow([str(p.date), str(p.predicted_cost)])
        return output.getvalue()


class MarkdownFormatter(ReportFormatter):
    """Markdown formatter for documentation."""

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        lines = [
            f"# Cost Report",
            f"",
            f"**Period:** {data.period.start} → {data.period.end}",
            f"**Granularity:** {data.granularity}",
            f"**Metric:** {data.metric}",
            f"",
        ]

        if isinstance(data, CostBreakdown) and data.summary:
            lines.extend([
                f"## Summary",
                f"",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total Cost | ${data.summary.total_cost:,.2f} |",
                f"| Daily Average | ${data.summary.daily_average:,.2f} |",
                f"| Top Service | {data.summary.top_service} |",
                f"",
            ])

        if isinstance(data, CostBreakdown):
            lines.extend([
                f"## By Service",
                f"",
                f"| Service | Cost | % |",
                f"|---------|------|---|",
            ])
            for g in data.groups[:20]:
                lines.append(f"| {g.key} | ${g.cost:,.2f} | {g.percentage:.1f}% |")
        else:
            lines.extend([
                f"## Daily Trend",
                f"",
                f"| Date | Cost |",
                f"|------|------|",
            ])
            for p in data.points[-30:]:
                lines.append(f"| {p.date} | ${p.cost:,.2f} |")

        return "\n".join(lines)

    def format_anomalies(self, data: AnomalyReport) -> str:
        lines = [
            f"# Anomaly Report",
            f"",
            f"**Total Anomalies:** {data.total_anomalies}",
            f"**Net Financial Impact:** ${data.net_financial_impact:,.2f}",
            f"",
            f"## By Severity",
            f"",
            f"| Severity | Count |",
            f"|----------|-------|",
        ]
        for sev, count in sorted(data.by_severity.items()):
            lines.append(f"| {sev.value.upper()} | {count} |")

        lines.extend([
            f"",
            f"## Details",
            f"",
            f"| ID | Service | Severity | Actual | Expected | Variance |",
            f"|----|---------|----------|--------|----------|----------|",
        ])
        for a in data.anomalies[:30]:
            lines.append(
                f"| {a.id[:18]} | {a.top_root_cause or ''} | "
                f"{a.severity.value.upper()} | "
                f"${a.impact.total_actual_spend:,.2f} | "
                f"${a.impact.total_expected_spend:,.2f} | "
                f"{a.variance_percentage:.1f}% |"
            )
        return "\n".join(lines)

    def format_forecast(self, data: ForecastResult) -> str:
        lines = [
            f"# Cost Forecast",
            f"",
            f"**Period:** {data.forecast_period.start} → {data.forecast_period.end}",
            f"**Model:** {data.model_used.value}",
            f"**Total Predicted:** ${data.total_predicted_cost:,.2f}",
            f"",
            f"| Date | Predicted Cost |",
            f"|------|---------------|",
        ]
        for p in data.predictions[:30]:
            lines.append(f"| {p.date} | ${p.predicted_cost:,.2f} |")
        return "\n".join(lines)


# -- ReportService --


class ReportService:
    """Report generation with Strategy pattern for output formats."""

    _formatters: dict[str, ReportFormatter] = {
        "table": TableFormatter(),
        "json": JsonFormatter(),
        "csv": CsvFormatter(),
        "markdown": MarkdownFormatter(),
    }

    @classmethod
    def register_formatter(cls, name: str, formatter: ReportFormatter) -> None:
        cls._formatters[name] = formatter

    def generate_report(
        self,
        data: CostBreakdown | CostTrend | AnomalyReport | ForecastResult,
        config: ReportConfig | None = None,
    ) -> str:
        """Generate a report in the specified format."""
        config = config or ReportConfig()
        formatter = self._formatters.get(config.format.value)
        if not formatter:
            raise ValueError(f"Unknown format: {config.format.value}")

        if isinstance(data, (CostBreakdown, CostTrend)):
            content = formatter.format_cost(data)
        elif isinstance(data, AnomalyReport):
            content = formatter.format_anomalies(data)
        elif isinstance(data, ForecastResult):
            content = formatter.format_forecast(data)
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")

        # Write to file if output_path specified
        if config.output_path:
            config.output_path.parent.mkdir(parents=True, exist_ok=True)
            config.output_path.write_text(content, encoding="utf-8")
            logger.info("Report saved to %s", config.output_path)

        return content

    def generate_cost_summary(
        self,
        data: CostBreakdown | CostTrend,
        config: ReportConfig | None = None,
    ) -> str:
        return self.generate_report(data, config)

    def generate_anomaly_report(
        self,
        data: AnomalyReport,
        config: ReportConfig | None = None,
    ) -> str:
        return self.generate_report(data, config)

    def generate_forecast_report(
        self,
        data: ForecastResult,
        config: ReportConfig | None = None,
    ) -> str:
        return self.generate_report(data, config)
