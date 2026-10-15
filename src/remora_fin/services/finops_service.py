"""Local persistence and calculations for FinOps planning features."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from remora_fin.schemas import (
    Alert,
    AlertStatus,
    AllocationEntry,
    Budget,
    BudgetCheck,
    BudgetScope,
    BudgetStatus,
    HistorySnapshot,
    RecommendationRecord,
    RecommendationState,
)


class FinOpsLocalStore:
    """Store non-cache FinOps state in a small set of local JSON files."""

    def __init__(self, directory: Path | None = None) -> None:
        configured = os.getenv("REMORA_DATA_DIR")
        if directory is not None:
            self.directory = directory
        elif configured:
            self.directory = Path(configured)
        else:
            self.directory = Path.home() / ".remora" / "data"
        self.directory.mkdir(parents=True, exist_ok=True)

    def _read(self, name: str, default: Any) -> Any:
        path = self.directory / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, name: str, value: Any) -> None:
        path = self.directory / name
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        temp.replace(path)

    def list_budgets(self) -> list[Budget]:
        return [Budget.model_validate(item) for item in self._read("budgets.json", [])]

    def save_budget(self, budget: Budget) -> Budget:
        budgets = [item for item in self.list_budgets() if item.id != budget.id]
        budgets.append(budget)
        self._write("budgets.json", [item.model_dump(mode="json") for item in budgets])
        return budget

    def list_history(self) -> list[HistorySnapshot]:
        return [HistorySnapshot.model_validate(item) for item in self._read("history.json", [])]

    def save_snapshot(self, snapshot: HistorySnapshot) -> HistorySnapshot:
        snapshots = [item for item in self.list_history() if item.captured_at != snapshot.captured_at]
        snapshots.append(snapshot)
        self._write("history.json", [item.model_dump(mode="json") for item in snapshots[-365:]])
        return snapshot

    def list_alerts(self, active_only: bool = False) -> list[Alert]:
        alerts = [Alert.model_validate(item) for item in self._read("alerts.json", [])]
        return [item for item in alerts if item.status == AlertStatus.ACTIVE] if active_only else alerts

    def save_alert(self, alert: Alert) -> Alert:
        alerts = [item for item in self.list_alerts() if item.id != alert.id]
        alerts.append(alert)
        self._write("alerts.json", [item.model_dump(mode="json") for item in alerts[-1000:]])
        return alert

    def acknowledge_alert(self, alert_id: str) -> Alert | None:
        alert = next((item for item in self.list_alerts() if item.id == alert_id), None)
        if alert is None:
            return None
        updated = alert.model_copy(update={"status": AlertStatus.ACKNOWLEDGED})
        return self.save_alert(updated)

    def list_recommendation_records(self) -> list[RecommendationRecord]:
        return [RecommendationRecord.model_validate(item) for item in self._read("recommendations.json", [])]

    def save_recommendation_record(self, record: RecommendationRecord) -> RecommendationRecord:
        records = [
            item for item in self.list_recommendation_records() if item.recommendation_id != record.recommendation_id
        ]
        records.append(record)
        self._write("recommendations.json", [item.model_dump(mode="json") for item in records])
        return record

    def update_recommendation(
        self,
        recommendation_id: str,
        state: RecommendationState,
        owner: str | None = None,
        note: str | None = None,
    ) -> RecommendationRecord:
        existing = next(
            (item for item in self.list_recommendation_records() if item.recommendation_id == recommendation_id), None
        )
        now = datetime.now()
        record = RecommendationRecord(
            recommendation_id=recommendation_id,
            state=state,
            owner=owner if owner is not None else existing.owner if existing else None,
            note=note if note is not None else existing.note if existing else None,
            first_seen=existing.first_seen if existing else now,
            last_seen=now,
        )
        return self.save_recommendation_record(record)

    def check_budgets(
        self,
        actual_by_scope: dict[tuple[BudgetScope, str], Decimal],
        period: str,
    ) -> list[BudgetCheck]:
        checks: list[BudgetCheck] = []
        for budget in self.list_budgets():
            actual = actual_by_scope.get((budget.scope, budget.target), Decimal("0"))
            status = (
                BudgetStatus.EXCEEDED
                if actual >= budget.monthly_limit
                else (
                    BudgetStatus.WARNING
                    if actual >= budget.monthly_limit * budget.warning_percent / 100
                    else BudgetStatus.HEALTHY
                )
            )
            checks.append(BudgetCheck(budget=budget, period=period, actual=actual, status=status))
        return checks

    @staticmethod
    def alert_id(kind: str, title: str) -> str:
        return hashlib.sha256(f"{kind}:{title}".encode()).hexdigest()[:16]

    def create_alert(self, kind: str, severity: str, title: str, detail: str) -> Alert:
        fingerprint = self.alert_id(kind, title)
        existing = next(
            (
                item
                for item in self.list_alerts()
                if item.fingerprint == fingerprint and item.status == AlertStatus.ACTIVE
            ),
            None,
        )
        if existing:
            return existing
        return self.save_alert(
            Alert(
                id=fingerprint,
                kind=kind,
                severity=severity,
                title=title,
                detail=detail,
                created_at=datetime.now(),
                fingerprint=fingerprint,
            )
        )

    @staticmethod
    def allocate_by_service(groups: list[tuple[str, Decimal]], total: Decimal) -> list[AllocationEntry]:
        return [
            AllocationEntry(
                key=key or "Unallocated",
                cost=cost,
                percentage=(cost / total * 100).quantize(Decimal("0.01")) if total else Decimal("0"),
                assigned=bool(key),
                source="Cost Explorer SERVICE",
            )
            for key, cost in groups
        ]
