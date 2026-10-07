"""Forecast panel widget — visualizes cost forecasts."""

from __future__ import annotations

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Label, Static

from remora_fin.schemas.forecast import ForecastResult


class AccuracyMeter(Static):
    """Visual gauge of forecast accuracy."""

    def __init__(self, accuracy: float | None = None, label: str = "ACCURACY") -> None:
        super().__init__()
        self._accuracy = accuracy
        self._label = label

    def on_mount(self) -> None:
        if self._accuracy is None:
            self.update(f"[bold #ffffff]{self._label.upper()}[/] [#6e7681]DATA UNAVAILABLE[/]")
        else:
            pct = max(0.0, min(100.0, self._accuracy * 100))
            color = "#42e3f5" if pct >= 80 else "#ffb300" if pct >= 50 else "#ff5252"
            bar_len = int(pct / 100 * 20)
            bar = "━" * bar_len
            track = "━" * (20 - bar_len)
            self.update(f"[bold #ffffff]{self._label.upper()}[/] [{color}]{bar}[/][#333742]{track}[/] {pct:.0f}%")


class ForecastPanel(VerticalScroll):
    """Panel for displaying cost forecasts."""

    def __init__(self, result: ForecastResult | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        self._result = result

    def on_mount(self) -> None:
        self._display_forecast()

    def _display_forecast(self) -> None:
        if not self._result:
            self.mount(Label("[dim]No forecast data loaded[/]"))
            return

        r = self._result

        self.mount(
            Horizontal(
                Label(f"[bold]Model:[/] {r.model_used.value}"),
                Label(f"[bold]Period:[/] {r.forecast_period.start} → {r.forecast_period.end}"),
                Label(f"[bold]Total:[/] [#ffffff]${r.total_predicted_cost:,.2f}[/]"),
                id="forecast-header",
            )
        )

        if r.accuracy_score is not None:
            self.mount(AccuracyMeter(r.accuracy_score, "Forecast Accuracy"))

        table: DataTable[str] = DataTable(id="forecast-table", cursor_background_priority="css")
        table.add_columns("Date", "Predicted Cost", "Lower Bound", "Upper Bound")
        table.cursor_type = "row"

        for p in r.predictions[:60]:
            lower = f"${p.lower_bound:,.2f}" if p.lower_bound is not None else "—"
            upper = f"${p.upper_bound:,.2f}" if p.upper_bound is not None else "—"

            marker = "(F)" if p.is_predicted else "(A)"
            table.add_row(
                f"{marker} {p.date}",
                f"${p.predicted_cost:,.2f}",
                lower,
                upper,
                key=str(p.date),
            )

        self.mount(table)

    def update_forecast(self, result: ForecastResult) -> None:
        self._result = result
        self.remove_children()
        self._display_forecast()

    def toggle_confidence_interval(self) -> None:
        pass
