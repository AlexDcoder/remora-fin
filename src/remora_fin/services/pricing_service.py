"""Pricing Service — AWS Pricing API integration.

Handles fetching unit prices for AWS services and caching them locally.
The Pricing API is only available in us-east-1 and ap-south-1.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from remora_fin.schemas.pricing import AWSPrice, PricingDetail, ProductAttributes
from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PricingService(BaseService):
    """Service for querying AWS Pricing information."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        super().__init__("pricing", session, cache)

    @retry_with_backoff(max_retries=3)
    def get_products(self, service_code: str, filters: list[dict[str, str]]) -> list[PricingDetail]:
        """Fetch products from AWS Pricing API with filters."""
        query = {
            "service": "pricing",
            "method": "get_products",
            "service_code": service_code,
            "filters": sorted([f"{f['Field']}={f['Value']}" for f in filters]),
        }

        # Use cache if available
        cached = self._cache.get_json(query, max_age_hours=24)
        if cached:
            return [PricingDetail(**p) for p in cached]

        client = self._session.pricing()
        
        # Convert filters to AWS format
        aws_filters = [
            {"Type": "TERM_MATCH", "Field": f["Field"], "Value": f["Value"]}
            for f in filters
        ]

        try:
            paginator = client.get_paginator("get_products")
            details = []
            for page in paginator.paginate(ServiceCode=service_code, Filters=aws_filters):
                for price_list_str in page.get("PriceList", []):
                    # PriceList items are actually JSON strings...
                    item = json.loads(price_list_str)
                    details.append(self._parse_item(item))

            # Store in cache
            self._cache.set_json(query, [d.model_dump(mode="json") for d in details])
            return details

        except Exception as e:
            logger.error(f"Failed to fetch pricing for {service_code}: {e}")
            return []

    def _parse_item(self, item: dict[str, Any]) -> PricingDetail:
        """Parse the complex nested JSON from AWS Pricing API."""
        product = item.get("product", {})
        sku = product.get("sku", "N/A")
        attributes = product.get("attributes", {})

        prices = []
        terms = item.get("terms", {}).get("OnDemand", {})
        for term in terms.values():
            price_dimensions = term.get("priceDimensions", {})
            for dim in price_dimensions.values():
                unit_price = dim.get("pricePerUnit", {}).get("USD", "0")
                prices.append(
                    AWSPrice(
                        rate_code=dim.get("rateCode", ""),
                        description=dim.get("description", ""),
                        unit=dim.get("unit", ""),
                        price_per_unit=Decimal(str(unit_price)),
                        currency="USD",
                        effective_date=term.get("effectiveDate"),
                    )
                )

        return PricingDetail(
            sku=sku,
            attributes=ProductAttributes(
                service_code=product.get("serviceCode", ""),
                region=attributes.get("regionCode"),
                location=attributes.get("location"),
                **attributes,
            ),
            prices=prices,
        )

    def get_ec2_price(self, instance_type: str, region_code: str, operating_system: str = "Linux") -> PricingDetail | None:
        """Helper for EC2 instance pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
            {"Field": "operatingSystem", "Value": operating_system},
            {"Field": "preInstalledSw", "Value": "NA"},
            {"Field": "tenancy", "Value": "Shared"},
            {"Field": "capacitystatus", "Value": "Used"},
        ]
        results = self.get_products("AmazonEC2", filters)
        return results[0] if results else None

    def get_s3_price(self, volume_type: str, region_code: str) -> PricingDetail | None:
        """Helper for S3 storage pricing."""
        filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "volumeType", "Value": volume_type},
        ]
        results = self.get_products("AmazonS3", filters)
        return results[0] if results else None
