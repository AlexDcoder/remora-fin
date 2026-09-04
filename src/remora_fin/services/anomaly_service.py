"""Anomaly Service — AWS native anomaly detection + local enrichment.

Design Patterns: Repository + Facade + Chain of Responsibility
PRIMARY data source: AWS native get_anomalies() API.
LOCAL enrichments: severity classification, type categorization, trend analysis.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from remora_fin.schemas import (
    Anomaly,
    AnomalyFeedback,
    AnomalyImpact,
    AnomalyReport,
    AnomalyRootCause,
    AnomalyScore,
    AnomalySeverity,
    AnomalyType,
)
from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class AnomalyService(BaseService):
    """Repository for AWS Cost Explorer anomaly data.

    Uses AWS NATIVE get_anomalies() as PRIMARY source.
    Local computation adds: severity, type, trending.
    """

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        super().__init__("anomaly", session, cache)

    @retry_with_backoff(max_retries=3)
    def _fetch_all_pages(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
        feedback: AnomalyFeedback | None = None,
        min_impact: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all paginated anomaly results."""
        ce = self._session.cost_explorer()
        params: dict[str, Any] = {
            "DateInterval": {
                "StartDate": start.isoformat(),
                "EndDate": end.isoformat(),
            }
        }
        if monitor_arn:
            params["MonitorArn"] = monitor_arn
        if feedback:
            params["Feedback"] = feedback.value
        if min_impact is not None:
            params["TotalImpact"] = {
                "NumericOperator": "GREATER_THAN_OR_EQUAL",
                "StartValue": str(min_impact),
            }

        pages = self._session.fetch_token_paginated(ce.get_anomalies, **params)
        logger.info("Fetched %d anomaly pages", len(pages))
        return pages

    @async_retry_with_backoff(max_retries=3)
    async def _fetch_all_pages_async(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
        feedback: AnomalyFeedback | None = None,
        min_impact: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """Async fetch all paginated anomaly results."""
        params: dict[str, Any] = {
            "DateInterval": {
                "StartDate": start.isoformat(),
                "EndDate": end.isoformat(),
            }
        }
        if monitor_arn:
            params["MonitorArn"] = monitor_arn
        if feedback:
            params["Feedback"] = feedback.value
        if min_impact is not None:
            params["TotalImpact"] = {
                "NumericOperator": "GREATER_THAN_OR_EQUAL",
                "StartValue": str(min_impact),
            }

        async with self._session.async_client("ce") as ce:
            pages = await self._session.fetch_token_paginated_async(ce, "get_anomalies", **params)

        logger.info("Fetched %d anomaly pages (async)", len(pages))
        return pages

    def _parse_anomaly(self, raw: dict[str, Any]) -> Anomaly:
        """Parse a single raw anomaly from AWS API into schema."""
        root_causes = [
            AnomalyRootCause(
                service=rc.get("Service", "Unknown"),
                region=rc.get("Region"),
                linked_account=rc.get("LinkedAccount"),
                linked_account_name=rc.get("LinkedAccountName"),
                usage_type=rc.get("UsageType"),
                contribution=Decimal(rc.get("Impact", {}).get("Contribution", "0")),
            )
            for rc in raw.get("RootCauses", [])
        ]

        score_data = raw.get("AnomalyScore", {})
        score = AnomalyScore(
            max_score=score_data.get("MaxScore", 0.0),
            current_score=score_data.get("CurrentScore", 0.0),
        )

        impact_data = raw.get("Impact", {})
        impact = AnomalyImpact(
            max_impact=Decimal(impact_data.get("MaxImpact", "0")),
            total_impact=Decimal(impact_data.get("TotalImpact", "0")),
            total_actual_spend=Decimal(impact_data.get("TotalActualSpend", "0")),
            total_expected_spend=Decimal(impact_data.get("TotalExpectedSpend", "0")),
            total_impact_percentage=float(impact_data.get("TotalImpactPercentage", 0.0)),
        )

        severity = AnomalySeverity.from_percentage(impact.total_impact_percentage)
        anomaly_type = self._classify_type(raw.get("DimensionValue", ""), root_causes)

        return Anomaly(
            id=raw["AnomalyId"],
            monitor_arn=raw["MonitorArn"],
            start_date=date.fromisoformat(raw["AnomalyStartDate"]),
            end_date=date.fromisoformat(raw["AnomalyEndDate"]) if raw.get("AnomalyEndDate") else None,
            dimension_value=raw.get("DimensionValue", ""),
            root_causes=root_causes,
            score=score,
            impact=impact,
            feedback=AnomalyFeedback(raw["Feedback"]) if raw.get("Feedback") else None,
            severity=severity,
            anomaly_type=anomaly_type,
        )

    def _classify_type(
        self,
        dimension_value: str,
        root_causes: list[AnomalyRootCause],
    ) -> AnomalyType:
        """LOCAL classification based on root cause patterns."""
        if not root_causes:
            return AnomalyType.UNKNOWN

        services = {rc.service for rc in root_causes}

        if len(services) == 1:
            return AnomalyType.SPIKE

        return AnomalyType.UNKNOWN

    def _process_anomaly_pages(self, pages: list[dict[str, Any]]) -> list[Anomaly]:
        """Convert raw AWS response pages into a list of Anomaly models."""
        anomalies = []
        for page in pages:
            for raw in page.get("Anomalies", []):
                try:
                    anomaly = self._parse_anomaly(raw)
                    anomalies.append(anomaly)
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse anomaly: %s", e)
        return anomalies

    def fetch_anomalies(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
    ) -> list[Anomaly]:
        """Fetch all anomalies for a period using AWS native API."""
        pages = self._fetch_all_pages(start, end, monitor_arn)
        anomalies = self._process_anomaly_pages(pages)
        logger.info("Parsed %d anomalies", len(anomalies))
        return anomalies

    def get_anomaly_summary(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
        use_cache: bool = True,
    ) -> AnomalyReport:
        """Fetch anomalies and build aggregated report."""
        query = {
            "service": "anomaly",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "monitor_arn": monitor_arn,
        }

        if use_cache:
            cached_data = self._cache.get_json(self.cache_query(query))
            if cached_data:
                return AnomalyReport.model_validate(cached_data)

        anomalies = self.fetch_anomalies(start, end, monitor_arn)
        report = self._build_report(anomalies)

        if use_cache:
            self._cache.set_json(self.cache_query(query), report.model_dump(mode="json"))

        return report

    async def get_anomaly_summary_async(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
        use_cache: bool = True,
    ) -> AnomalyReport:
        """Async version of get_anomaly_summary."""
        query = {
            "service": "anomaly",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "monitor_arn": monitor_arn,
        }

        async def _fetch():
            pages = await self._fetch_all_pages_async(start, end, monitor_arn)
            anomalies = self._process_anomaly_pages(pages)
            return self._build_report(anomalies)

        data = await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)
        if isinstance(data, dict):
            return AnomalyReport.model_validate(data)
        return data

    def _build_report(self, anomalies: list[Anomaly]) -> AnomalyReport:
        """Build AnomalyReport from a list of anomalies."""
        by_severity: dict[AnomalySeverity, int] = {}
        by_type: dict[AnomalyType, int] = {}
        total_actual = Decimal("0")
        total_expected = Decimal("0")

        for a in anomalies:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            by_type[a.anomaly_type] = by_type.get(a.anomaly_type, 0) + 1
            total_actual += a.impact.total_actual_spend
            total_expected += a.impact.total_expected_spend

        return AnomalyReport(
            total_anomalies=len(anomalies),
            by_severity=by_severity,
            by_type=by_type,
            total_actual_impact=total_actual,
            total_expected_without_anomalies=total_expected,
            anomalies=anomalies,
        )

    def get_anomaly_details(self, anomaly_id: str) -> Anomaly | None:
        """Get details for a single anomaly (searches last 90 days)."""
        end = date.today()
        start = end - timedelta(days=90)

        anomalies = self.fetch_anomalies(start, end)
        for a in anomalies:
            if a.id == anomaly_id:
                return a
        return None

    def get_root_cause_analysis(self, anomaly_id: str) -> list[AnomalyRootCause]:
        """Get root cause analysis — comes directly from AWS native API."""
        anomaly = self.get_anomaly_details(anomaly_id)
        if anomaly:
            return anomaly.root_causes
        return []

    @retry_with_backoff(max_retries=3)
    def create_monitor(
        self,
        name: str,
        monitor_type: str = "DIMENSIONAL",
        dimension: str = "SERVICE",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new anomaly monitor via native API."""
        ce = self._session.cost_explorer()
        anomaly_monitor: dict[str, Any] = {
            "MonitorName": name,
            "MonitorType": monitor_type,
            "DimensionalMonitorParameters": {"MonitorDimension": dimension},
        }
        if metadata and metadata.get("specification"):
            anomaly_monitor["MonitorSpecification"] = metadata["specification"]

        resp = ce.create_anomaly_monitor(AnomalyMonitor=anomaly_monitor)  # type: ignore[arg-type]
        monitor_arn: str = resp["MonitorArn"]
        logger.info("Created anomaly monitor: %s (%s)", name, monitor_arn)
        return monitor_arn

    @retry_with_backoff(max_retries=3)
    def list_monitors(self) -> list[dict[str, Any]]:
        """List all anomaly monitors."""
        ce = self._session.cost_explorer()
        resp = ce.get_anomaly_monitors()
        monitors: list[dict[str, Any]] = cast("list[dict[str, Any]]", resp.get("AnomalyMonitors", []))
        return monitors

    @retry_with_backoff(max_retries=3)
    def delete_monitor(self, monitor_arn: str) -> None:
        """Delete an anomaly monitor."""
        ce = self._session.cost_explorer()
        ce.delete_anomaly_monitor(MonitorArn=monitor_arn)
        logger.info("Deleted anomaly monitor: %s", monitor_arn)
