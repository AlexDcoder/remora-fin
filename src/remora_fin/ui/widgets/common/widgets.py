"""Common reusable widgets for Remora TUI."""

from __future__ import annotations

from textual.widgets import Static


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
