"""Anomaly panel widget — displays and interacts with cost anomalies."""

from __future__ import annotations

from typing import ClassVar

from textual.containers import Vertical, VerticalScroll
from textual.widgets import DataTable, Label, Static

from remora_fin.schemas.anomaly import Anomaly, AnomalyReport


class SeverityBadge(Static):
    """Colored badge for anomaly severity."""

    DEFAULT_CSS = """
    SeverityBadge {
        padding: 0 1;
        margin: 0 1;
        text-style: bold;
    }
    """

    COLOR_MAP: ClassVar[dict[str, str]] = {
        "low": "#39ff14",
        "medium": "#ffff00",
        "high": "#4b86b4",
        "critical": "#ff4500",
    }

    def __init__(self, severity: str) -> None:
        super().__init__()
        self._severity = severity
        self._color = self.COLOR_MAP.get(severity, "#c0c0cf")

    def on_mount(self) -> None:
        color = self._color
        self.update(f"[{color}]» [ {self._severity.upper()} ] «[/{color}]")


class AnomalyDetailCard(Vertical):
    """Expanded detail view for a single anomaly."""

    DEFAULT_CSS = """
    AnomalyDetailCard {
        background: #0a1931;
        border: tall #00f3ff;
        padding: 1 2;
        margin: 1 0;
    }
    """

    def __init__(self, anomaly: Anomaly) -> None:
        super().__init__()
        self._anomaly = anomaly

    def on_mount(self) -> None:
        a = self._anomaly
        root_cause_str = ", ".join(rc.service for rc in a.root_causes[:3]) if a.root_causes else "Unknown"
        top_root_cause = a.top_root_cause
        top_cause = top_root_cause() if callable(top_root_cause) else top_root_cause or "Unknown"

        self.mount(
            Label(f"[bold #00f3ff]ANOMALY ID:[/] [#e0e0ff]{a.id}[/]"),
            Label(f"[bold #00f3ff]SERVICE:[/] [#e0e0ff]{top_cause}[/]"),
            Label(f"[bold #00f3ff]TIMELINE:[/] [#e0e0ff]{a.start_date} → {a.end_date or 'ACTIVE'}[/]"),
            Label(f"[bold #00f3ff]ACTUAL SPEND:[/] [bold #39ff14]${a.impact.total_actual_spend:,.2f}[/]"),
            Label(f"[bold #00f3ff]EXPECTED SPEND:[/] [#ffff00]${a.impact.total_expected_spend:,.2f}[/]"),
            Label(f"[bold #00f3ff]VARIANCE:[/] [bold #ff4500]{a.variance_percentage:.1f}%[/]"),
            Label(f"[bold #00f3ff]ROOT CAUSES:[/] [#e0e0ff]{root_cause_str}[/]"),
        )


class AnomalyPanel(VerticalScroll):
    """Main anomaly panel — list + detail view."""

    DEFAULT_CSS = """
    AnomalyPanel {
        background: #06060e;
    }
    """

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
            self.mount(Label("[green]No anomalies in this period[/]"))
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

        table: DataTable[str] = DataTable(id="anomaly-table")
        table.add_columns("Severity", "Service", "Variance", "Actual", "Expected")
        table.cursor_type = "row"

        for a in self._anomalies[:50]:
            sev_color = {
                "low": "green",
                "medium": "yellow",
                "high": "red",
                "critical": "bold red",
            }.get(a.severity.value, "white")

            top_root_cause = a.top_root_cause
            top_cause = top_root_cause() if callable(top_root_cause) else top_root_cause or "Unknown"

            table.add_row(
                f"[{sev_color}]{a.severity.value.upper()}[/{sev_color}]",
                top_cause or "Unknown",
                f"[red]{a.variance_percentage:.1f}%[/]",
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
