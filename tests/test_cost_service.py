from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl

from remora.services.cache_service import CacheService
from remora.services.cost_service import CostService


@patch("remora.services.cost_service.AWSSession")
def test_cost_service_uses_cache(mock_aws_session_class):
    mock_aws_session = MagicMock()
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    mock_cache = MagicMock(spec=CacheService)
    mock_df = pl.DataFrame({
        "unblended_cost": [10.0],
        "date": [date(2023, 1, 1)],
        "service": ["S3"],
        "account": ["123"]
    })
    mock_cache.get.return_value = mock_df

    service = CostService(session=mock_aws_session, cache=mock_cache)
    # This should hit the cache and not call AWS
    df = service._get_data({"dummy": "query"})

    assert df.shape == (1, 4)
    mock_cache.get.assert_called_once()
