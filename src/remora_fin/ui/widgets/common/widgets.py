"""Common reusable widgets for Remora TUI."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Select, Static


class LoadingIndicator(Static):
    """Loading spinner displayed during async operations."""

    DEFAULT_CSS = """
    LoadingIndicator {
        align: center middle;
        color: #00f3ff;
        text-style: bold;
    }
    LoadingIndicator .spinner {
        color: #00f3ff;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._chars = ["█", "▓", "▒", "░", "▒", "▓"]
        self._idx = 0

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        self._idx = (self._idx + 1) % len(self._chars)
        char = self._chars[self._idx]
        self.update(f"[#00f3ff]{char}[/] [bold #00f3ff]INITIALIZING DATA STREAM...[/] [#00f3ff]{char}[/]")


class ErrorBanner(Static):
    """Error message banner."""

    DEFAULT_CSS = """
    ErrorBanner {
        background: #ff450022;
        color: #ff4500;
        padding: 0 1;
        border: tall #ff4500;
        dock: top;
        text-style: bold;
    }
    """

    def show(self, message: str) -> None:
        self.update(f"⚠️ SYSTEM ERROR: {message}")
        self.display = True

    def hide(self) -> None:
        self.display = False


class KPICard(Static):
    """Key Performance Indicator card."""

    DEFAULT_CSS = """
    KPICard {
        background: #0a1931;
        border: tall #00f3ff;
        padding: 1 2;
        width: 1fr;
    }
    KPICard .kpi-label {
        color: #4b86b4;
        text-style: bold;
    }
    KPICard .kpi-value {
        color: #39ff14;
        text-style: bold;
    }
    KPICard .kpi-value.warning {
        color: #ffff00;
    }
    KPICard .kpi-value.danger {
        color: #ff4500;
        text-style: bold blink;
    }
    """

    def __init__(
        self,
        label: str,
        value: str,
        variant: str = "normal",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._label = label
        self._value = value
        self._variant = variant

    def on_mount(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        variant_class = ""
        if self._variant == "warning":
            variant_class = "warning"
        elif self._variant == "danger":
            variant_class = "danger"

        self.update(f"[kpi-label]» {self._label.upper()}[/]\n[kpi-value {variant_class}]{self._value}[/]")

    def update_value(self, value: str, variant: str | None = None) -> None:
        self._value = value
        if variant:
            self._variant = variant
        self._update_display()


class PeriodSelector(Horizontal):
    """Widget for selecting time period."""

    DEFAULT_CSS = """
    PeriodSelector {
        height: auto;
        margin: 1 0;
    }
    PeriodSelector Button {
        margin: 0 1;
        min-width: 8;
    }
    PeriodSelector Button.-active {
        background: #238636;
        color: #ffffff;
    }
    """

    PERIODS: ClassVar[list[tuple[str, int]]] = [
        ("7d", 7),
        ("30d", 30),
        ("90d", 90),
        ("180d", 180),
        ("365d", 365),
    ]

    def __init__(self, default_days: int = 30) -> None:
        super().__init__()
        self._default_days = default_days
        self.selected_days = default_days

    def compose(self) -> ComposeResult:
        for label, days in self.PERIODS:
            active = "-active" if days == self._default_days else ""
            btn = Button(label, id=f"period-{days}", classes=active)
            btn.can_focus = False
            yield btn

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("period-"):
            days = int(event.button.id.split("-")[1])
            self.selected_days = days
            # Update active button
            for btn in self.query("Button"):
                btn.set_classes("")
            event.button.set_classes("-active")
            self.post_message(self.Changed(days))

    class Changed(Message):
        def __init__(self, days: int) -> None:
            super().__init__()
            self.days = days


class FilterBar(Horizontal):
    """Filter bar for services, accounts, etc."""

    DEFAULT_CSS = """
    FilterBar {
        height: auto;
        margin: 1 0;
    }
    FilterBar Input {
        width: 1fr;
        margin: 0 1;
    }
    FilterBar Select {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Filter by service...", id="filter-service")
        yield Input(placeholder="Filter by account...", id="filter-account")
        yield Select(
            options=[
                ("All Metrics", "all"),
                ("Unblended Cost", "unblended"),
                ("Amortized Cost", "amortized"),
            ],
            value="all",
            id="filter-metric",
        )


class ExportButton(Horizontal):
    """Export button with format dropdown."""

    DEFAULT_CSS = """
    ExportButton {
        height: auto;
        margin: 1 0;
    }
    ExportButton Button {
        min-width: 10;
    }
    ExportButton Select {
        width: 12;
    }
    """

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Button("Export", id="btn-export")
        yield Select(
            options=[
                ("JSON", "json"),
                ("CSV", "csv"),
                ("Markdown", "markdown"),
                ("Table", "table"),
            ],
            value="json",
            id="export-format",
        )
