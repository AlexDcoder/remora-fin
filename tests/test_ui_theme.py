"""Smoke checks for the tactical Textual dashboard."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, ContentSwitcher, Label, Select, Static
from textual.widgets._select import SelectCurrent, SelectOverlay

from remora_fin.ui.app import DashboardScreen, RemoraApp
from remora_fin.ui.facade import DashboardUIData
from remora_fin.ui.styles import DARK_THEME
from remora_fin.ui.widgets.dashboard import DashboardWidget


class DashboardPreview(App[None]):
    CSS = DARK_THEME
    presses = 0

    def compose(self) -> ComposeResult:
        yield DashboardWidget(id="dashboard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-toggle":
            self.presses += 1
            self.query_one("#dashboard", DashboardWidget).toggle_view()


@pytest.mark.asyncio
async def test_dashboard_theme_and_view_toggle() -> None:
    app = DashboardPreview()
    async with app.run_test(size=(120, 40)) as pilot:
        dashboard = app.query_one("#dashboard", DashboardWidget)
        assert dashboard.query_one("#kpi-total .kpi-index", Label).content == "01"
        assert dashboard.query_one("#activity-log")

        assert await pilot.click("#view-toggle")
        assert app.presses == 1
        assert dashboard.query_one("#dashboard-content-switcher", ContentSwitcher).current == "dashboard-report-table"

        await pilot.pause(0.5)
        assert await pilot.click("#view-toggle")
        assert app.presses == 2
        assert dashboard.query_one("#dashboard-content-switcher", ContentSwitcher).current == "dashboard-chart"


@pytest.mark.asyncio
async def test_dashboard_screen_uses_tactical_theme_and_live_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFacade:
        async def get_available_services(self, days: int) -> list[str]:
            return ["S3"]

        async def get_dashboard_data(self, days: int, selected_service: str) -> DashboardUIData:
            return DashboardUIData(
                total_cost="$20.00",
                daily_avg="$1.00",
                anomaly_count=2,
                inventory="3 Res",
                status_title="Region: Global",
                status_subtitle="Comprehensive Monitoring",
                chart_data=[("2026-09-29", 20.0)],
                table_data=[("2026-09-29", "S3", "$20.00")],
            )

    monkeypatch.setattr("remora_fin.ui.app.AWSSession.get_instance", lambda **kwargs: None)
    monkeypatch.setattr("remora_fin.ui.app.UIFacade", lambda session: FakeFacade())

    app = RemoraApp()
    assert app.CSS == DARK_THEME
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)
        assert app.screen.query_one("#system-status", Label).content == "SYS: OK"
        assert app.screen.query_one("#aws-status", Label).content == "AWS: OK"
        assert app.screen.query_one("#alert-count", Label).content == "ALERTS: 02"

        assert isinstance(app.screen, DashboardScreen)
        assert [binding[0] for binding in app.BINDINGS] == ["q", "ctrl+c", "r"]

        selector = app.screen.query_one("#service-selector", Select)
        current = selector.query_one(SelectCurrent)
        assert current.styles.color.hex.lower() == "#ffffff"
        assert current.query_one("#label", Static).styles.color.hex.lower() == "#ffffff"
        assert await pilot.click(current)
        overlay = selector.query_one(SelectOverlay)
        assert overlay.display
        assert overlay.option_count == 2
        assert overlay.styles.color.hex.lower() == "#ffffff"
        assert overlay.styles.background.hex.lower() == "#16181d"
        option_style = overlay.get_component_styles("option-list--option")
        highlighted_style = overlay.get_component_styles("option-list--option-highlighted")
        assert option_style.color.hex.lower() == "#ffffff"
        assert highlighted_style.color.hex.lower() == "#0a0a0a"
        assert highlighted_style.background.hex.lower() == "#42e3f5"

        await pilot.press("down", "enter")
        assert selector.value == "S3"
