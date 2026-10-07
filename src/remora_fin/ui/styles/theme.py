"""Theme definitions for the Remora Textual interface."""

from __future__ import annotations

from pathlib import Path

DARK_THEME = Path(__file__).with_name("tactical.tcss").read_text(encoding="utf-8")

# Kept for users who explicitly selected the existing light theme.
LIGHT_THEME = (
    DARK_THEME
    + """
Screen, DashboardScreen, DashboardWidget, AnomalyPanel, ForecastPanel {
    background: #ffffff;
    color: #24292f;
}
Footer { background: #f6f8fa; color: #656d76; }
.status-bar { background: #f6f8fa; border-bottom: solid #d0d7de; }
.breadcrumbs, .page-title, .section-title, .kpi-value, .log-heading { color: #24292f; }
.page-subtitle, .kpi-label, .status-context, #filter-label { color: #656d76; }
.panel, .kpi-card, AnomalyDetailCard, AccuracyMeter {
    background: #f6f8fa;
    border: solid #d0d7de;
}
.kpi-index { color: #d0d7de; }
.status-pill { background: #ffffff; color: #24292f; border: solid #d0d7de; }
.status-pill.okay { color: #1a7f37; }
.status-pill.warning { color: #9a6700; }
.status-pill.error { color: #cf222e; }
.status-pill.accent { color: #0969da; }
#service-status-header { background: #f6f8fa; border-left: solid #d0d7de; border-right: solid #d0d7de; }
Button { background: #f6f8fa; color: #24292f; border: solid #d0d7de; }
Button.primary-action, Button.-primary { background: #0969da; color: #ffffff; border: none; }
Button.primary-action:hover, Button.-primary:hover { background: #0550ae; color: #ffffff; }
Button.secondary-action:hover { background: #eaeef2; }
DataTable { background: #ffffff; color: #24292f; border: solid #d0d7de; }
DataTable > .datatable--header { background: #f6f8fa; color: #24292f; }
DataTable > .datatable--cursor { background: #0969da; color: #ffffff; }
DataTable > .datatable--hover { background: #eaeef2; }
Input { background: #ffffff; color: #24292f; border: solid #d0d7de; }
Select { color: #24292f; border: none; }
Select > SelectCurrent { background: #ffffff; color: #24292f; border: solid #d0d7de; }
Select > SelectCurrent Static#label { color: #656d76; }
Select > SelectCurrent.-has-value Static#label { color: #24292f; }
Select > SelectCurrent .arrow { color: #0969da; }
Select:focus > SelectCurrent { background: #f6f8fa; border: solid #0969da; }
Select > SelectOverlay { background: #ffffff; color: #24292f; border: solid #d0d7de; }
Select > SelectOverlay > .option-list--option { background: #ffffff; color: #24292f; }
Select > SelectOverlay > .option-list--option-highlighted,
Select > SelectOverlay:focus > .option-list--option-highlighted,
Select > SelectOverlay > .option-list--option-hover { background: #0969da; color: #ffffff; }
.log-panel, .log-stream { background: #f6f8fa; color: #24292f; }
.log-panel { border: solid #d0d7de; }
"""
)

THEMES = {"dark": DARK_THEME, "light": LIGHT_THEME}


def get_theme_css(name: str = "dark") -> str:
    """Return the selected Textual CSS, defaulting to tactical dark."""
    return THEMES.get(name, DARK_THEME)
