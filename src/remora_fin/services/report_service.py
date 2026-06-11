"""Report Service — Export cost analysis in multiple formats.

This service utilizes a Strategy pattern to support multiple export formats
including PDF, Excel, JSON, CSV, Parquet, and Markdown. It also
includes an S3 exporter for remote storage.
"""

from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

import polars as pl
import xlsxwriter
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from remora_fin.schemas.anomaly import AnomalyReport
from remora_fin.schemas.cost import CostBreakdown, CostGroup, CostTrend, CostTrendPoint
from remora_fin.schemas.forecast import ForecastResult
from remora_fin.schemas.report import FullReport, ReportConfig, ReportMetadata
from remora_fin.services.aws_service import AWSSession

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
        self,
        data: CostBreakdown | CostTrend,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | str | FPDF:
        """Format cost breakdown or trend data."""
        ...

    @abstractmethod
    def format_anomalies(
        self,
        data: AnomalyReport,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | str | FPDF:
        """Format anomaly detection results."""
        ...

    @abstractmethod
    def format_forecast(
        self,
        data: ForecastResult,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | str | FPDF:
        """Format cost forecast results."""
        ...

    @abstractmethod
    def format_infrastructure(
        self,
        data: dict[str, int],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | str | FPDF:
        """Format infrastructure inventory summary."""
        ...

    @abstractmethod
    def format_governance(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | str | FPDF:
        """Format governance and compliance data."""
        ...

    @abstractmethod
    def format_full(
        self, data: FullReport, metadata: ReportMetadata | None = None, config: ReportConfig | None = None
    ) -> bytes | str:
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
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(44, 62, 80)  # Dark Blue
        pdf.cell(0, 15, "REMORA | FinOps Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        pdf.set_draw_color(44, 62, 80)
        pdf.line(10, 25, 200, 25)
        pdf.ln(5)

        # Title and Dates
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Metadata / User Info
        pdf.set_font("Helvetica", "", 9)
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
        pdf.set_font("Helvetica", "B", 10)
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
            pdf.set_font("Helvetica", "", 8)
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

    def _draw_line_chart(self, pdf: FPDF, points: list[CostTrendPoint], title: str, show_labels: bool = True) -> None:
        """Draw a progression line chart for cost trends with optional minimalistic labels."""
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        if not points:
            return

        h = 40  # Chart height
        w = 170  # Chart width
        x_start = pdf.get_x() + 15  # Offset for Y labels
        y_start = pdf.get_y()

        # Draw background/axes
        pdf.set_draw_color(230, 230, 230)
        pdf.rect(x_start, y_start, w, h)

        max_cost = float(max(p.cost for p in points)) if points else 1.0
        min_cost = float(min(p.cost for p in points)) if points else 0.0
        cost_range = max_cost - min_cost if max_cost != min_cost else 1.0

        # Minimalistic Labels
        if show_labels:
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(120, 120, 120)

            # Y-Axis (Max/Min)
            pdf.text(x_start - 14, y_start + 2, f"${max_cost:,.0f}")
            pdf.text(x_start - 14, y_start + h, f"${min_cost:,.0f}")

            # X-Axis (Start/End Dates)
            start_date = str(points[0].date)
            end_date = str(points[-1].date)
            pdf.text(x_start, y_start + h + 4, start_date)
            pdf.text(x_start + w - 18, y_start + h + 4, end_date)

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

        pdf.set_y(y_start + h + 6)
        pdf.ln(4)

    def format_cost(
        self,
        data: CostBreakdown | CostTrend,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | FPDF:
        title = "Cost Analysis Report"
        is_partial = pdf is not None
        config = config or ReportConfig()

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        if isinstance(data, CostBreakdown):
            # Summary Box
            if data.summary:
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 12, "  Executive Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(60, 10, f"  Total Cost: ${data.summary.total_cost:,.2f}", new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.cell(60, 10, f"  Daily Avg: ${data.summary.daily_average:,.2f}", new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.cell(0, 10, f"  Top Service: {data.summary.top_service}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(8)

            # Chart Section
            if config.include_charts:
                self._draw_bar_chart(pdf, data.groups, "Visual Breakdown (Top Services)")

            # Table Header
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(70, 10, " Service / Dimension", border=1, fill=True)
            pdf.cell(45, 10, " Usage (Quantity)", border=1, fill=True, align="C")
            pdf.cell(40, 10, " Cost (USD)", border=1, fill=True, align="C")
            pdf.cell(35, 10, " % of Total", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

            # Table Rows
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            for g in data.groups[:40]:
                pdf.cell(70, 8, f" {g.key[:40]}", border=1)
                pdf.cell(45, 8, f"{g.usage_quantity:,.2f}", border=1, align="R")
                pdf.cell(40, 8, f"${g.cost:,.2f}", border=1, align="R")
                pdf.cell(35, 8, f"{g.percentage:.1f}%", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        else:
            # Trend Chart
            if config.include_charts:
                self._draw_line_chart(pdf, data.points, "Cost Progression Over Time", show_labels=config.chart_labels)

            # Table Header
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(50, 10, " Date", border=1, fill=True)
            pdf.cell(70, 10, " Usage Quantity", border=1, fill=True, align="C")
            pdf.cell(70, 10, " Cost (USD)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            for p in data.points[-60:]:
                pdf.cell(50, 8, f" {p.date}", border=1)
                pdf.cell(70, 8, f"{p.usage:,.2f}", border=1, align="R")
                pdf.cell(70, 8, f"${p.cost:,.2f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_anomalies(
        self,
        data: AnomalyReport,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | FPDF:
        title = "Anomaly Detection Report"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 10, f"Total Spikes Detected: {data.total_anomalies}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(192, 57, 43)  # Soft Red
        pdf.set_text_color(255, 255, 255)
        pdf.cell(50, 10, " Service", border=1, fill=True)
        pdf.cell(30, 10, " Severity", border=1, fill=True, align="C")
        pdf.cell(35, 10, " Actual Cost", border=1, fill=True, align="C")
        pdf.cell(35, 10, " Expected", border=1, fill=True, align="C")
        pdf.cell(40, 10, " Variance %", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)
        for a in data.anomalies[:40]:
            pdf.cell(50, 8, f" {a.top_root_cause or 'Unknown'}", border=1)
            pdf.cell(30, 8, f" {a.severity.value.upper()}", border=1, align="C")
            pdf.cell(35, 8, f"${a.impact.total_actual_spend:,.2f} ", border=1, align="R")
            pdf.cell(35, 8, f"${a.impact.total_expected_spend:,.2f} ", border=1, align="R")
            pdf.cell(40, 8, f"{a.variance_percentage:+.1f}% ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_forecast(
        self,
        data: ForecastResult,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | FPDF:
        title = "Spend Forecast Projection"
        is_partial = pdf is not None
        config = config or ReportConfig()

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        if data.total_predicted_cost:
            pdf.set_fill_color(230, 240, 230)
            pdf.set_font("Helvetica", "B", 11)
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
        if config.include_charts:
            trend_points = [CostTrendPoint(date=p.date, cost=p.predicted_cost) for p in data.predictions]
            self._draw_line_chart(pdf, trend_points, "Projected Spend Progression", show_labels=config.chart_labels)

        # Service Breakdown for Forecast (if available)
        if data.grouped_predictions:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(0, 10, "Projected Service Breakdown", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(4)

            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(100, 8, " Service", border=1, fill=True)
            pdf.cell(
                80, 8, " Predicted Period Spend", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
            )

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            for svc, points in data.grouped_predictions.items():
                svc_total = sum(p.predicted_cost for p in points)
                pdf.cell(100, 7, f" {svc}", border=1)
                pdf.cell(80, 7, f"${svc_total:,.2f} ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(39, 174, 96)  # Soft Green
        pdf.set_text_color(255, 255, 255)
        pdf.cell(95, 10, " Date", border=1, fill=True)
        pdf.cell(95, 10, " Predicted Cost (USD)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        for p in data.predictions[:60]:
            pdf.cell(95, 8, f" {p.date}", border=1)
            pdf.cell(95, 8, f"${p.predicted_cost:,.2f} ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_infrastructure(
        self,
        data: dict[str, int],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | FPDF:
        title = "Infrastructure Inventory Summary"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 10, "Resource Counts", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(52, 152, 219)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(100, 10, " Service", border=1, fill=True)
        pdf.cell(80, 10, " Count", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        for svc, count in sorted(data.items()):
            pdf.cell(100, 8, f" {svc.upper()}", border=1)
            pdf.cell(80, 8, f"{count} ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        return pdf if is_partial else bytes(pdf.output())

    def format_governance(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: FPDF | None = None,
    ) -> bytes | FPDF:
        title = "Governance & Compliance Report"
        is_partial = pdf is not None

        if not pdf:
            pdf = self._create_base_pdf(title, metadata)
        else:
            pdf.add_page()
            self._add_header(pdf, title, metadata)

        score = data.get("score", 0)
        compliant = data.get("compliant_resources", 0)
        non_compliant = data.get("non_compliant_resources", 0)
        total = data.get("total_resources", 0)

        # Compliance Score Box
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font("Helvetica", "B", 12)
        color = (39, 174, 96) if score >= 80 else (230, 126, 34) if score >= 50 else (192, 57, 43)
        pdf.set_text_color(*color)
        pdf.cell(0, 15, f"  Tag Compliance Score: {score:.1f}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(60, 10, f"Compliant: {compliant}", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(60, 10, f"Non-Compliant: {non_compliant}", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(0, 10, f"Total Resources: {total}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(8)

        # Details Table
        if data.get("details"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(140, 10, " Resource ARN", border=1, fill=True)
            pdf.cell(50, 10, " Status", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(0, 0, 0)
            for item in data["details"][:50]:
                status = "COMPLIANT" if item.get("is_compliant") else "NON-COMPLIANT"
                pdf.cell(140, 8, f" {item['arn'][-80:]}", border=1)
                pdf.cell(50, 8, f" {status}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        return pdf if is_partial else bytes(pdf.output())

    def format_full(
        self, data: FullReport, metadata: ReportMetadata | None = None, config: ReportConfig | None = None
    ) -> bytes:
        pdf = FPDF()
        config = config or ReportConfig()
        if data.cost_breakdown:
            self.format_cost(data.cost_breakdown, metadata, config=config, pdf=pdf)
        if data.cost_trend:
            self.format_cost(data.cost_trend, metadata, config=config, pdf=pdf)
        if data.anomalies:
            self.format_anomalies(data.anomalies, metadata, config=config, pdf=pdf)
        if data.forecast:
            self.format_forecast(data.forecast, metadata, config=config, pdf=pdf)
        if data.infrastructure_summary:
            self.format_infrastructure(data.infrastructure_summary, metadata, config=config, pdf=pdf)
        if data.governance:
            self.format_governance(data.governance, metadata, config=config, pdf=pdf)
        return bytes(pdf.output())


class ExcelFormatter(ReportFormatter):
    """Excel formatter using Polars and xlsxwriter."""

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
        elif isinstance(data, dict):
            # Infrastructure or Governance
            if "score" in data:
                # Simple flat view for Excel
                return pl.DataFrame([{"metric": k, "value": v} for k, v in data.items() if k != "details"])
            return pl.DataFrame([{"service": k, "count": v} for k, v in data.items()])
        return pl.DataFrame()

    def format_cost(
        self,
        data: CostBreakdown | CostTrend,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> bytes:
        df = self._to_df(data)
        buf = io.BytesIO()
        df.write_excel(buf)
        return buf.getvalue()

    def format_anomalies(
        self,
        data: AnomalyReport,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> bytes:
        df = self._to_df(data)
        buf = io.BytesIO()
        df.write_excel(buf)
        return buf.getvalue()

    def format_forecast(
        self,
        data: ForecastResult,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> bytes:
        df = self._to_df(data)
        buf = io.BytesIO()
        df.write_excel(buf)
        return buf.getvalue()

    def format_infrastructure(
        self,
        data: dict[str, int],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> bytes:
        df = self._to_df(data)
        buf = io.BytesIO()
        df.write_excel(buf)
        return buf.getvalue()

    def format_governance(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> bytes:
        df = self._to_df(data)
        buf = io.BytesIO()
        df.write_excel(buf)
        return buf.getvalue()

    def format_full(
        self, data: FullReport, metadata: ReportMetadata | None = None, config: ReportConfig | None = None
    ) -> bytes:
        sheets = {}
        if data.cost_breakdown:
            sheets["Cost Breakdown"] = self._to_df(data.cost_breakdown)
        if data.cost_trend:
            sheets["Cost Trend"] = self._to_df(data.cost_trend)
        if data.anomalies:
            sheets["Anomalies"] = self._to_df(data.anomalies)
        if data.forecast:
            sheets["Forecast"] = self._to_df(data.forecast)
        if data.infrastructure_summary:
            sheets["Infrastructure"] = self._to_df(data.infrastructure_summary)
        if data.governance:
            sheets["Governance"] = self._to_df(data.governance)

        buf = io.BytesIO()
        with xlsxwriter.Workbook(buf) as workbook:
            for name, df in sheets.items():
                df.write_excel(workbook=workbook, worksheet=name)
        return buf.getvalue()


class FastTableFormatter(ReportFormatter):
    """Fast exporter leveraging Polars for CSV format."""

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
        elif isinstance(data, dict):
            # Assume infrastructure or governance dict
            if "score" in data:
                # Governance
                return pl.DataFrame([{"score": data["score"], "compliant": data["compliant_resources"]}])
            return pl.DataFrame([{"service": k, "count": v} for k, v in data.items()])
        return pl.DataFrame()

    def _serialize(self, df: pl.DataFrame) -> str:
        buf = io.BytesIO()
        df.write_csv(buf)
        return buf.getvalue().decode("utf-8")

    def format_cost(
        self,
        data: CostBreakdown | CostTrend,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        return self._serialize(self._to_df(data))

    def format_anomalies(
        self,
        data: AnomalyReport,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        return self._serialize(self._to_df(data))

    def format_forecast(
        self,
        data: ForecastResult,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        return self._serialize(self._to_df(data))

    def format_infrastructure(
        self,
        data: dict[str, int],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        return self._serialize(self._to_df(data))

    def format_governance(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        return self._serialize(self._to_df(data))

    def format_full(
        self, data: FullReport, metadata: ReportMetadata | None = None, config: ReportConfig | None = None
    ) -> str:
        return "Comprehensive report not supported in CSV yet."


class MarkdownFormatter(ReportFormatter):
    """Markdown formatter for documentation-ready reports."""

    def format_cost(
        self,
        data: CostBreakdown | CostTrend,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
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

    def format_anomalies(
        self,
        data: AnomalyReport,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
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

    def format_forecast(
        self,
        data: ForecastResult,
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
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

    def format_infrastructure(
        self,
        data: dict[str, int],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        lines = ["# Infrastructure Inventory", "", "| Service | Resource Count |", "|---------|----------------|"]
        for svc, count in sorted(data.items()):
            lines.append(f"| {svc.upper()} | {count} |")
        return "\n".join(lines)

    def format_governance(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata | None = None,
        config: ReportConfig | None = None,
        pdf: Any = None,
    ) -> str:
        lines = ["# Governance & Compliance", "", f"**Compliance Score:** {data.get('score', 0):.1f}%", ""]
        lines.extend(["| Metric | Value |", "|--------|-------|"])
        lines.append(f"| Compliant Resources | {data.get('compliant_resources', 0)} |")
        lines.append(f"| Non-Compliant Resources | {data.get('non_compliant_resources', 0)} |")
        return "\n".join(lines)

    def format_full(
        self, data: FullReport, metadata: ReportMetadata | None = None, config: ReportConfig | None = None
    ) -> str:
        parts = []
        if data.cost_breakdown:
            parts.append(self.format_cost(data.cost_breakdown, metadata, config=config))
        if data.anomalies:
            parts.append(self.format_anomalies(data.anomalies, metadata, config=config))
        if data.forecast:
            parts.append(self.format_forecast(data.forecast, metadata, config=config))
        if data.infrastructure_summary:
            parts.append(self.format_infrastructure(data.infrastructure_summary, metadata, config=config))
        if data.governance:
            parts.append(self.format_governance(data.governance, metadata, config=config))
        return "\n\n\n".join(parts)


class ReportService:
    """Orchestrates report generation using the Strategy pattern."""

    _formatters: ClassVar[dict[str, ReportFormatter]] = {
        "pdf": PDFFormatter(),
        "excel": ExcelFormatter(),
        "csv": FastTableFormatter(format="csv"),
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
            content = formatter.format_cost(data, metadata, config=config)
        elif isinstance(data, AnomalyReport):
            content = formatter.format_anomalies(data, metadata, config=config)
        elif isinstance(data, ForecastResult):
            content = formatter.format_forecast(data, metadata, config=config)
        elif isinstance(data, FullReport):
            content = formatter.format_full(data, metadata, config=config)
        elif isinstance(data, dict):
            content = formatter.format_infrastructure(data, metadata, config=config)
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
