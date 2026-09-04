"""Pricing Service — AWS Pricing API integration.

Handles fetching unit prices for AWS services and caching them locally.
The Pricing API is only available in us-east-1 and ap-south-1.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, cast

from remora_fin.schemas import AWSPrice, PricingDetail, ProductAttributes
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
        query = {
            "service": "pricing",
            "method": "get_products",
            "service_code": service_code,
            "filters": sorted([f"{f['Field']}={f['Value']}" for f in filters]),
        }

        cached = self._cache.get_json(self.cache_query(query), max_age_hours=24)
        if cached:
            cached_products = cast(list[dict[str, Any]], cached)
            return [PricingDetail(**p) for p in cached_products]

        client = self._session.pricing()

        aws_filters = [{"Type": "TERM_MATCH", "Field": f["Field"], "Value": f["Value"]} for f in filters]

        try:
            paginator = client.get_paginator("get_products")
            details: list[PricingDetail] = []
            for page in paginator.paginate(ServiceCode=service_code, Filters=cast(Any, aws_filters)):
                for price_list_str in page.get("PriceList", []):
                    item = json.loads(price_list_str)
                    details.append(self._parse_item(item))

            self._cache.set_json(self.cache_query(query), [d.model_dump(mode="json") for d in details])
            return details

        except Exception as e:
            logger.error(f"Failed to fetch pricing for {service_code}: {e}")
            return []

    def _parse_item(self, item: dict[str, Any]) -> PricingDetail:
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

        attrs = attributes.copy()
        region = attrs.pop("regionCode", attrs.pop("region", None))
        location = attrs.pop("location", None)
        service_code = attrs.pop("serviceCode", product.get("serviceCode", ""))

        return PricingDetail(
            sku=sku,
            attributes=ProductAttributes(
                service_code=service_code,
                region=region,
                location=location,
                **attrs,
            ),
            prices=prices,
        )

    def get_ec2_price(
        self, instance_type: str, region_code: str, operating_system: str = "Linux"
    ) -> PricingDetail | None:
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
        filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "volumeType", "Value": volume_type},
        ]
        results = self.get_products("AmazonS3", filters)
        return results[0] if results else None

    def get_rds_price(
        self, instance_class: str, region_code: str, database_engine: str = "MySQL"
    ) -> PricingDetail | None:
        filters = [
            {"Field": "instanceType", "Value": instance_class},
            {"Field": "regionCode", "Value": region_code},
            {"Field": "databaseEngine", "Value": database_engine},
            {"Field": "deploymentOption", "Value": "Single-AZ"},
        ]
        results = self.get_products("AmazonRDS", filters)
        return results[0] if results else None

    def get_lambda_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        filters_duration = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "productFamily", "Value": "Serverless"},
            {"Field": "group", "Value": "AWS-Lambda-Duration"},
        ]
        filters_requests = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "productFamily", "Value": "Serverless"},
            {"Field": "group", "Value": "AWS-Lambda-Requests"},
        ]

        duration = self.get_products("AWSLambda", filters_duration)
        requests = self.get_products("AWSLambda", filters_requests)

        return {
            "duration": duration[0] if duration else None,
            "requests": requests[0] if requests else None,
        }

    def get_region_pricing_summary(self, region_code: str) -> dict[str, Any]:
        summary: dict[str, Any] = {}

        s3 = self.get_s3_price("Standard", region_code)
        if s3 and s3.on_demand_price:
            summary["S3 Standard (per GB)"] = s3.on_demand_price.price_per_unit

        for itype in ["t3.medium", "m5.large", "c5.xlarge"]:
            ec2 = self.get_ec2_price(itype, region_code)
            if ec2 and ec2.on_demand_price:
                summary[f"EC2 {itype} (On-Demand)"] = ec2.on_demand_price.price_per_unit

        lambda_p = self.get_lambda_price(region_code)
        duration_price = lambda_p.get("duration")
        requests_price = lambda_p.get("requests")
        if duration_price and duration_price.on_demand_price:
            summary["Lambda Duration (per GB-sec)"] = duration_price.on_demand_price.price_per_unit
        if requests_price and requests_price.on_demand_price:
            summary["Lambda Requests (per 1M)"] = requests_price.on_demand_price.price_per_unit

        rds = self.get_rds_price("db.t3.medium", region_code)
        if rds and rds.on_demand_price:
            summary["RDS t3.medium (MySQL)"] = rds.on_demand_price.price_per_unit

        return summary
