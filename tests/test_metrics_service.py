from datetime import UTC, datetime
from unittest.mock import MagicMock

from remora_fin.services.metrics_service import MetricsService


def test_sum_statistic_is_preserved() -> None:
    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Timestamp": datetime.now(UTC), "Sum": 2.0, "Unit": "Count"},
            {"Timestamp": datetime.now(UTC), "Sum": 3.0, "Unit": "Count"},
        ]
    }
    session = MagicMock()
    session.cloudwatch.return_value = cloudwatch
    session.get_caller_identity.return_value = {"account": "123"}
    session.profile = "test"
    session.region = "us-east-1"
    cache = MagicMock()
    cache.get_json.return_value = None

    result = MetricsService(session=session, cache=cache).get_lambda_invocations("function", days=7)

    assert result is not None
    assert result.average == 2.5
    assert result.total == 5.0
    assert [point.value for point in result.data_points] == [2.0, 3.0]
