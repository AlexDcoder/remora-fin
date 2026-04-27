from remora.services import ReportService, CsvFormatter, ParquetFormatter, PDFFormatter, JsonFormatter, TableFormatter, MarkdownFormatter

def test_report_service_instantiation():
    service = ReportService()
    assert service is not None

def test_formatters_exist():
    assert CsvFormatter is not None
    assert ParquetFormatter is not None
    assert PDFFormatter is not None
    assert JsonFormatter is not None
    assert TableFormatter is not None
    assert MarkdownFormatter is not None

def test_report_service_formatters_registration():
    service = ReportService()
    assert "csv" in service._formatters
    assert "parquet" in service._formatters
    assert "pdf" in service._formatters
    assert "json" in service._formatters
    assert "table" in service._formatters
    assert "markdown" in service._formatters
