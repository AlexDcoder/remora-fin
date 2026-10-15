"""Schemas for local FinOps planning, history, alerts, and allocation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BudgetScope(StrEnum):
    """Supported cost dimensions for a local budget."""

    TOTAL = "total"
    SERVICE = "service"
    ACCOUNT = "account"
    REGION = "region"
    TAG = "tag"


class BudgetStatus(StrEnum):
    """Budget health state."""

    HEALTHY = "healthy"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class Budget(BaseModel):
    """A monthly local spending target."""

    model_config = ConfigDict(frozen=True)

    id: str
    scope: BudgetScope
    target: str = "*"
    monthly_limit: Decimal = Field(gt=0)
    warning_percent: Decimal = Field(default=Decimal("80"), gt=0, le=100)
    currency: str = "USD"
    enabled: bool = True


class BudgetCheck(BaseModel):
    """Evaluated state of a budget for a calendar month."""

    model_config = ConfigDict(frozen=True)

    budget: Budget
    period: str
    actual: Decimal = Field(ge=0)
    forecast: Decimal | None = Field(default=None, ge=0)
    status: BudgetStatus

    @property
    def consumed_percent(self) -> Decimal:
        return (self.actual / self.budget.monthly_limit * 100).quantize(Decimal("0.01"))


class HistorySnapshot(BaseModel):
    """A local, reproducible cost snapshot."""

    model_config = ConfigDict(frozen=True)

    captured_at: datetime
    period_start: date
    period_end: date
    profile: str
    account_id: str
    region: str
    total_cost: Decimal = Field(ge=0)
    by_service: dict[str, Decimal] = Field(default_factory=dict)
    forecast: Decimal | None = Field(default=None, ge=0)
    anomaly_count: int = Field(default=0, ge=0)


class AlertStatus(StrEnum):
    """Local alert lifecycle state."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"


class Alert(BaseModel):
    """A local FinOps alert generated from evidence."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    severity: str
    title: str
    detail: str
    created_at: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    fingerprint: str


class AllocationEntry(BaseModel):
    """Cost assigned to a business owner or classification."""

    model_config = ConfigDict(frozen=True)

    key: str
    cost: Decimal = Field(ge=0)
    percentage: Decimal = Field(ge=0, le=100)
    assigned: bool
    source: str


class RecommendationState(StrEnum):
    """Review state for a persisted recommendation."""

    NEW = "new"
    REVIEWING = "reviewing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    IGNORED = "ignored"


class RecommendationRecord(BaseModel):
    """Persisted lifecycle metadata for a recommendation."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: str
    state: RecommendationState = RecommendationState.NEW
    owner: str | None = None
    note: str | None = None
    first_seen: datetime
    last_seen: datetime
