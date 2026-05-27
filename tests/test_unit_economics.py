from unittest.mock import MagicMock

import polars as pl

from remora_fin.services.cost_service import CostService


def test_unit_economics_calculation() -> None:
    # Use None for dependencies not needed for this logic-only test
    service = CostService(session=MagicMock(), cache=MagicMock())

    cost_df = pl.DataFrame({"date": ["2024-01-01", "2024-01-02"], "unblended_cost": [100.0, 150.0]})

    business_df = pl.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "metric_value": [10, 30],  # e.g., Active Customers
        }
    )

    result = service.get_unit_economics(cost_df, business_df)

    # 100/10 = 10.0 and 150/30 = 5.0
    assert result["cost_per_unit"].to_list() == [10.0, 5.0]
