"""Pricing schemas — mapping to AWS Pricing API responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AWSPrice(BaseModel):
    """A single price point for an AWS product."""

    model_config = ConfigDict(frozen=True)

    rate_code: str
    description: str
    unit: str
    price_per_unit: Decimal = Field(ge=0)
    currency: str = "USD"
    effective_date: str | None = None


class ProductAttributes(BaseModel):
    """Generic attributes for an AWS product (service-specific)."""

    model_config = ConfigDict(frozen=True, extra="allow")

    service_code: str
    region: str | None = None
    location: str | None = None


class PricingDetail(BaseModel):
    """Detailed pricing information for a specific product."""

    model_config = ConfigDict(frozen=True)

    sku: str
    attributes: ProductAttributes
    prices: list[AWSPrice]

    @property
    def on_demand_price(self) -> AWSPrice | None:
        """Find the on-demand price point if available."""
        for p in self.prices:
            if "On Demand" in p.description or "OnDemand" in p.description:
                return p
        return self.prices[0] if self.prices else None
