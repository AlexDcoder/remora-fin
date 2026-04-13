"""Anomaly schemas — mapping to AWS Cost Explorer anomaly detection API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# -- Enums --


class AnomalySeverity(StrEnum):
    """Severity classification based on TotalImpactPercentage.

    LOCAL classification (AWS native does NOT provide severity labels):
        LOW:      < 10% variance
        MEDIUM:   10-25% variance
        HIGH:     25-50% variance
        CRITICAL: > 50% variance
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_percentage(cls, pct: float) -> AnomalySeverity:
        """Classify severity from TotalImpactPercentage."""
        if pct < 10:
            return cls.LOW
        if pct < 25:
            return cls.MEDIUM
        if pct < 50:
            return cls.HIGH
        return cls.CRITICAL


class AnomalyType(StrEnum):
    """LOCAL categorization based on root cause patterns."""

    SPIKE = "spike"  # sudden increase
    NEW_SERVICE = "new_service"  # previously unseen service
    SEASONAL = "seasonal"  # recurring seasonal pattern
    UNKNOWN = "unknown"


class AnomalyFeedback(StrEnum):
    """Maps directly to AWS native Feedback field."""

    YES = "YES"
    NO = "NO"
    PLANNED_ACTIVITY = "PLANNED_ACTIVITY"


# -- Sub-models (direct AWS native mapping) --


class AnomalyRootCause(BaseModel):
    """Root cause detail — maps directly to RootCauses[] from AWS native API.

    Fields:
        service:            RootCauses[].Service
        region:             RootCauses[].Region
        linked_account:     RootCauses[].LinkedAccount
        linked_account_name: RootCauses[].LinkedAccountName
        usage_type:         RootCauses[].UsageType
        contribution:       RootCauses[].Impact.Contribution
    """

    model_config = ConfigDict(frozen=True)

    service: str
    region: str | None = None
    linked_account: str | None = None
    linked_account_name: str | None = None
    usage_type: str | None = None
    contribution: Decimal = Field(default=Decimal("0"))


class AnomalyScore(BaseModel):
    """Anomaly score — maps directly to AnomalyScore from AWS native API."""

    model_config = ConfigDict(frozen=True)

    max_score: float
    current_score: float


class AnomalyImpact(BaseModel):
    """Impact details — maps directly to Impact from AWS native API."""

    model_config = ConfigDict(frozen=True)

    max_impact: Decimal = Field(default=Decimal("0"))
    total_impact: Decimal = Field(default=Decimal("0"))
    total_actual_spend: Decimal = Field(default=Decimal("0"))
    total_expected_spend: Decimal = Field(default=Decimal("0"))
    total_impact_percentage: float = Field(default=0.0, ge=0)


# -- Main Anomaly model --


class Anomaly(BaseModel):
    """Cost anomaly — combines AWS NATIVE fields + LOCAL enrichments.

    NATIVE fields (directly from get_anomalies API):
        id, monitor_arn, start_date, end_date, dimension_value,
        root_causes, score, impact, feedback

    LOCAL computed fields:
        severity, anomaly_type, is_recurring
    """

    model_config = ConfigDict(frozen=True)

    # --- NATIVE AWS fields ---
    id: str
    monitor_arn: str
    start_date: date
    end_date: date | None = None
    dimension_value: str
    root_causes: list[AnomalyRootCause] = Field(default_factory=list)
    score: AnomalyScore
    impact: AnomalyImpact
    feedback: AnomalyFeedback | None = None

    # --- LOCAL computed fields ---
    severity: AnomalySeverity
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    is_recurring: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variance_percentage(self) -> float:
        """Calculated from native impact fields."""
        if self.impact.total_expected_spend == 0:
            return 0.0
        return float(
            (self.impact.total_actual_spend - self.impact.total_expected_spend) / self.impact.total_expected_spend * 100
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def top_root_cause(self) -> str | None:
        """Service contributing most to the anomaly."""
        if not self.root_causes:
            return None
        return max(self.root_causes, key=lambda rc: rc.contribution).service

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Anomaly ID cannot be empty")
        return v


# -- Aggregated reports --


class AnomalyReport(BaseModel):
    """Aggregated anomaly report."""

    model_config = ConfigDict(frozen=True)

    total_anomalies: int = Field(ge=0)
    by_severity: dict[AnomalySeverity, int] = Field(default_factory=dict)
    by_type: dict[AnomalyType, int] = Field(default_factory=dict)
    total_actual_impact: Decimal = Field(default=Decimal("0"))
    total_expected_without_anomalies: Decimal = Field(default=Decimal("0"))
    anomalies: list[Anomaly] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def net_financial_impact(self) -> Decimal:
        """Total extra cost caused by anomalies."""
        return self.total_actual_impact - self.total_expected_without_anomalies
