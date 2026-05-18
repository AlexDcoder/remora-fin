"""Report Service — Export cost analysis in multiple formats.

This service utilizes a Strategy pattern to support multiple export formats
including PDF, terminal tables, JSON, CSV, Parquet, and Markdown. It also
includes an S3 exporter for remote storage.
"""

from __future__ import annotations

import io
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

import polars as pl
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from rich.console import Console
from rich.table import Table as RichTable

from remora.schemas.anomaly import AnomalyReport
from remora.schemas.cost import CostBreakdown, CostGroup, CostTrend, CostTrendPoint
from remora.schemas.forecast import ForecastResult
from remora.schemas.report import FullReport, ReportConfig, ReportMetadata
from remora.services.aws_service import AWSSession

logger = logging.getLogger(__name__)


class S3Exporter:
    """Handles uploading generated reports to AWS S3."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize S3Exporter with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    def upload(self, content: bytes | str, bucket: str, key: str) -> str:
        """Upload content to a specific S3 bucket and key.

        Args:
            content: The data to upload (bytes or string).
            bucket: Target S3 bucket name.
            key: Target S3 object key.

        Returns:
            The S3 URI of the uploaded object.
        """
        s3 = self._session.s3()
        body = content if isinstance(content, bytes) else content.encode("utf-8")
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        logger.info("Report uploaded to [blue]s3://%s/%s[/]", bucket, key)
        return f"s3://{bucket}/{key}"


class ReportFormatter(ABC):
    """Abstract base class for report formatters (Strategy Interface)."""

    @abstractmethod
    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | str | FPDF:
        """Format cost breakdown or trend data."""
        ...

    @abstractmethod
    def format_anomalies(
        self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | str | FPDF:
        """Format anomaly detection results."""
        ...

    @abstractmethod
    def format_forecast(
        self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | str | FPDF:
        """Format cost forecast results."""
        ...

    @abstractmethod
    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> bytes | str:
        """Format a comprehensive report."""
        ...


class PDFFormatter(ReportFormatter):
    """PDF formatter leveraging the fpdf2 library."""

    def _create_base_pdf(self, title: str, metadata: ReportMetadata | None = None) -> FPDF:
        """Create a PDF object with a standard header and metadata."""
        pdf = FPDF()
        pdf.add_page()
        self._add_header(pdf, title, metadata)
        return pdf

    def _add_header(self, pdf: FPDF, title: str, metadata: ReportMetadata | None = None) -> None:
        """Add header to a new page."""
        # Header
        pdf.set_font("Arial", "B", 20)
        pdf.set_text_color(44, 62, 80)  # Dark Blue
        pdf.cell(0, 15, "REMORA | FinOps Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        pdf.set_draw_color(44, 62, 80)
        pdf.line(10, 25, 200, 25)
        pdf.ln(5)

        # Title and Dates
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Metadata / User Info
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(100, 100, 100)

        gen_time = (
            metadata.generated_at.strftime("%Y-%m-%d %H:%M:%S")
            if metadata
            else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        pdf.cell(100, 5, f"Generated: {gen_time}", new_x=XPos.RIGHT, new_y=YPos.TOP)

        if metadata:
            pdf.cell(
                0, 5, f"Account: {metadata.account_id or 'Unknown'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R"
            )
            pdf.cell(100, 5, f"User: {metadata.generated_by or 'Unknown'}", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(
                0,
                5,
                f"Period: {metadata.period.start} to {metadata.period.end}",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="R",
            )
        else:
            pdf.ln(5)

        pdf.ln(10)

    def _draw_bar_chart(self, pdf: FPDF, groups: list[CostGroup], title: str) -> None:
        """Draw a horizontal bar chart for the top services based on Usage Quantity."""
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        max_w = 140  # Max width of a bar

        # Sort by usage for this specific chart
        top_groups = sorted(groups, key=lambda x: x.usage_quantity, reverse=True)[:6]
        if not top_groups:
            return

        max_val = float(max(g.usage_quantity for g in top_groups)) if top_groups else 1.0

        for g in top_groups:
            # Label
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(40, 6, f"{g.key[:18]}", new_x=XPos.RIGHT, new_y=YPos.TOP)

            # Bar
            bar_w = (float(g.usage_quantity) / max_val) * max_w if max_val > 0 else 0
            pdf.set_fill_color(52, 152, 219)  # Lighter Blue for usage
            pdf.rect(pdf.get_x(), pdf.get_y() + 1, bar_w, 4, "F")

            # Value label
            pdf.set_x(pdf.get_x() + max_w + 5)
            pdf.cell(0, 6, f"{g.usage_quantity:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        pdf.ln(8)

    def _draw_line_chart(self, pdf: FPDF, points: list[CostTrendPoint], title: str) -> None:
        """Draw a progression line chart for cost trends."""
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        if not points:
            return

        h = 40  # Chart height
        w = 180  # Chart width
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        # Draw background/axes
        pdf.set_draw_color(230, 230, 230)
        pdf.rect(x_start, y_start, w, h)

        max_cost = float(max(p.cost for p in points)) if points else 1.0
        min_cost = float(min(p.cost for p in points)) if points else 0.0
        cost_range = max_cost - min_cost if max_cost != min_cost else 1.0

        pdf.set_draw_color(41, 128, 185)  # Blue line
        pdf.set_line_width(0.5)

        step_x = w / (len(points) - 1) if len(points) > 1 else w

        prev_x, prev_y = 0.0, 0.0
        for i, p in enumerate(points):
            curr_x = x_start + (i * step_x)
            # Inverse Y (top is 0)
            curr_y = y_start + h - ((float(p.cost) - min_cost) / cost_range * h)

            if i > 0:
                pdf.line(prev_x, prev_y, curr_x, curr_y)
            prev_x, prev_y = curr_x, curr_y

        pdf.set_y(y_start + h + 5)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, f"Min: ${min_cost:,.2f} | Max: ${max_cost:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        pdf.ln(8)

    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | FPDF:
        title = "Cost Analysis Report"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        if isinstance(data, CostBreakdown):
            # Summary Box
            if data.summary:
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 12, "  Executive Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(60, 10, f"  Total Cost: ${data.summary.total_cost:,.2f}", new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.cell(60, 10, f"  Daily Avg: ${data.summary.daily_average:,.2f}", new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.cell(0, 10, f"  Top Service: {data.summary.top_service}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(8)

            # Chart Section
            self._draw_bar_chart(pdf, data.groups, "Visual Breakdown (Top Services)")

            # Table Header
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(70, 10, " Service / Dimension", border=1, fill=True)
            pdf.cell(45, 10, " Usage (Quantity)", border=1, fill=True, align="C")
            pdf.cell(40, 10, " Cost (USD)", border=1, fill=True, align="C")
            pdf.cell(35, 10, " % of Total", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

            # Table Rows
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            for g in data.groups[:40]:
                pdf.cell(70, 8, f" {g.key[:40]}", border=1)
                pdf.cell(45, 8, f"{g.usage_quantity:,.2f}", border=1, align="R")
                pdf.cell(40, 8, f"${g.cost:,.2f}", border=1, align="R")
                pdf.cell(35, 8, f"{g.percentage:.1f}%", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        else:
            # Trend Chart
            self._draw_line_chart(pdf, data.points, "Cost Progression Over Time")

            # Table Header
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(50, 10, " Date", border=1, fill=True)
            pdf.cell(70, 10, " Usage Quantity", border=1, fill=True, align="C")
            pdf.cell(70, 10, " Cost (USD)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            for p in data.points[-60:]:
                pdf.cell(50, 8, f" {p.date}", border=1)
                pdf.cell(70, 8, f"{p.usage:,.2f}", border=1, align="R")
                pdf.cell(70, 8, f"${p.cost:,.2f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_anomalies(
        self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | FPDF:
        title = "Anomaly Detection Report"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 10, f"Total Spikes Detected: {data.total_anomalies}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(8)

        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(192, 57, 43)  # Soft Red
        pdf.set_text_color(255, 255, 255)
        pdf.cell(50, 10, " Service", border=1, fill=True)
        pdf.cell(30, 10, " Severity", border=1, fill=True, align="C")
        pdf.cell(35, 10, " Actual Cost", border=1, fill=True, align="C")
        pdf.cell(35, 10, " Expected", border=1, fill=True, align="C")
        pdf.cell(40, 10, " Variance %", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(0, 0, 0)
        for a in data.anomalies[:40]:
            pdf.cell(50, 8, f" {a.top_root_cause or 'Unknown'}", border=1)
            pdf.cell(30, 8, f" {a.severity.value.upper()}", border=1, align="C")
            pdf.cell(35, 8, f"${a.impact.total_actual_spend:,.2f} ", border=1, align="R")
            pdf.cell(35, 8, f"${a.impact.total_expected_spend:,.2f} ", border=1, align="R")
            pdf.cell(40, 8, f"{a.variance_percentage:+.1f}% ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_forecast(
        self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: FPDF | None = None
    ) -> bytes | FPDF:
        title = "Spend Forecast Projection"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        if data.total_predicted_cost:
            pdf.set_fill_color(230, 240, 230)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(
                0,
                12,
                f"  Estimated Total for Period: ${data.total_predicted_cost:,.2f}",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                fill=True,
            )
            pdf.ln(6)

        # Draw progression line for forecast
        trend_points = [CostTrendPoint(date=p.date, cost=p.predicted_cost) for p in data.predictions]
        self._draw_line_chart(pdf, trend_points, "Projected Spend Progression")

        # Service Breakdown for Forecast (if available)
        if data.grouped_predictions:
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(0, 10, "Projected Service Breakdown", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(4)

            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(100, 8, " Service", border=1, fill=True)
            pdf.cell(
                80, 8, " Predicted Period Spend", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
            )

            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            for svc, points in data.grouped_predictions.items():
                svc_total = sum(p.predicted_cost for p in points)
                pdf.cell(100, 7, f" {svc}", border=1)
                pdf.cell(80, 7, f"${svc_total:,.2f} ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            pdf.ln(8)

        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(39, 174, 96)  # Soft Green
        pdf.set_text_color(255, 255, 255)
        pdf.cell(95, 10, " Date", border=1, fill=True)
        pdf.cell(95, 10, " Predicted Cost (USD)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)
        for p in data.predictions[:60]:
            pdf.cell(95, 8, f" {p.date}", border=1)
            pdf.cell(95, 8, f"${p.predicted_cost:,.2f} ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> bytes:
        pdf = FPDF()
        if data.cost_breakdown:
            self.format_cost(data.cost_breakdown, metadata, pdf=pdf)
        if data.cost_trend:
            self.format_cost(data.cost_trend, metadata, pdf=pdf)
        if data.anomalies:
            self.format_anomalies(data.anomalies, metadata, pdf=pdf)
        if data.forecast:
            self.format_forecast(data.forecast, metadata, pdf=pdf)
        return bytes(pdf.output())


class TableFormatter(ReportFormatter):
    """Rich Table formatter for styled terminal output."""

    def __init__(self, console: Console | None = None):
        self._console = console or Console()

    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> str:
        table = RichTable(
            title=f"Cost Report ({data.period.start} → {data.period.end})",
            show_lines=True,
        )

        if isinstance(data, CostBreakdown):
            table.add_column("Service", style="cyan")
            table.add_column("Cost", justify="right", style="green")
            table.add_column("%", justify="right", style="yellow")

            for g in data.groups[:20]:
                table.add_row(g.key, f"${g.cost:,.2f}", f"{g.percentage:.1f}%")

            if data.summary:
                table.add_row(
                    "[bold]TOTAL[/bold]",
                    f"[bold green]${data.summary.total_cost:,.2f}[/]",
                    "100%",
                )
        else:
            table.add_column("Date", style="cyan")
            table.add_column("Cost", justify="right", style="green")
            table.add_column("Trend", justify="right", style="yellow")

            for i, p in enumerate(data.points[-30:], 1):
                trend = ""
                if i > 1:
                    prev = data.points[-30 + i - 1]
                    if p.cost > prev.cost:
                        trend = "[red]▲[/]"
                    elif p.cost < prev.cost:
                        trend = "[green]▼[/]"
                    else:
                        trend = "[yellow]━[/]"
                table.add_row(str(p.date), f"${p.cost:,.2f}", trend)

        output = io.StringIO()
        temp_console = Console(file=output, force_terminal=True, width=120)
        temp_console.print(table)
        return output.getvalue()

    def format_anomalies(self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
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

        severity_colors = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}

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

    def format_forecast(self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
        table = RichTable(
            title=f"Cost Forecast ({data.forecast_period.start} → {data.forecast_period.end})",
            show_lines=True,
        )
        table.add_column("Date", style="cyan")
        table.add_column("Predicted", justify="right", style="green")
        table.add_column("Model", style="dim")

        for p in data.predictions[:30]:
            table.add_row(str(p.date), f"${p.predicted_cost:,.2f}", data.model_used.value)

        table.add_row("[bold]TOTAL[/bold]", f"[bold green]${data.total_predicted_cost:,.2f}[/]", "")

        output = io.StringIO()
        temp_console = Console(file=output, force_terminal=True, width=120)
        temp_console.print(table)
        return output.getvalue()

    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> str:
        parts = []
        if data.cost_breakdown:
            parts.append(self.format_cost(data.cost_breakdown, metadata))
        if data.anomalies:
            parts.append(self.format_anomalies(data.anomalies, metadata))
        if data.forecast:
            parts.append(self.format_forecast(data.forecast, metadata))
        return "\n\n\n".join(parts)


class JsonFormatter(ReportFormatter):
    """JSON formatter for machine-readable output."""

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

    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_anomalies(self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_forecast(self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
        return self._serialize(data.model_dump(mode="json"))

    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> str:
        return self._serialize(data.model_dump(mode="json"))


class FastTableFormatter(ReportFormatter):
    """Fast exporter leveraging Polars for CSV and Parquet formats."""

    def __init__(self, format: str = "csv"):
        self._format = format

    def _to_df(self, data: Any) -> pl.DataFrame:
        if isinstance(data, CostBreakdown):
            return pl.DataFrame(
                [{"service": g.key, "cost": float(g.cost), "percentage": g.percentage} for g in data.groups]
            )
        elif isinstance(data, CostTrend):
            return pl.DataFrame([{"date": p.date, "cost": float(p.cost)} for p in data.points])
        elif isinstance(data, AnomalyReport):
            return pl.DataFrame(
                [
                    {
                        "id": a.id,
                        "service": a.top_root_cause,
                        "severity": a.severity.value,
                        "actual": float(a.impact.total_actual_spend),
                        "expected": float(a.impact.total_expected_spend),
                        "variance": a.variance_percentage,
                    }
                    for a in data.anomalies
                ]
            )
        elif isinstance(data, ForecastResult):
            return pl.DataFrame([{"date": p.date, "predicted_cost": float(p.predicted_cost)} for p in data.predictions])
        return pl.DataFrame()

    def _serialize(self, df: pl.DataFrame) -> bytes | str:
        buf = io.BytesIO()
        if self._format == "csv":
            df.write_csv(buf)
            return buf.getvalue().decode("utf-8")
        elif self._format == "parquet":
            df.write_parquet(buf)
            return buf.getvalue()
        return ""

    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> bytes | str:
        return self._serialize(self._to_df(data))

    def format_anomalies(
        self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> bytes | str:
        return self._serialize(self._to_df(data))

    def format_forecast(
        self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> bytes | str:
        return self._serialize(self._to_df(data))

    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> str:
        return "Comprehensive report not supported in CSV/Parquet yet."


class MarkdownFormatter(ReportFormatter):
    """Markdown formatter for documentation-ready reports."""

    def format_cost(
        self, data: CostBreakdown | CostTrend, metadata: ReportMetadata | None = None, pdf: Any = None
    ) -> str:
        lines = ["# Cost Report", "", f"**Period:** {data.period.start} → {data.period.end}", ""]
        if isinstance(data, CostBreakdown) and data.summary:
            lines.extend(
                [
                    "## Summary",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Total Cost | ${data.summary.total_cost:,.2f} |",
                    f"| Daily Average | ${data.summary.daily_average:,.2f} |",
                    "",
                ]
            )
        if isinstance(data, CostBreakdown):
            lines.extend(["## By Service", "", "| Service | Cost | % |", "|---------|------|---|"])
            for g in data.groups[:20]:
                lines.append(f"| {g.key} | ${g.cost:,.2f} | {g.percentage:.1f}% |")
        else:
            lines.extend(["## Daily Trend", "", "| Date | Cost |", "|------|------|"])
            for p in data.points[-30:]:
                lines.append(f"| {p.date} | ${p.cost:,.2f} |")
        return "\n".join(lines)

    def format_anomalies(self, data: AnomalyReport, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
        lines = ["# Anomaly Report", "", f"**Total Anomalies:** {data.total_anomalies}", ""]
        lines.extend(
            [
                "## Details",
                "",
                "| ID | Service | Severity | Actual | Expected | Variance |",
                "|----|---------|----------|--------|----------|----------|",
            ]
        )
        for a in data.anomalies[:30]:
            lines.append(
                f"| {a.id[:18]} | {a.top_root_cause or ''} | {a.severity.value.upper()} | "
                f"${a.impact.total_actual_spend:,.2f} | ${a.impact.total_expected_spend:,.2f} | "
                f"{a.variance_percentage:.1f}% |"
            )
        return "\n".join(lines)

    def format_forecast(self, data: ForecastResult, metadata: ReportMetadata | None = None, pdf: Any = None) -> str:
        lines = [
            "# Cost Forecast",
            "",
            f"**Total Predicted:** ${data.total_predicted_cost:,.2f}",
            "",
            "| Date | Predicted Cost |",
            "|------|---------------|",
        ]
        for p in data.predictions[:30]:
            lines.append(f"| {p.date} | ${p.predicted_cost:,.2f} |")
        return "\n".join(lines)

    def format_full(self, data: FullReport, metadata: ReportMetadata | None = None) -> str:
        parts = []
        if data.cost_breakdown:
            parts.append(self.format_cost(data.cost_breakdown, metadata))
        if data.anomalies:
            parts.append(self.format_anomalies(data.anomalies, metadata))
        if data.forecast:
            parts.append(self.format_forecast(data.forecast, metadata))
        return "\n\n\n".join(parts)


class ReportService:
    """Orchestrates report generation using the Strategy pattern."""

    _formatters: ClassVar[dict[str, ReportFormatter]] = {
        "pdf": PDFFormatter(),
        "table": TableFormatter(),
        "json": JsonFormatter(),
        "csv": FastTableFormatter(format="csv"),
        "parquet": FastTableFormatter(format="parquet"),
        "markdown": MarkdownFormatter(),
    }

    def generate_report(
        self,
        data: CostBreakdown | CostTrend | AnomalyReport | ForecastResult | FullReport,
        config: ReportConfig | None = None,
        metadata: ReportMetadata | None = None,
    ) -> str | bytes:
        """Generate a report in the specified format based on configuration."""
        config = config or ReportConfig()
        formatter = self._formatters.get(config.format.value)
        if not formatter:
            raise ValueError(f"Unknown format: {config.format.value}")

        if isinstance(data, (CostBreakdown, CostTrend)):
            content = formatter.format_cost(data, metadata)
        elif isinstance(data, AnomalyReport):
            content = formatter.format_anomalies(data, metadata)
        elif isinstance(data, ForecastResult):
            content = formatter.format_forecast(data, metadata)
        elif isinstance(data, FullReport):
            content = formatter.format_full(data, metadata)
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")

        if config.output_path:
            config.output_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (bytes, bytearray)):
                config.output_path.write_bytes(content)
            elif isinstance(content, str):
                config.output_path.write_text(content, encoding="utf-8")
            else:
                # Should not happen when final output is expected, but satisfies mypy
                logger.warning(
                    "[yellow]Report content is neither bytes nor string[/] (type: [cyan]%s[/]). Not saved.",
                    type(content),
                )

        # Final safety check for return type
        if isinstance(content, FPDF):
            return bytes(content.output())
        if isinstance(content, bytearray):
            return bytes(content)
        return content
