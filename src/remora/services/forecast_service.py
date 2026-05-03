"""Forecast Service — AWS native forecast + local fallback strategies.

Design Pattern: Strategy

PRIMARY: AWS native get_cost_forecast() (ARIMA-based ML)
FALLBACKS: Linear regression, moving average, seasonal decomposition
LOCAL enhancements: confidence intervals, accuracy tracking, scenario analysis.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import polars as pl

from remora.schemas.common import DateRange
from remora.schemas.forecast import (
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)
from remora.services.aws_service import AWSSession, retry_with_backoff
from remora.services.cost_service import CostService

logger = logging.getLogger(__name__)


# -- Strategy Interface --


class ForecastStrategy(ABC):
    """Base strategy for cost forecasting."""

    @abstractmethod
    def predict(
        self,
        historical_data: pl.DataFrame,
        start: date,
        end: date,
        metric: ForecastMetric,
        **kwargs: Any,
    ) -> ForecastResult:
        """Generate a forecast."""
        ...


# -- Concrete Strategies --


class AWSCostExplorerNativeForecast(ForecastStrategy):
    """DEFAULT strategy: uses AWS native get_cost_forecast() API.

    AWS uses ARIMA-based ML. Supports up to 365 days forecast.
    """

    def __init__(self, session: AWSSession | None = None):
        self._session = session or AWSSession.get_instance()

    @retry_with_backoff(max_retries=3)
    def predict(
        self,
        historical_data: pl.DataFrame,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        granularity: str = "DAILY",
        group_by_type: str | None = None,
        group_by_key: str | None = None,
        **kwargs: Any,
    ) -> ForecastResult:
        ce = self._session.cost_explorer()

        params: dict[str, Any] = {
            "TimePeriod": {
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            "Metric": metric.value,
            "Granularity": granularity,
        }

        # Optional filter
        if kwargs.get("filter"):
            params["Filter"] = kwargs["filter"]

        # Optional group-by
        if group_by_type and group_by_key:
            params["GroupBy"] = [{"Type": group_by_type, "Key": group_by_key}]

        resp = ce.get_cost_forecast(**params)

        # Parse native forecast
        total_results = resp.get("Total", {})
        forecast_points = []

        for period_str, data in total_results.items():
            forecast_date = date.fromisoformat(period_str)
            amount = Decimal(data.get("Amount", "0"))
            is_predicted = data.get("predicted", False)

            point = ForecastPoint(
                date=forecast_date,
                predicted_cost=amount,
                is_predicted=is_predicted,
            )
            forecast_points.append(point)

        # Sort by date
        forecast_points.sort(key=lambda p: p.date)

        # Calculate actual period from historical data
        actual_period: DateRange | None = None
        if not historical_data.is_empty():
            actual_start = historical_data["date"].min()
            actual_end = historical_data["date"].max()
            if actual_start is not None and actual_end is not None:
                actual_period = DateRange(
                    start=date.fromordinal(int(actual_start)),  # type: ignore[arg-type]
                    end=date.fromordinal(int(actual_end)),  # type: ignore[arg-type]
                )

        model = ForecastModel.AWS_NATIVE_ARIMA

        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            actual_period=actual_period,
            metric=metric,
            granularity=granularity,
            predictions=forecast_points,
            group_by_type=group_by_type,
            group_by_key=group_by_key,
            model_used=model,
        )


class LinearRegressionForecast(ForecastStrategy):
    """FALLBACK strategy: simple linear regression on historical data.

    Used when AWS native forecast API is not available (permissions).
    """

    def predict(
        self,
        historical_data: pl.DataFrame,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        **kwargs: Any,
    ) -> ForecastResult:
        if historical_data.is_empty():
            raise ValueError("Historical data required for linear regression")

        # Simple linear regression using Polars
        df = historical_data.with_columns(
            pl.col("date").map_elements(lambda d: d.toordinal(), return_dtype=pl.Int64).alias("day_num")
        )

        # Get cost column
        cost_col = "unblended_cost" if "unblended_cost" in df.columns else "cost"

        day_nums = df["day_num"].to_list()
        costs = [float(c) for c in df[cost_col].to_list()]

        n = len(day_nums)
        if n < 2:
            raise ValueError("Need at least 2 data points")

        mean_x = sum(day_nums) / n
        mean_y = sum(costs) / n

        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(day_nums, costs))
        denominator = sum((x - mean_x) ** 2 for x in day_nums)

        slope = 0 if denominator == 0 else numerator / denominator
        intercept = mean_y - slope * mean_x

        # Generate forecast
        days = (end - start).days + 1
        start.toordinal()
        predictions = []

        for i in range(days):
            day = start + timedelta(days=i)
            x = day.toordinal()
            predicted = max(0, slope * x + intercept)
            predictions.append(
                ForecastPoint(
                    date=day,
                    predicted_cost=Decimal(f"{predicted:.6f}"),
                )
            )

        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            metric=metric,
            predictions=predictions,
            model_used=ForecastModel.LINEAR_REGRESSION,
        )


class MovingAverageForecast(ForecastStrategy):
    """FALLBACK: simple moving average."""

    def __init__(self, window: int = 7):
        self._window = window

    def predict(
        self,
        historical_data: pl.DataFrame,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        **kwargs: Any,
    ) -> ForecastResult:
        if historical_data.is_empty():
            raise ValueError("Historical data required for moving average")

        cost_col = "unblended_cost" if "unblended_cost" in historical_data.columns else "cost"

        # Calculate moving average
        df = historical_data.sort("date")
        ma = df.select(pl.col(cost_col).rolling_mean(window_size=self._window))
        avg_cost = ma[-1][cost_col].item() or Decimal("0")

        if isinstance(avg_cost, float):
            avg_cost = Decimal(str(avg_cost))

        days = (end - start).days + 1
        predictions = [
            ForecastPoint(
                date=start + timedelta(days=i),
                predicted_cost=avg_cost,
            )
            for i in range(days)
        ]

        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            metric=metric,
            predictions=predictions,
            model_used=ForecastModel.MOVING_AVERAGE,
        )


# -- ForecastService --


class ForecastService:
    """Cost forecasting using AWS native API + local fallbacks.

    Strategy Pattern:
      - DEFAULT: AWSCostExplorerNativeForecast (boto3 get_cost_forecast)
      - FALLBACK: LinearRegression, MovingAverage, SeasonalDecomposition
    """

    def __init__(
        self,
        session: AWSSession | None = None,
        cost_service: CostService | None = None,
    ):
        self._session = session or AWSSession.get_instance()
        self._cost_service = cost_service or CostService(session)

    def get_aws_native_forecast(
        self,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        granularity: str = "DAILY",
        group_by_type: str | None = None,
        group_by_key: str | None = None,
        historical_days: int = 90,
    ) -> ForecastResult:
        """Get forecast using AWS native ARIMA-based API."""
        # Fetch historical data for context
        hist_start = start - timedelta(days=historical_days)
        trend = self._cost_service.get_daily_trend(hist_start, start)

        # Convert to DataFrame
        df = pl.DataFrame([{"date": p.date, "unblended_cost": p.cost} for p in trend.points])

        strategy = AWSCostExplorerNativeForecast(self._session)
        return strategy.predict(
            historical_data=df,
            start=start,
            end=end,
            metric=metric,
            granularity=granularity,
            group_by_type=group_by_type,
            group_by_key=group_by_key,
        )

    def get_forecast(
        self,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        granularity: str = "DAILY",
        **kwargs: Any,
    ) -> ForecastResult:
        """Get forecast with automatic fallback to local models if AWS native fails."""
        try:
            return self.get_aws_native_forecast(start, end, metric, granularity, **kwargs)
        except Exception as e:
            logger.warning("AWS native forecast failed, falling back to moving average: %s", e)
            
            # Fetch historical data for moving average
            hist_start = start - timedelta(days=60)
            trend = self._cost_service.get_daily_trend(hist_start, start)
            
            df = pl.DataFrame([{"date": p.date, "unblended_cost": p.cost} for p in trend.points])
            
            strategy = MovingAverageForecast(window=7)
            return strategy.predict(
                historical_data=df,
                start=start,
                end=end,
                metric=metric,
            )

    def get_forecast_with_confidence(
        self,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        confidence_level: float = 0.95,
    ) -> ForecastResult:
        """Get forecast with LOCAL confidence intervals.

        AWS native gives point estimates only.
        We add confidence intervals using historical variance.
        """
        result = self.get_aws_native_forecast(start, end, metric)

        # Fetch historical data for variance calculation
        hist_start = start - timedelta(days=90)
        trend = self._cost_service.get_daily_trend(hist_start, start)
        costs = [float(p.cost) for p in trend.points]

        if len(costs) >= 2:
            # Calculate standard deviation
            mean = sum(costs) / len(costs)
            variance = sum((c - mean) ** 2 for c in costs) / (len(costs) - 1)
            std_dev = variance**0.5

            # Z-score for confidence level
            z = 1.96 if confidence_level >= 0.95 else 1.645

            # Add confidence intervals to predictions
            enhanced_predictions = []
            for p in result.predictions:
                cost = float(p.predicted_cost)
                margin = z * std_dev
                enhanced_predictions.append(
                    ForecastPoint(
                        date=p.date,
                        predicted_cost=p.predicted_cost,
                        lower_bound=Decimal(str(max(0, cost - margin))),
                        upper_bound=Decimal(str(cost + margin)),
                        confidence_level=confidence_level,
                        is_predicted=p.is_predicted,
                    )
                )

            return ForecastResult(
                forecast_period=result.forecast_period,
                actual_period=result.actual_period,
                metric=result.metric,
                granularity=result.granularity,
                predictions=enhanced_predictions,
                model_used=result.model_used,
            )

        return result

    def compare_actual_vs_predicted(
        self,
        forecast: ForecastResult,
        actual_start: date,
        actual_end: date,
    ) -> ForecastComparison:
        """Compare forecast vs actuals and compute accuracy metrics."""
        trend = self._cost_service.get_daily_trend(actual_start, actual_end, forecast.metric.value)

        actual_total = sum(p.cost for p in trend.points)

        # Get overlapping predicted points
        actual_map = {p.date: float(p.cost) for p in trend.points}
        predicted_map = {p.date: float(p.predicted_cost) for p in forecast.predictions}

        common_dates = set(actual_map.keys()) & set(predicted_map.keys())
        if not common_dates:
            return ForecastComparison(
                forecast=forecast,
                actuals_total=Decimal(str(actual_total)),
                variance_analysis=VarianceAnalysis(),
            )

        errors = []
        abs_errors = []
        pct_errors = []
        squared_errors = []
        overestimated = 0
        underestimated = 0

        for d in sorted(common_dates):
            actual = actual_map[d]
            predicted = predicted_map[d]
            error = predicted - actual
            errors.append(error)
            abs_errors.append(abs(error))
            if actual != 0:
                pct_errors.append(abs(error) / actual * 100)
            squared_errors.append(error**2)

            if error > 0:
                overestimated += 1
            elif error < 0:
                underestimated += 1

        n = len(common_dates)
        mae = Decimal(str(sum(abs_errors) / n))
        mape = sum(pct_errors) / n if pct_errors else 0.0
        rmse = Decimal(str((sum(squared_errors) / n) ** 0.5))
        bias = sum(errors) / n if n > 0 else 0.0

        analysis = VarianceAnalysis(
            mean_absolute_error=mae,
            mean_absolute_percentage_error=round(mape, 2),
            root_mean_square_error=rmse,
            overestimated_periods=overestimated,
            underestimated_periods=underestimated,
            bias=round(bias, 6),
        )

        return ForecastComparison(
            forecast=forecast,
            actuals_total=Decimal(str(actual_total)),
            variance_analysis=analysis,
        )

    def get_forecast_accuracy(
        self,
        historical_actuals: list[float],
        historical_predictions: list[float],
    ) -> float | None:
        """Calculate MAPE for historical forecast accuracy."""
        if len(historical_actuals) != len(historical_predictions):
            return None
        if not historical_actuals:
            return None

        pct_errors = []
        for actual, predicted in zip(historical_actuals, historical_predictions):
            if actual != 0:
                pct_errors.append(abs(predicted - actual) / actual * 100)

        if not pct_errors:
            return None

        return round(sum(pct_errors) / len(pct_errors), 2)

    def scenario_analysis(
        self,
        forecast: ForecastResult,
        variations: dict[str, float],
    ) -> dict[str, ForecastResult]:
        """What-if scenario analysis.

        Args:
            forecast: Base forecast
            variations: {"optimistic": -0.10, "pessimistic": 0.15, ...}

        Returns:
            Dict of scenario name → ForecastResult
        """
        scenarios = {}
        for name, pct_change in variations.items():
            new_predictions = [
                ForecastPoint(
                    date=p.date,
                    predicted_cost=p.predicted_cost * Decimal(str(1 + pct_change)),
                    is_predicted=p.is_predicted,
                )
                for p in forecast.predictions
            ]
            scenarios[name] = ForecastResult(
                forecast_period=forecast.forecast_period,
                actual_period=forecast.actual_period,
                metric=forecast.metric,
                granularity=forecast.granularity,
                predictions=new_predictions,
                model_used=forecast.model_used,
            )
        return scenarios
