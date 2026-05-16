"""Anomaly Service — AWS native anomaly detection + local enrichment.

Design Patterns: Repository + Facade + Chain of Responsibility
PRIMARY data source: AWS native get_anomalies() API.
LOCAL enrichments: severity classification, type categorization, trend analysis.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, cast

from remora.schemas.anomaly import (
    Anomaly,
    AnomalyFeedback,
    AnomalyImpact,
    AnomalyReport,
    AnomalyRootCause,
    AnomalyScore,
    AnomalySeverity,
    AnomalyType,
)
from remora.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)


class AnomalyService:
    """Repository for AWS Cost Explorer anomaly data.

    Uses AWS NATIVE get_anomalies() as PRIMARY source.
    Local computation adds: severity, type, trending.
    """

    def __init__(self, session: AWSSession | None = None) -> None:
        self._session = session or AWSSession.get_instance()

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

    def _parse_anomaly(self, raw: dict[str, Any]) -> Anomaly:
        """Parse a single raw anomaly from AWS API into schema."""
        # Parse root causes (native)
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

        # Parse score (native)
        score_data = raw.get("AnomalyScore", {})
        score = AnomalyScore(
            max_score=score_data.get("MaxScore", 0.0),
            current_score=score_data.get("CurrentScore", 0.0),
        )

        # Parse impact (native)
        impact_data = raw.get("Impact", {})
        impact = AnomalyImpact(
            max_impact=Decimal(impact_data.get("MaxImpact", "0")),
            total_impact=Decimal(impact_data.get("TotalImpact", "0")),
            total_actual_spend=Decimal(impact_data.get("TotalActualSpend", "0")),
            total_expected_spend=Decimal(impact_data.get("TotalExpectedSpend", "0")),
            total_impact_percentage=float(impact_data.get("TotalImpactPercentage", 0.0)),
        )

        # LOCAL: classify severity
        severity = AnomalySeverity.from_percentage(impact.total_impact_percentage)

        # LOCAL: classify type
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

        # Check for new service pattern
        if len(services) == 1:
            return AnomalyType.SPIKE

        return AnomalyType.UNKNOWN

    # -- Public API --

    def fetch_anomalies(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
    ) -> list[Anomaly]:
        """Fetch all anomalies for a period using AWS native API."""
        pages = self._fetch_all_pages(start, end, monitor_arn)
        anomalies = []
        for page in pages:
            for raw in page.get("Anomalies", []):
                try:
                    anomaly = self._parse_anomaly(raw)
                    anomalies.append(anomaly)
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse anomaly: %s", e)

        logger.info("Parsed %d anomalies", len(anomalies))
        return anomalies

    def get_anomaly_summary(
        self,
        start: date,
        end: date,
        monitor_arn: str | None = None,
    ) -> AnomalyReport:
        """Fetch anomalies and build aggregated report."""
        anomalies = self.fetch_anomalies(start, end, monitor_arn)

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
        from datetime import timedelta

        end = date.today()
        start = end - timedelta(days=90)  # AWS keeps anomalies for 90 days

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
        """Create a new anomaly monitor via native API.

        Returns: MonitorArn
        """
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
