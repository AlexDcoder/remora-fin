"""Cost chart widget — renders cost trends using simple text-based bars."""

from __future__ import annotations

from textual.widgets import Static


class CostChartWidget(Static):
    """Chart widget for cost visualization.

    Uses a simple text-based bar chart with sparse layout.
    """

    DEFAULT_CSS = """
    CostChartWidget {
        height: auto;
        min-height: 10;
        background: #0a0a1a;
        border: tall #00f2ff;
        margin: 1 0;
        padding: 1 2;
    }
    """

    def __init__(self, title: str = "Cost Trend", id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = title
        self._dates: list[str] = []
        self._values: list[float] = []

    def update_data(self, dates: list[str], values: list[float]) -> None:
        self._dates = dates
        self._values = values
        self._render_chart()

    def _render_chart(self) -> None:
        if not self._values:
            self.update("[dim]No data available[/]")
            return

        lines: list[str] = []
        lines.append(f"[bold #00f3ff]» {self._title.upper()}[/]")
        lines.append("")

        max_val = max(self._values) if self._values else 1
        bar_width = 40

        display_dates = self._dates[-12:]
        display_values = self._values[-12:]

        for d, v in zip(display_dates, display_values):
            bar_len = int((v / max_val) * bar_width) if max_val > 0 else 0

            if v > max_val * 0.8:
                color = "#ff4500"
            elif v > max_val * 0.5:
                color = "#4b86b4"
            else:
                color = "#00f3ff"

            bar = "█" * bar_len
            glow = "░" * (bar_len // 4)

            lines.append(f"  [#e0e0ff]{d}[/]  [{color}]{bar}{glow}[/]  [bold #39ff14]${v:,.2f}[/]")
            lines.append("")

        self.update("\n".join(lines))

    def show_daily_trend(self, trend_data: list[tuple[str, float]]) -> None:
        dates = [d for d, _ in trend_data]
        values = [v for _, v in trend_data]
        self._title = "Daily Cost Trend"
        self.update_data(dates, values)

    def show_service_breakdown(self, services: list[tuple[str, float]]) -> None:
        names = [s for s, _ in services]
        values = [v for _, v in services]
        self._title = "Cost by Service"
        self.update_data(names, values)
