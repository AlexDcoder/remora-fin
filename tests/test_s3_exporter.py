from unittest.mock import MagicMock

from remora_fin.services.report_service import S3Exporter


def test_s3_upload_call() -> None:
    mock_session = MagicMock()
    mock_s3 = mock_session.s3.return_value

    exporter = S3Exporter(session=mock_session)
    url = exporter.upload("content", bucket="my-bucket", key="report.pdf")

    assert url == "s3://my-bucket/report.pdf"
    mock_s3.put_object.assert_called_once_with(Bucket="my-bucket", Key="report.pdf", Body=b"content")
