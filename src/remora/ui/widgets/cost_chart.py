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
        background: #0d1117;
        border: solid #30363d;
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
        """Update chart with new data."""
        self._dates = dates
        self._values = values
        self._render_chart()

    def _render_chart(self) -> None:
        """Render as a minimalist text-based bar chart."""
        if not self._values:
            self.update("[dim]No data available[/]")
            return

        lines: list[str] = []

        # Simple bar chart using text
        max_val = max(self._values) if self._values else 1
        bar_width = 30

        # Show last 10 days for a cleaner, sparser look
        display_dates = self._dates[-10:]
        display_values = self._values[-10:]

        for d, v in zip(display_dates, display_values):
            bar_len = int((v / max_val) * bar_width) if max_val > 0 else 0
            # Using ┃ (U+2503) for a cleaner vertical look
            bar = "┃" * bar_len
            lines.append(f"  [cyan]{d}[/]  [dim]{bar}[/]  [green]${v:,.2f}[/]")
            lines.append("")  # Sparse: add empty line between bars

        self.update("\n".join(lines))

    def show_daily_trend(self, trend_data: list[tuple[str, float]]) -> None:
        """Show daily cost trend."""
        dates = [d for d, _ in trend_data]
        values = [v for _, v in trend_data]
        self._title = "Daily Cost Trend"
        self.update_data(dates, values)

    def show_service_breakdown(self, services: list[tuple[str, float]]) -> None:
        """Show cost breakdown by service."""
        names = [s for s, _ in services]
        values = [v for _, v in services]
        self._title = "Cost by Service"
        self.update_data(names, values)
