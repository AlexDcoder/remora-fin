"""Cost chart widget — renders cost trends using plotext."""

from __future__ import annotations

from textual.widgets import Static

try:
    from textual_plotext import PlotextPlot
except ImportError:
    PlotextPlot = None  # type: ignore[misc, assignment]


class CostChartWidget(Static):
    """Chart widget for cost visualization.

    Uses textual-plotext for native terminal charts.
    Falls back to text-based display if plotext unavailable.
    """

    DEFAULT_CSS = """
    CostChartWidget {
        height: 15;
        background: #0d1117;
        border: solid #30363d;
        margin: 1 0;
    }
    """

    def __init__(self, title: str = "Cost Trend") -> None:
        super().__init__()
        self._title = title
        self._dates: list[str] = []
        self._values: list[float] = []
        self._has_plotext = PlotextPlot is not None

    def update_data(self, dates: list[str], values: list[float]) -> None:
        """Update chart with new data."""
        self._dates = dates
        self._values = values
        self._render_chart()

    def _render_chart(self) -> None:
        if self._has_plotext and PlotextPlot is not None:
            self._render_plotext_chart()
        else:
            self._render_text_chart()

    def _render_plotext_chart(self) -> None:
        """Render using textual-plotext."""
        try:
            import plotext as plt

            plt.clf()
            plt.title(self._title)
            plt.date_form("Y-m-d")
            plt.plot_date(self._dates, self._values)
            plt.grid(True)

            widget = PlotextPlot()
            self.mount(widget)
            widget.refresh()
        except Exception:
            self._render_text_chart()

    def _render_text_chart(self) -> None:
        """Fallback: render as text-based table."""
        if not self._values:
            self.update("No data available")
            return

        lines = [f"[bold]{self._title}[/]", ""]

        # Simple bar chart using text
        if self._values:
            max_val = max(self._values) if self._values else 1
            bar_width = 40

            # Show last 14 days
            display_dates = self._dates[-14:]
            display_values = self._values[-14:]

            for d, v in zip(display_dates, display_values):
                bar_len = int((v / max_val) * bar_width) if max_val > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  [cyan]{d}[/] [dim]{bar}[/] [green]${v:,.2f}[/]")

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
