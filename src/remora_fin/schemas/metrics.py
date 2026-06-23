"""Metrics schemas — mapping to AWS CloudWatch responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResourceMetric(BaseModel):
    """A single metric data point."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    value: float
    unit: str = "Percent"


class MetricSummary(BaseModel):
    """Summary statistics for a metric over a period."""

    model_config = ConfigDict(frozen=True)

    metric_name: str
    resource_id: str
    unit: str
    min: float = 0.0
    max: float = 0.0
    average: float = 0.0
    p95: float = 0.0
    data_points: list[ResourceMetric] = Field(default_factory=list)

    @field_validator("data_points", mode="before")
    @classmethod
    def _validate_data_points(cls, v: Any) -> list[ResourceMetric]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

    @property
    def is_underutilized(self) -> bool:
        """Heuristic for underutilization (e.g., avg CPU < 5%)."""
        if "CPU" in self.metric_name and self.unit == "Percent":
            return self.average < 5.0
        return False