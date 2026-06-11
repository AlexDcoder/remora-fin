from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from remora_fin.services.pricing_service import PricingService


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pricing_service(mock_session: MagicMock) -> PricingService:
    return PricingService(session=mock_session)


def test_parse_item(pricing_service: PricingService) -> None:
    item = {
        "product": {
            "sku": "SKU123",
            "attributes": {
                "serviceCode": "AmazonEC2",
                "regionCode": "us-east-1",
                "location": "US East (N. Virginia)",
                "instanceType": "t3.medium",
            },
        },
        "terms": {
            "OnDemand": {
                "TERM1": {
                    "priceDimensions": {
                        "DIM1": {
                            "rateCode": "RATE1",
                            "description": "$0.0416 per On Demand Linux t3.medium Instance Hour",
                            "unit": "Hrs",
                            "pricePerUnit": {"USD": "0.0416000000"},
                        }
                    },
                    "effectiveDate": "2024-01-01T00:00:00Z",
                }
            }
        },
    }
    detail = pricing_service._parse_item(item)
    assert detail.sku == "SKU123"
    assert detail.attributes.service_code == "AmazonEC2"
    assert detail.attributes.region == "us-east-1"
    assert len(detail.prices) == 1
    assert detail.prices[0].price_per_unit == Decimal("0.0416")
    assert detail.on_demand_price is not None
    assert detail.on_demand_price.price_per_unit == Decimal("0.0416")


def test_get_products_cached(pricing_service: PricingService) -> None:
    with patch.object(
        pricing_service._cache,
        "get_json",
        return_value=[
            {
                "sku": "SKU_CACHED",
                "attributes": {"service_code": "AmazonS3", "region": "us-east-1"},
                "prices": [
                    {"rate_code": "R1", "description": "D1", "unit": "GB", "price_per_unit": "0.023", "currency": "USD"}
                ],
            }
        ],
    ):
        results = pricing_service.get_products("AmazonS3", [{"Field": "regionCode", "Value": "us-east-1"}])
        assert len(results) == 1
        assert results[0].sku == "SKU_CACHED"
        assert results[0].prices[0].price_per_unit == Decimal("0.023")


@patch("remora_fin.services.pricing_service.json.loads")
def test_get_products_api(mock_json_loads: MagicMock, pricing_service: PricingService, mock_session: MagicMock) -> None:
    with (
        patch.object(pricing_service._cache, "get_json", return_value=None),
        patch.object(pricing_service._cache, "set_json") as mock_set_json,
    ):
        client = MagicMock()
        mock_session.pricing.return_value = client

        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"PriceList": ['{"fake": "json"}']}]

        mock_json_loads.return_value = {
            "product": {"sku": "SKU_API", "attributes": {"serviceCode": "S1"}},
            "terms": {"OnDemand": {}},
        }

        results = pricing_service.get_products("S1", [])
        assert len(results) == 1
        assert results[0].sku == "SKU_API"
        mock_set_json.assert_called_once()


def test_get_ec2_price(pricing_service: PricingService) -> None:
    with patch.object(pricing_service, "get_products", return_value=[MagicMock()]) as mock_get_products:
        result = pricing_service.get_ec2_price("t3.medium", "us-east-1")
        assert result is not None
        mock_get_products.assert_called_once()


def test_get_lambda_price(pricing_service: PricingService) -> None:
    with patch.object(pricing_service, "get_products", side_effect=[[MagicMock()], [MagicMock()]]) as mock_get_products:
        result = pricing_service.get_lambda_price("us-east-1")
        assert "duration" in result
        assert "requests" in result
        assert mock_get_products.call_count == 2


def test_get_elb_price(pricing_service: PricingService) -> None:
    with patch.object(pricing_service, "get_products", side_effect=[[MagicMock()], [MagicMock()]]) as mock_get_products:
        result = pricing_service.get_elb_price("us-east-1", "Application")
        assert "hourly" in result
        assert "lcu" in result
        assert mock_get_products.call_count == 2


def test_get_fargate_price(pricing_service: PricingService) -> None:
    with patch.object(pricing_service, "get_products", side_effect=[[MagicMock()], [MagicMock()]]) as mock_get_products:
        result = pricing_service.get_fargate_price("us-east-1")
        assert "vcpu" in result
        assert "ram" in result
        assert mock_get_products.call_count == 2


def test_get_secrets_manager_price(pricing_service: PricingService) -> None:
    with patch.object(pricing_service, "get_products", side_effect=[[MagicMock()], [MagicMock()]]) as mock_get_products:
        result = pricing_service.get_secrets_manager_price("us-east-1")
        assert "storage" in result
        assert "api" in result
        assert mock_get_products.call_count == 2
