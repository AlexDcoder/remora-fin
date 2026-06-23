"""Anomaly schemas — mapping to AWS Cost Explorer anomaly detection API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_percentage(cls, pct: float) -> AnomalySeverity:
        if pct < 10:
            return cls.LOW
        if pct < 25:
            return cls.MEDIUM
        if pct < 50:
            return cls.HIGH
        return cls.CRITICAL


class AnomalyType(StrEnum):
    SPIKE = "spike"
    NEW_SERVICE = "new_service"
    SEASONAL = "seasonal"
    UNKNOWN = "unknown"


class AnomalyFeedback(StrEnum):
    YES = "YES"
    NO = "NO"
    PLANNED_ACTIVITY = "PLANNED_ACTIVITY"


class AnomalyRootCause(BaseModel):
    model_config = ConfigDict(frozen=True)
    service: str
    region: str | None = None
    linked_account: str | None = None
    linked_account_name: str | None = None
    usage_type: str | None = None
    contribution: Decimal = Field(default=Decimal("0"))


class AnomalyScore(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_score: float
    current_score: float


class AnomalyImpact(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_impact: Decimal = Field(default=Decimal("0"))
    total_impact: Decimal = Field(default=Decimal("0"))
    total_actual_spend: Decimal = Field(default=Decimal("0"))
    total_expected_spend: Decimal = Field(default=Decimal("0"))
    total_impact_percentage: float = Field(default=0.0, ge=0)


class Anomaly(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    monitor_arn: str
    start_date: date
    end_date: date | None = None
    dimension_value: str
    root_causes: list[AnomalyRootCause] = Field(default_factory=list)
    score: AnomalyScore
    impact: AnomalyImpact
    feedback: AnomalyFeedback | None = None
    severity: AnomalySeverity
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    is_recurring: bool = False

    @computed_field
    def variance_percentage(self) -> float:
        if self.impact.total_expected_spend == 0:
            return 0.0
        return float(
            (self.impact.total_actual_spend - self.impact.total_expected_spend) / self.impact.total_expected_spend * 100
        )

    @computed_field
    def top_root_cause(self) -> str | None:
        if not self.root_causes:
            return None
        return max(self.root_causes, key=lambda rc: rc.contribution).service

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Anomaly ID cannot be empty")
        return v


class AnomalyReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_anomalies: int = Field(ge=0)
    by_severity: dict[AnomalySeverity, int] = Field(default_factory=dict)
    by_type: dict[AnomalyType, int] = Field(default_factory=dict)
    total_actual_impact: Decimal = Field(default=Decimal("0"))
    total_expected_without_anomalies: Decimal = Field(default=Decimal("0"))
    anomalies: list[Anomaly] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    def net_financial_impact(self) -> Decimal:
        return self.total_actual_impact - self.total_expected_without_anomalies