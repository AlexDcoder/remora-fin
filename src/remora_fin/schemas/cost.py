"""Cost schemas — mapping to AWS Cost Explorer API responses."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from remora_fin.schemas.common import DateRange


class CostEntry(BaseModel):
    """A single cost entry from Cost Explorer."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    date: date
    service: str
    account: str = Field(alias="linked_account")
    region: str | None = None
    usage_type: str | None = None
    resource_id: str | None = None
    unblended_cost: Decimal = Field(default=Decimal("0"), ge=0)
    blended_cost: Decimal = Field(default=Decimal("0"), ge=0)
    amortized_cost: Decimal = Field(default=Decimal("0"), ge=0)
    usage_quantity: Decimal = Field(default=Decimal("0"))
    currency: str = "USD"

    @field_validator("unblended_cost", "blended_cost", "amortized_cost", mode="before")
    @classmethod
    def clip_negative_costs(cls, v: Any) -> Any:
        if v is not None:
            try:
                dec_v = Decimal(str(v))
                if Decimal("-0.0001") < dec_v < 0:
                    return Decimal("0")
            except (ValueError, TypeError):
                pass
        return v


class CostSummary(BaseModel):
    """Aggregated cost summary."""

    model_config = ConfigDict(frozen=True)

    total_cost: Decimal = Field(ge=0)
    daily_average: Decimal = Field(ge=0)
    max_daily_cost: Decimal = Field(ge=0)
    min_daily_cost: Decimal = Field(ge=0)
    top_service: str
    top_account: str | None = None
    num_services: int = Field(ge=0)
    num_accounts: int = Field(ge=0)

    @field_validator("total_cost", "daily_average", "max_daily_cost", "min_daily_cost", mode="before")
    @classmethod
    def clip_negative_costs(cls, v: Any) -> Any:
        if v is not None:
            try:
                dec_v = Decimal(str(v))
                if Decimal("-0.0001") < dec_v < 0:
                    return Decimal("0")
            except (ValueError, TypeError):
                pass
        return v

    @computed_field
    def peak_to_average_ratio(self) -> float:
        if self.daily_average == 0:
            return 0.0
        return float(self.max_daily_cost / self.daily_average)


class CostGroup(BaseModel):
    """A group within a cost breakdown (e.g. by service or account)."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str | None = None
    cost: Decimal = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    usage_quantity: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("cost", mode="before")
    @classmethod
    def clip_negative_costs(cls, v: Any) -> Any:
        if v is not None:
            try:
                dec_v = Decimal(str(v))
                if Decimal("-0.0001") < dec_v < 0:
                    return Decimal("0")
            except (ValueError, TypeError):
                pass
        return v


class CostBreakdown(BaseModel):
    """Full cost breakdown with period and granularity."""

    model_config = ConfigDict(frozen=True)

    period: DateRange
    granularity: str
    metric: str = "UnblendedCost"
    entries: list[CostEntry] = Field(default_factory=list)
    groups: list[CostGroup] = Field(default_factory=list)
    summary: CostSummary | None = None

    @computed_field
    def total_cost(self) -> Decimal:
        if self.summary:
            return self.summary.total_cost
        return sum((e.unblended_cost for e in self.entries), Decimal("0"))


class CostTrendPoint(BaseModel):
    """A single point in a cost trend time series."""

    model_config = ConfigDict(frozen=True)

    date: date
    cost: Decimal = Field(ge=0)
    usage: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("cost", mode="before")
    @classmethod
    def clip_negative_costs(cls, v: Any) -> Any:
        if v is not None:
            try:
                dec_v = Decimal(str(v))
                if Decimal("-0.0001") < dec_v < 0:
                    return Decimal("0")
            except (ValueError, TypeError):
                pass
        return v


class CostTrend(BaseModel):
    """Time series cost trend."""

    model_config = ConfigDict(frozen=True)

    period: DateRange
    granularity: str
    metric: str
    points: list[CostTrendPoint]

    @computed_field
    def trend_direction(self) -> str:
        if len(self.points) < 2:
            return "insufficient_data"
        first_half = sum(p.cost for p in self.points[: len(self.points) // 2])
        second_half = sum(p.cost for p in self.points[len(self.points) // 2 :])
        diff = float(second_half - first_half)
        threshold = float(first_half) * 0.05
        if diff > threshold:
            return "increasing"
        if diff < -threshold:
            return "decreasing"
        return "stable"