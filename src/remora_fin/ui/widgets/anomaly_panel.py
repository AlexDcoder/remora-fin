"""Anomaly panel widget — displays and interacts with cost anomalies."""

from __future__ import annotations

from typing import ClassVar

from textual.containers import Vertical, VerticalScroll
from textual.widgets import DataTable, Label, Static

from remora_fin.schemas.anomaly import Anomaly, AnomalyReport


class SeverityBadge(Static):
    """Colored badge for anomaly severity."""

    COLOR_MAP: ClassVar[dict[str, str]] = {
        "low": "#00e676",
        "medium": "#ffb300",
        "high": "#ffb300",
        "critical": "#ff5252",
    }

    def __init__(self, severity: str) -> None:
        super().__init__()
        self._severity = severity
        self._color = self.COLOR_MAP.get(severity, "#a0a8b6")

    def on_mount(self) -> None:
        color = self._color
        self.update(f"[{color}]{self._severity.upper()}[/{color}]")


class AnomalyDetailCard(Vertical):
    """Expanded detail view for a single anomaly."""

    def __init__(self, anomaly: Anomaly) -> None:
        super().__init__()
        self._anomaly = anomaly

    def on_mount(self) -> None:
        a = self._anomaly
        root_cause_str = ", ".join(rc.service for rc in a.root_causes[:3]) if a.root_causes else "Unknown"
        top_root_cause = a.top_root_cause
        top_cause = top_root_cause() if callable(top_root_cause) else top_root_cause or "Unknown"

        self.mount(
            Label(f"[bold #ffffff]ANOMALY ID:[/] [#a0a8b6]{a.id}[/]"),
            Label(f"[bold #ffffff]SERVICE:[/] [#a0a8b6]{top_cause}[/]"),
            Label(f"[bold #ffffff]TIMELINE:[/] [#a0a8b6]{a.start_date} → {a.end_date or 'ACTIVE'}[/]"),
            Label(f"[bold #ffffff]ACTUAL SPEND:[/] [bold #ffffff]${a.impact.total_actual_spend:,.2f}[/]"),
            Label(f"[bold #ffffff]EXPECTED SPEND:[/] [#a0a8b6]${a.impact.total_expected_spend:,.2f}[/]"),
            Label(f"[bold #ffffff]VARIANCE:[/] [bold #ff5252]{a.variance_percentage:.1f}%[/]"),
            Label(f"[bold #ffffff]ROOT CAUSES:[/] [#a0a8b6]{root_cause_str}[/]"),
        )


class AnomalyPanel(VerticalScroll):
    """Main anomaly panel — list + detail view."""

    def __init__(self, report: AnomalyReport | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        self._report = report
        self._anomalies: list[Anomaly] = report.anomalies if report else []
        self._selected_anomaly: Anomaly | None = None

    def on_mount(self) -> None:
        self._display_summary()

    def _display_summary(self) -> None:
        if not self._report:
            self.mount(Label("[dim]No anomaly data loaded[/]"))
            return

        r = self._report
        self.mount(Label(f"[bold]{r.total_anomalies} anomalies detected[/]"))

        if r.total_anomalies == 0:
            self.mount(Label("[#00e676]No anomalies in this period[/]"))
            return

        by_severity = ", ".join(
            f"{sev.value.upper()}: {count}"
            for sev, count in sorted(
                r.by_severity.items(),
                key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}[x[0].value],
            )
        )
        self.mount(Label(f"[dim]By severity: {by_severity}[/]"))
        self.mount(Label(""))

        table: DataTable[str] = DataTable(id="anomaly-table", cursor_background_priority="css")
        table.add_columns("Severity", "Service", "Variance", "Actual", "Expected")
        table.cursor_type = "row"

        for a in self._anomalies[:50]:
            sev_color = {
                "low": "#00e676",
                "medium": "#ffb300",
                "high": "#ffb300",
                "critical": "#ff5252",
            }.get(a.severity.value, "#a0a8b6")

            top_root_cause = a.top_root_cause
            top_cause = top_root_cause() if callable(top_root_cause) else top_root_cause or "Unknown"

            table.add_row(
                f"[{sev_color}]{a.severity.value.upper()}[/{sev_color}]",
                top_cause or "Unknown",
                f"[#ff5252]{a.variance_percentage:.1f}%[/]",
                f"${a.impact.total_actual_spend:,.2f}",
                f"${a.impact.total_expected_spend:,.2f}",
                key=a.id,
            )

        self.mount(table)

    def update_report(self, report: AnomalyReport) -> None:
        self._report = report
        self._anomalies = report.anomalies
        self.remove_children()
        self._display_summary()

    def filter_by_severity(self, severity: str) -> list[Anomaly]:
        filtered = [a for a in self._anomalies if a.severity.value == severity.lower()]
        return filtered
