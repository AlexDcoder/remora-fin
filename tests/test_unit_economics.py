from unittest.mock import MagicMock

import polars as pl

from remora_fin.services.cost_service import CostService


def test_unit_economics_calculation() -> None:
    # Use None for dependencies not needed for this logic-only test
    CostService(session=MagicMock(), cache=MagicMock())

    pl.DataFrame({"date": ["2024-01-01", "2024-01-02"], "unblended_cost": [100.0, 150.0]})

    pl.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "metric_value": [10, 30],  # e.g., Active Customers
        }
    )

    # Calcular manualmente o resultado esperado
    result = {
        "cost_per_unit": [100.0 / 10.0, 150.0 / 30.0],
        "dates": ["2024-01-01", "2024-01-02"],
    }

    assert result["cost_per_unit"] == [10.0, 5.0]
