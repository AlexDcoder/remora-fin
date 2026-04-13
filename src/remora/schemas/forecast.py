"""Forecast schemas — wrapping AWS native get_cost_forecast + local enhancements."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from remora.schemas.common import DateRange

# -- Enums --


class ForecastMetric(StrEnum):
    """Metrics available in AWS native Cost Explorer forecast."""

    UNBLENDED_COST = "UnblendedCost"
    BLENDED_COST = "BlendedCost"
    NET_UNBLENDED_COST = "NetUnblendedCost"
    AMORTIZED_COST = "AmortizedCost"
    NET_AMORTIZED_COST = "NetAmortizedCost"
    USAGE_QUANTITY = "UsageQuantity"
    NORMALIZED_USAGE_AMOUNT = "NormalizedUsageAmount"


class ForecastModel(StrEnum):
    """Forecast model used — native AWS or local fallback."""

    AWS_NATIVE_ARIMA = "AWS_NATIVE_ARIMA"
    LINEAR_REGRESSION = "LinearRegression"
    MOVING_AVERAGE = "MovingAverage"
    SEASONAL_DECOMPOSITION = "SeasonalDecomposition"
    EXPONENTIAL_SMOOTHING = "ExponentialSmoothing"


# -- Core models --


class ForecastPoint(BaseModel):
    """A single forecast point.

    NATIVE AWS fields (from get_cost_forecast):
        predicted_cost:  Total.Amount
        predicted_usage: UsageQuantity (optional)

    LOCAL computed fields:
        lower_bound, upper_bound, confidence_level
    """

    model_config = ConfigDict(frozen=True)

    date: date
    predicted_cost: Decimal = Field(ge=0)
    predicted_usage: Decimal | None = Field(default=None, ge=0)
    # LOCAL: confidence interval (AWS native only gives point estimate)
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    confidence_level: float | None = Field(default=None, ge=0, le=1)
    is_predicted: bool = True  # True = future, False = historical actual


class ForecastResult(BaseModel):
    """Complete forecast result."""

    model_config = ConfigDict(frozen=True)

    forecast_period: DateRange
    actual_period: DateRange | None = None
    metric: ForecastMetric = ForecastMetric.UNBLENDED_COST
    granularity: str = "DAILY"
    predictions: list[ForecastPoint]
    # Optional group-by breakdown
    group_by_type: str | None = None
    group_by_key: str | None = None
    grouped_predictions: dict[str, list[ForecastPoint]] | None = None
    model_used: ForecastModel = ForecastModel.AWS_NATIVE_ARIMA
    accuracy_score: float | None = Field(default=None, ge=0, le=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_predicted_cost(self) -> Decimal:
        """Sum of all predicted costs."""
        return sum((p.predicted_cost for p in self.predictions), Decimal("0"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prediction_count(self) -> int:
        return len(self.predictions)


class VarianceAnalysis(BaseModel):
    """LOCAL computation: comparing forecast vs actuals.

    AWS native forecast does NOT provide accuracy metrics — we compute them.
    """

    model_config = ConfigDict(frozen=True)

    mean_absolute_error: Decimal = Field(default=Decimal("0"), ge=0)
    mean_absolute_percentage_error: float = Field(default=0.0, ge=0)
    root_mean_square_error: Decimal = Field(default=Decimal("0"), ge=0)
    overestimated_periods: int = Field(default=0, ge=0)
    underestimated_periods: int = Field(default=0, ge=0)
    bias: float = 0.0  # positive = tendency to overestimate


class ForecastComparison(BaseModel):
    """Comparison between forecast and actuals."""

    model_config = ConfigDict(frozen=True)

    forecast: ForecastResult
    actuals_total: Decimal = Field(default=Decimal("0"), ge=0)
    variance_analysis: VarianceAnalysis

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_variance_pct(self) -> float:
        if self.actuals_total == 0:
            return 0.0
        return float((self.forecast.total_predicted_cost - self.actuals_total) / self.actuals_total * 100)
