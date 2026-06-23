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

from remora_fin.schemas import (
    DateRange,
    ForecastComparison,
    ForecastMetric,
    ForecastModel,
    ForecastPoint,
    ForecastResult,
    VarianceAnalysis,
)
from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService
from remora_fin.services.cost_service import CostService

logger = logging.getLogger(__name__)


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


class AWSCostExplorerNativeForecast(ForecastStrategy):
    """DEFAULT strategy: uses AWS native get_cost_forecast() API."""

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
            "Metric": metric.name,
            "Granularity": granularity,
        }

        if kwargs.get("filter"):
            params["Filter"] = kwargs["filter"]

        if group_by_type and group_by_key:
            params["GroupBy"] = [{"Type": group_by_type, "Key": group_by_key}]

        resp = ce.get_cost_forecast(**params)

        forecast_points = []

        for res in resp.get("ForecastResultsByTime", []):
            time_period = res.get("TimePeriod", {})
            start_str = time_period.get("Start", "")
            if not start_str:
                continue

            forecast_date = date.fromisoformat(start_str)
            amount = Decimal(res.get("MeanValue", "0"))
            point = ForecastPoint(
                date=forecast_date,
                predicted_cost=amount,
                lower_bound=Decimal(res.get("PredictionIntervalLowerBound", "0")),
                upper_bound=Decimal(res.get("PredictionIntervalUpperBound", "0")),
                is_predicted=True,
            )
            forecast_points.append(point)

        forecast_points.sort(key=lambda p: p.date)

        actual_period: DateRange | None = None
        if not historical_data.is_empty():
            actual_start = historical_data["date"].min()
            actual_end = historical_data["date"].max()
            if isinstance(actual_start, date) and isinstance(actual_end, date):
                actual_period = DateRange(
                    start=actual_start,
                    end=actual_end,
                )

        return ForecastResult(
            forecast_period=DateRange(start=start, end=end),
            actual_period=actual_period,
            metric=metric,
            granularity=granularity,
            predictions=forecast_points,
            group_by_type=group_by_type,
            group_by_key=group_by_key,
            model_used=ForecastModel.AWS_NATIVE_ARIMA,
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


class ForecastService(BaseService):
    """Cost forecasting using AWS native API + local fallbacks."""

    def __init__(
        self,
        session: AWSSession | None = None,
        cost_service: CostService | None = None,
        cache: CacheService | None = None,
    ):
        super().__init__("forecast", session, cache)
        self._cost_service = cost_service or CostService(self._session, self._cache)

    def _parse_forecast_response(self, resp: dict[str, Any]) -> list[ForecastPoint]:
        forecast_points = []
        for res in resp.get("ForecastResultsByTime", []):
            time_period = res.get("TimePeriod", {})
            start_str = time_period.get("Start", "")
            if not start_str:
                continue

            forecast_date = date.fromisoformat(start_str)
            point = ForecastPoint(
                date=forecast_date,
                predicted_cost=Decimal(res.get("MeanValue", "0")),
                lower_bound=Decimal(res.get("PredictionIntervalLowerBound", "0")),
                upper_bound=Decimal(res.get("PredictionIntervalUpperBound", "0")),
                is_predicted=True,
            )
            forecast_points.append(point)

        forecast_points.sort(key=lambda p: p.date)
        return forecast_points

    @async_retry_with_backoff(max_retries=3)
    async def get_aws_native_forecast_async(
        self,
        start: date,
        end: date,
        metric: ForecastMetric = ForecastMetric.UNBLENDED_COST,
        granularity: str = "DAILY",
        use_cache: bool = True,
    ) -> ForecastResult:
        query = {
            "service": "forecast",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "metric": metric.value,
            "granularity": granularity,
        }

        async def _fetch():
            ce_client = await self._session.async_client("ce")
            async with ce_client as ce:
                resp = await ce.get_cost_forecast(
                    TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                    Metric=metric.name,
                    Granularity=granularity,
                )

            return ForecastResult(
                forecast_period=DateRange(start=start, end=end),
                metric=metric,
                granularity=granularity,
                predictions=self._parse_forecast_response(resp),
                model_used=ForecastModel.AWS_NATIVE_ARIMA,
            )

        data = await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
        if isinstance(data, dict):
            return ForecastResult.model_validate(data)
        return data

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
        hist_start = start - timedelta(days=historical_days)
        trend = self._cost_service.get_daily_trend(hist_start, start, metric=metric.value)

        df = pl.DataFrame([{"date": p.date, "cost": p.cost} for p in trend.points])

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
        try:
            return self.get_aws_native_forecast(start, end, metric, granularity, **kwargs)
        except Exception as e:
            logger.warning("AWS native forecast failed, falling back to moving average: %s", e)

            hist_start = start - timedelta(days=60)
            trend = self._cost_service.get_daily_trend(hist_start, start, metric=metric.value)

            df = pl.DataFrame([{"date": p.date, "cost": p.cost} for p in trend.points])

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
        result = self.get_aws_native_forecast(start, end, metric)

        hist_start = start - timedelta(days=90)
        trend = self._cost_service.get_daily_trend(hist_start, start, metric=metric.value)
        costs = [float(p.cost) for p in trend.points]

        if len(costs) >= 2:
            mean = sum(costs) / len(costs)
            variance = sum((c - mean) ** 2 for c in costs) / (len(costs) - 1)
            std_dev = variance**0.5

            z = 1.96 if confidence_level >= 0.95 else 1.645

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
        trend = self._cost_service.get_daily_trend(actual_start, actual_end, forecast.metric.value)

        actual_total = sum(p.cost for p in trend.points)

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

    def scenario_analysis(
        self,
        forecast: ForecastResult,
        variations: dict[str, float],
    ) -> dict[str, ForecastResult]:
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