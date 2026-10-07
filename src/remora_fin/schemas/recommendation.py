"""Typed models for actionable, read-only FinOps recommendations."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RecommendationCategory(StrEnum):
    """High-level class of a recommendation."""

    COST = "cost"
    GOVERNANCE = "governance"
    HYGIENE = "hygiene"


class RecommendationSeverity(StrEnum):
    """Operational importance of a recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationConfidence(StrEnum):
    """Confidence in the evidence supporting a recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recommendation(BaseModel):
    """A single recommendation with evidence and a safe suggested action."""

    model_config = ConfigDict(frozen=True)

    id: str
    category: RecommendationCategory
    service: str
    resource_id: str
    resource_name: str | None = None
    title: str
    severity: RecommendationSeverity
    confidence: RecommendationConfidence
    evidence: list[str] = Field(default_factory=list)
    suggested_action: str
    estimated_monthly_savings: Decimal | None = Field(default=None, ge=0)
    currency: str = "USD"


class RecommendationSummary(BaseModel):
    """Ranked recommendation result for one analysis window."""

    model_config = ConfigDict(frozen=True)

    analysis_days: int = Field(ge=1)
    recommendations: list[Recommendation] = Field(default_factory=list)
    total_estimated_monthly_savings: Decimal = Field(default=Decimal("0"), ge=0)
    partial_failures: list[str] = Field(default_factory=list)

    @property
    def total_findings(self) -> int:
        return len(self.recommendations)
