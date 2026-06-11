"""Unit tests for UnitEconomicsService."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from remora_fin.services.unit_economics_service import UnitEconomicsService


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.region = "us-east-1"
    return session


@pytest.fixture
def mock_inventory() -> MagicMock:
    service = MagicMock()
    service.list_resources_async = AsyncMock(
        return_value=[
            {"id": "i-1234567890abcdef0", "name": "web-server", "type": "t3.medium"},
            {"id": "i-0fedcba9876543210", "name": "db-server", "type": "m5.large"},
        ]
    )
    return service


@pytest.fixture
def mock_pricing() -> MagicMock:
    service = MagicMock()

    # Mock EC2 price
    price_detail = MagicMock()
    on_demand = MagicMock()
    on_demand.price_per_unit = Decimal("0.0416")  # t3.medium price
    price_detail.on_demand_price = on_demand

    service.get_ec2_price.return_value = price_detail
    return service


@pytest.fixture
def mock_metrics() -> MagicMock:
    service = MagicMock()

    # Mock CPU metrics
    summary = MagicMock()
    summary.average = 2.5
    summary.is_underutilized = True

    service.get_ec2_cpu_utilization.return_value = summary
    return service


@pytest.mark.asyncio
async def test_ec2_efficiency(
    mock_session: MagicMock, mock_inventory: MagicMock, mock_pricing: MagicMock, mock_metrics: MagicMock
) -> None:
    service = UnitEconomicsService(
        session=mock_session, inventory=mock_inventory, pricing=mock_pricing, metrics=mock_metrics
    )

    results = await service.get_ec2_efficiency(days=7)

    assert len(results) == 2
    assert results[0]["id"] == "i-1234567890abcdef0"
    assert results[0]["avg_cpu"] == 2.5
    assert results[0]["hourly_rate"] == Decimal("0.0416")
    assert results[0]["is_underutilized"] is True
    assert results[0]["potential_savings_7d"] > 0
