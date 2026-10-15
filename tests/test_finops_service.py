from decimal import Decimal
from pathlib import Path

from remora_fin.schemas import Budget, BudgetScope, BudgetStatus, RecommendationState
from remora_fin.services import FinOpsLocalStore


def test_budget_check_classifies_health(tmp_path: Path) -> None:
    store = FinOpsLocalStore(tmp_path)
    store.save_budget(Budget(id="total", scope=BudgetScope.TOTAL, monthly_limit=Decimal("100")))

    checks = store.check_budgets({(BudgetScope.TOTAL, "*"): Decimal("85")}, "2026-10")

    assert checks[0].status == BudgetStatus.WARNING
    assert checks[0].consumed_percent == Decimal("85.00")


def test_alerts_are_deduplicated_and_acknowledged(tmp_path: Path) -> None:
    store = FinOpsLocalStore(tmp_path)
    first = store.create_alert("budget", "high", "Over budget", "Exceeded")
    second = store.create_alert("budget", "high", "Over budget", "Exceeded")

    assert first.id == second.id
    assert len(store.list_alerts()) == 1
    assert store.acknowledge_alert(first.id) is not None
    assert store.list_alerts(active_only=True) == []


def test_recommendation_state_is_persisted(tmp_path: Path) -> None:
    store = FinOpsLocalStore(tmp_path)

    record = store.update_recommendation("rec-1", RecommendationState.ACCEPTED, owner="platform")

    assert record.state == RecommendationState.ACCEPTED
    assert record.owner == "platform"
    assert store.list_recommendation_records()[0].recommendation_id == "rec-1"


def test_service_allocation_uses_total_cost(tmp_path: Path) -> None:
    entries = FinOpsLocalStore(tmp_path).allocate_by_service(
        [("EC2", Decimal("25")), ("S3", Decimal("75"))], Decimal("100")
    )

    assert [entry.percentage for entry in entries] == [Decimal("25.00"), Decimal("75.00")]
