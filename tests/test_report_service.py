from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from remora_fin.schemas.common import DateRange
from remora_fin.schemas.cost import CostBreakdown, CostGroup, CostSummary
from remora_fin.schemas.report import FullReport, ReportConfig, ReportFormat, ReportMetadata
from remora_fin.services.report_service import ReportService


@pytest.fixture
def report_service() -> ReportService:
    return ReportService()


@pytest.fixture
def mock_cost_breakdown() -> CostBreakdown:
    return CostBreakdown(
        period=DateRange(start=date(2023, 1, 1), end=date(2023, 1, 31)),
        granularity="DAILY",
        groups=[
            CostGroup(key="AmazonEC2", cost=Decimal("100.00"), usage_quantity=Decimal("10.0"), percentage=50.0),
            CostGroup(key="AmazonS3", cost=Decimal("100.00"), usage_quantity=Decimal("5.0"), percentage=50.0),
        ],
        summary=CostSummary(
            total_cost=Decimal("200.00"),
            daily_average=Decimal("6.45"),
            top_service="AmazonEC2",
            max_daily_cost=Decimal("10.00"),
            min_daily_cost=Decimal("2.00"),
            num_services=2,
            num_accounts=1,
        ),
        entries=[],
    )


@pytest.fixture
def report_metadata() -> ReportMetadata:
    return ReportMetadata(
        period=DateRange(start=date(2023, 1, 1), end=date(2023, 1, 31)),
        account_id="123456789012",
        generated_by="test-user",
    )


def test_generate_markdown_report(
    report_service: ReportService, mock_cost_breakdown: CostBreakdown, report_metadata: ReportMetadata
) -> None:
    config = ReportConfig(format=ReportFormat.MARKDOWN)
    report = report_service.generate_report(mock_cost_breakdown, config=config, metadata=report_metadata)

    assert isinstance(report, str)
    assert "# Cost Report" in report
    assert "AmazonEC2" in report
    assert "$100.00" in report


def test_generate_csv_report(
    report_service: ReportService, mock_cost_breakdown: CostBreakdown, report_metadata: ReportMetadata
) -> None:
    config = ReportConfig(format=ReportFormat.CSV)
    report = report_service.generate_report(mock_cost_breakdown, config=config, metadata=report_metadata)

    assert isinstance(report, str)
    assert "service,cost,percentage" in report
    assert "AmazonEC2,100.0,50.0" in report


def test_generate_pdf_report(
    report_service: ReportService, mock_cost_breakdown: CostBreakdown, report_metadata: ReportMetadata
) -> None:
    # PDF generation returns bytes
    config = ReportConfig(format=ReportFormat.PDF)
    report = report_service.generate_report(mock_cost_breakdown, config=config, metadata=report_metadata)

    assert isinstance(report, bytes)
    assert report.startswith(b"%PDF")


def test_report_service_invalid_format(report_service: ReportService, mock_cost_breakdown: CostBreakdown) -> None:
    # We force an invalid format to test error handling
    config = MagicMock()
    config.format.value = "invalid"
    config.output_path = None

    with pytest.raises(ValueError, match="Unknown format: invalid"):
        report_service.generate_report(mock_cost_breakdown, config=config)


def test_generate_full_report_with_pricing(
    report_service: ReportService, mock_cost_breakdown: CostBreakdown, report_metadata: ReportMetadata
) -> None:
    data = FullReport(
        cost_breakdown=mock_cost_breakdown,
        pricing_summary={"S3 Standard (per GB)": Decimal("0.023"), "EC2 t3.medium": Decimal("0.0416")},
    )
    config = ReportConfig(format=ReportFormat.MARKDOWN)
    report = report_service.generate_report(data, config=config, metadata=report_metadata)

    assert isinstance(report, str)
    assert "# Pricing Benchmarks" in report
    assert "S3 Standard (per GB)" in report
    assert "$0.023000" in report
    assert "EC2 t3.medium" in report
