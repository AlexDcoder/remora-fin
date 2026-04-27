"""Report Service — Export cost analysis in multiple formats.

Design Patterns: Strategy + Template Method

Formats: PDF (Default), Rich Table, JSON, CSV, Parquet, Markdown
"""

from __future__ import annotations

import io
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar
from decimal import Decimal

import polars as pl
from fpdf import FPDF
from rich.console import Console
from rich.table import Table as RichTable

from remora.schemas.anomaly import AnomalyReport
from remora.schemas.cost import CostBreakdown, CostTrend
from remora.schemas.forecast import ForecastResult
from remora.schemas.report import ReportConfig, ReportFormat

logger = logging.getLogger(__name__)


# -- Strategy Interface --


class ReportFormatter(ABC):
    """Strategy interface for report output formats."""

    @abstractmethod
    def format_cost(self, data: CostBreakdown | CostTrend) -> bytes | str:
        """Format cost data."""
        ...

    @abstractmethod
    def format_anomalies(self, data: AnomalyReport) -> bytes | str:
        """Format anomaly data."""
        ...

    @abstractmethod
    def format_forecast(self, data: ForecastResult) -> bytes | str:
        """Format forecast data."""
        ...


# -- Concrete Formatters --

class PDFFormatter(ReportFormatter):
    """PDF formatter using fpdf2."""

    def __init__(self) -> None:
        super().__init__()

    def _create_base_pdf(self, title: str) -> FPDF:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="R")
        pdf.ln(10)
        return pdf

    def format_cost(self, data: CostBreakdown | CostTrend) -> bytes:
        pdf = self._create_base_pdf(f"Cost Report ({data.period.start} to {data.period.end})")
        
        if isinstance(data, CostBreakdown):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(80, 10, "Service", border=1)
            pdf.cell(50, 10, "Cost", border=1)
            pdf.cell(40, 10, "%", border=1, ln=True)
            
            pdf.set_font("Arial", "", 10)
            for g in data.groups[:30]:
                pdf.cell(80, 10, str(g.key), border=1)
                pdf.cell(50, 10, f"${g.cost:,.2f}", border=1)
                pdf.cell(40, 10, f"{g.percentage:.1f}%", border=1, ln=True)
        else:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(80, 10, "Date", border=1)
            pdf.cell(80, 10, "Cost", border=1, ln=True)
            
            pdf.set_font("Arial", "", 10)
            for p in data.points[-60:]:
                pdf.cell(80, 10, str(p.date), border=1)
                pdf.cell(80, 10, f"${p.cost:,.2f}", border=1, ln=True)
                
        return pdf.output()

    def format_anomalies(self, data: AnomalyReport) -> bytes:
        pdf = self._create_base_pdf(f"Anomaly Report ({data.total_anomalies} detected)")
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(60, 10, "ID", border=1)
        pdf.cell(50, 10, "Service", border=1)
        pdf.cell(30, 10, "Severity", border=1)
        pdf.cell(50, 10, "Variance", border=1, ln=True)
        
        pdf.set_font("Arial", "", 8)
        for a in data.anomalies[:40]:
            pdf.cell(60, 10, str(a.id[:18]), border=1)
            pdf.cell(50, 10, str(a.top_root_cause or "Unknown"), border=1)
            pdf.cell(30, 10, str(a.severity.value.upper()), border=1)
            pdf.cell(50, 10, f"{a.variance_percentage:.1f}%", border=1, ln=True)
            
        return pdf.output()

    def format_forecast(self, data: ForecastResult) -> bytes:
        pdf = self._create_base_pdf(f"Cost Forecast ({data.forecast_period.start} to {data.forecast_period.end})")
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(80, 10, "Date", border=1)
        pdf.cell(80, 10, "Predicted Cost", border=1, ln=True)
        
        pdf.set_font("Arial", "", 10)
        for p in data.predictions[:60]:
            pdf.cell(80, 10, str(p.date), border=1)
            pdf.cell(80, 10, f"${p.predicted_cost:,.2f}", border=1, ln=True)
            
        return pdf.output()


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

        return json.dumps(obj, indent=self._indent, default=default_handler)

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_anomalies(self, data: AnomalyReport) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_forecast(self, data: ForecastResult) -> str:
        return self._serialize(data.model_dump(mode="json"))


class FastTableFormatter(ReportFormatter):
    """Fast export using Polars (CSV, Parquet)."""

    def __init__(self, format: str = "csv"):
        self._format = format

    def _to_df(self, data: Any) -> pl.DataFrame:
        if isinstance(data, CostBreakdown):
            return pl.DataFrame([{"service": g.key, "cost": float(g.cost), "percentage": g.percentage} for g in data.groups])
        elif isinstance(data, CostTrend):
            return pl.DataFrame([{"date": p.date, "cost": float(p.cost)} for p in data.points])
        elif isinstance(data, AnomalyReport):
            return pl.DataFrame([{
                "id": a.id,
                "service": a.top_root_cause,
                "severity": a.severity.value,
                "actual": float(a.impact.total_actual_spend),
                "expected": float(a.impact.total_expected_spend),
                "variance": a.variance_percentage
            } for a in data.anomalies])
        elif isinstance(data, ForecastResult):
            return pl.DataFrame([{"date": p.date, "predicted_cost": float(p.predicted_cost)} for p in data.predictions])
        return pl.DataFrame()

    def _serialize(self, df: pl.DataFrame) -> bytes | str:
        if self._format == "csv":
            buf = io.BytesIO()
            df.write_csv(buf)
            return buf.getvalue().decode("utf-8")
        elif self._format == "parquet":
            buf = io.BytesIO()
            df.write_parquet(buf)
            return buf.getvalue()
        return ""

    def format_cost(self, data: CostBreakdown | CostTrend) -> bytes | str:
        return self._serialize(self._to_df(data))

    def format_anomalies(self, data: AnomalyReport) -> bytes | str:
        return self._serialize(self._to_df(data))

    def format_forecast(self, data: ForecastResult) -> bytes | str:
        return self._serialize(self._to_df(data))


class CsvFormatter(FastTableFormatter):
    """CSV formatter using Polars."""

    def __init__(self) -> None:
        super().__init__(format="csv")


class ParquetFormatter(FastTableFormatter):
    """Parquet formatter using Polars."""

    def __init__(self) -> None:
        super().__init__(format="parquet")


class MarkdownFormatter(ReportFormatter):
    """Markdown formatter for documentation."""

    def format_cost(self, data: CostBreakdown | CostTrend) -> str:
        lines = [
            "# Cost Report",
            "",
            f"**Period:** {data.period.start} → {data.period.end}",
            f"**Granularity:** {data.granularity}",
            f"**Metric:** {data.metric}",
            "",
        ]

        if isinstance(data, CostBreakdown) and data.summary:
            lines.extend(
                [
                    "## Summary",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Total Cost | ${data.summary.total_cost:,.2f} |",
                    f"| Daily Average | ${data.summary.daily_average:,.2f} |",
                    f"| Top Service | {data.summary.top_service} |",
                    "",
                ]
            )

        if isinstance(data, CostBreakdown):
            lines.extend(
                [
                    "## By Service",
                    "",
                    "| Service | Cost | % |",
                    "|---------|------|---|",
                ]
            )
            for g in data.groups[:20]:
                lines.append(f"| {g.key} | ${g.cost:,.2f} | {g.percentage:.1f}% |")
        else:
            lines.extend(
                [
                    "## Daily Trend",
                    "",
                    "| Date | Cost |",
                    "|------|------|",
                ]
            )
            for p in data.points[-30:]:
                lines.append(f"| {p.date} | ${p.cost:,.2f} |")

        return "\n".join(lines)

    def format_anomalies(self, data: AnomalyReport) -> str:
        lines = [
            "# Anomaly Report",
            "",
            f"**Total Anomalies:** {data.total_anomalies}",
            f"**Net Financial Impact:** ${data.net_financial_impact:,.2f}",
            "",
            "## By Severity",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]
        for sev, count in sorted(data.by_severity.items()):
            lines.append(f"| {sev.value.upper()} | {count} |")

        lines.extend(
            [
                "",
                "## Details",
                "",
                "| ID | Service | Severity | Actual | Expected | Variance |",
                "|----|---------|----------|--------|----------|----------|",
            ]
        )
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
            "# Cost Forecast",
            "",
            f"**Period:** {data.forecast_period.start} → {data.forecast_period.end}",
            f"**Model:** {data.model_used.value}",
            f"**Total Predicted:** ${data.total_predicted_cost:,.2f}",
            "",
            "| Date | Predicted Cost |",
            "|------|---------------|",
        ]
        for p in data.predictions[:30]:
            lines.append(f"| {p.date} | ${p.predicted_cost:,.2f} |")
        return "\n".join(lines)


# -- ReportService --


class ReportService:
    """Report generation with Strategy pattern for output formats."""

    _formatters: ClassVar[dict[str, ReportFormatter]] = {
        "pdf": PDFFormatter(),
        "table": TableFormatter(),
        "json": JsonFormatter(),
        "csv": FastTableFormatter(format="csv"),
        "parquet": FastTableFormatter(format="parquet"),
        "markdown": MarkdownFormatter(),
    }

    @classmethod
    def register_formatter(cls, name: str, formatter: ReportFormatter) -> None:
        cls._formatters[name] = formatter

    def generate_report(
        self,
        data: CostBreakdown | CostTrend | AnomalyReport | ForecastResult,
        config: ReportConfig | None = None,
    ) -> str | bytes:
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
            if isinstance(content, bytes):
                config.output_path.write_bytes(content)
            else:
                config.output_path.write_text(content, encoding="utf-8")
            logger.info("Report saved to %s", config.output_path)

        return content

    def generate_cost_summary(
        self,
        data: CostBreakdown | CostTrend,
        config: ReportConfig | None = None,
    ) -> str | bytes:
        return self.generate_report(data, config)

    def generate_anomaly_report(
        self,
        data: AnomalyReport,
        config: ReportConfig | None = None,
    ) -> str | bytes:
        return self.generate_report(data, config)

    def generate_forecast_report(
        self,
        data: ForecastResult,
        config: ReportConfig | None = None,
    ) -> str | bytes:
        return self.generate_report(data, config)
