"""Common reusable widgets for Remora TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Label, Static


class ErrorBanner(Static):
    """Error message banner."""

    def show(self, message: str) -> None:
        self.add_class("error-banner")
        self.update(f"SYSTEM ERROR: {message}")
        self.display = True

    def hide(self) -> None:
        self.display = False


class KPICard(Container):
    """Key Performance Indicator card."""

    def __init__(
        self,
        label: str,
        value: str,
        variant: str = "normal",
        id: str | None = None,
        index: str = "",
    ) -> None:
        super().__init__(id=id, classes="kpi-card")
        self._label = label
        self._value = value
        self._variant = variant
        self._index = index

    def compose(self) -> ComposeResult:
        yield Label(self._index, classes="kpi-index")
        yield Label(self._label.upper(), classes="kpi-label")
        yield Label(self._value, classes="kpi-value")

    def _update_display(self) -> None:
        self.set_class(self._variant == "warning", "warning")
        self.set_class(self._variant == "danger", "danger")
        self.query_one(".kpi-value", Label).update(self._value)

    def on_mount(self) -> None:
        self._update_display()

    def update_value(self, value: str, variant: str | None = None) -> None:
        self._value = value
        if variant:
            self._variant = variant
        self._update_display()
