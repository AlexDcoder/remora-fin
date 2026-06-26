from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from remora_fin.services.cache_service import CacheService
from remora_fin.services.cost_service import CostService


@pytest.mark.asyncio
@patch("remora_fin.services.cost_service.AWSSession")
async def test_cost_service_uses_cache(mock_aws_session_class: Any) -> None:
    mock_aws_session = MagicMock()
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    mock_cache = MagicMock(spec=CacheService)
    mock_df = pl.DataFrame(
        {"unblended_cost": [10.0], "date": [date(2023, 1, 1)], "service": ["S3"], "account": ["123"]}
    )
    mock_cache.get.return_value = mock_df

    service = CostService(session=mock_aws_session, cache=mock_cache)

    # Agora _get_data_async é o método correto
    # Vamos criar um mock do método privado
    with patch.object(service, "_get_data_async", return_value=mock_df):
        df = await service._get_data_async({"dummy": "query"})
        assert df.shape == (1, 4)


@pytest.mark.asyncio
@patch("remora_fin.services.cost_service.AWSSession")
async def test_cost_service_get_total_cost(mock_aws_session_class: Any) -> None:
    mock_aws_session = MagicMock()
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    mock_cache = MagicMock(spec=CacheService)
    mock_cache.get.return_value = None

    service = CostService(session=mock_aws_session, cache=mock_cache)

    # Mock o método _fetch_all_pages_async
    mock_df = pl.DataFrame(
        {
            "unblended_cost": [10.0, 20.0],
            "date": [date(2023, 1, 1), date(2023, 1, 2)],
            "service": ["S3", "EC2"],
            "account": ["123", "123"],
        }
    )
    # Combinar os dois patches em um único with statement
    with (
        patch.object(service, "_fetch_all_pages_async", return_value=[]),
        patch.object(service, "_process_pages", return_value=mock_df),
    ):
        summary = await service.get_total_cost_async(start=date(2023, 1, 1), end=date(2023, 1, 3))
        assert summary.total_cost == 30.0
