"""Anomaly panel widget — displays and interacts with cost anomalies."""

from __future__ import annotations

from typing import ClassVar

from textual.containers import Vertical, VerticalScroll
from textual.widgets import DataTable, Label, Static

from remora.schemas.anomaly import Anomaly, AnomalyReport


class SeverityBadge(Static):
    """Colored badge for anomaly severity."""

    DEFAULT_CSS = """
    SeverityBadge {
        padding: 0 1;
        margin: 0 1;
    }
    """

    COLOR_MAP: ClassVar[dict[str, str]] = {
        "low": "#3fb950",
        "medium": "#d29922",
        "high": "#f85149",
        "critical": "#ff6b6b",
    }

    def __init__(self, severity: str) -> None:
        super().__init__()
        self._severity = severity
        self._color = self.COLOR_MAP.get(severity, "#8b949e")

    def on_mount(self) -> None:
        color = self._color
        self.update(f"[{color}][ {self._severity.upper()} ][/{color}]")


class AnomalyDetailCard(Vertical):
    """Expanded detail view for a single anomaly."""

    DEFAULT_CSS = """
    AnomalyDetailCard {
        background: #161b22;
        border: solid #30363d;
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

        self.mount(
            Label(f"[bold]Anomaly:[/] {a.id}"),
            Label(f"[bold]Service:[/] {a.top_root_cause or 'Unknown'}"),
            Label(f"[bold]Period:[/] {a.start_date} → {a.end_date or 'ongoing'}"),
            Label(f"[bold]Actual Spend:[/] [green]${a.impact.total_actual_spend:,.2f}[/]"),
            Label(f"[bold]Expected Spend:[/] [yellow]${a.impact.total_expected_spend:,.2f}[/]"),
            Label(f"[bold]Variance:[/] [red]{a.variance_percentage:.1f}%[/]"),
            Label(f"[bold]Root Causes:[/] {root_cause_str}"),
        )


class AnomalyPanel(VerticalScroll):
    """Main anomaly panel — list + detail view."""

    DEFAULT_CSS = """
    AnomalyPanel {
        background: #0d1117;
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
        """Display anomaly summary."""
        if not self._report:
            self.mount(Label("[dim]No anomaly data loaded[/]"))
            return

        r = self._report
        self.mount(Label(f"[bold]{r.total_anomalies} anomalies detected[/]"))

        if r.total_anomalies == 0:
            self.mount(Label("[green]No anomalies in this period[/]"))
            return

        # Severity breakdown
        by_severity = ", ".join(
            f"{sev.value.upper()}: {count}"
            for sev, count in sorted(
                r.by_severity.items(),
                key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}[x[0].value],
            )
        )
        self.mount(Label(f"[dim]By severity: {by_severity}[/]"))
        self.mount(Label(""))

        # Anomaly table
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

            table.add_row(
                f"[{sev_color}]{a.severity.value.upper()}[/{sev_color}]",
                a.top_root_cause or "Unknown",
                f"[red]{a.variance_percentage:.1f}%[/]",
                f"${a.impact.total_actual_spend:,.2f}",
                f"${a.impact.total_expected_spend:,.2f}",
                key=a.id,
            )

        self.mount(table)

    def update_report(self, report: AnomalyReport) -> None:
        """Update with new anomaly data."""
        self._report = report
        self._anomalies = report.anomalies
        # Clear and refresh
        self.remove_children()
        self._display_summary()

    def filter_by_severity(self, severity: str) -> list[Anomaly]:
        """Filter displayed anomalies by severity."""
        filtered = [a for a in self._anomalies if a.severity.value == severity.lower()]
        return filtered
