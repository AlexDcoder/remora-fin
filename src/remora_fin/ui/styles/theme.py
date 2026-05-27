"""Theme definitions for Remora TUI."""

from __future__ import annotations

# -- Dark Theme (default) --
DARK_THEME = """
Screen {
    background: #040814;
    color: #e6f4f8;
}

#header {
    dock: top;
    height: 3;
    background: #0a1931;
    color: #00f3ff;
    text-style: bold;
    border-bottom: tall #00f3ff;
    content-align: center middle;
}

#sidebar {
    dock: left;
    width: 26;
    background: #0a1931;
    border-right: tall #00f3ff;
}

#footer {
    dock: bottom;
    height: 1;
    background: #0a1931;
    color: #4b86b4;
    text-style: italic;
    border-top: tall #00f3ff;
}

#main-content {
    background: #040814;
}

DataTable {
    background: #060e1f;
    border: tall #00f3ff;
    color: #e6f4f8;
}

DataTable > .datatable--header {
    background: #0a1931;
    color: #00f3ff;
    text-style: bold italic;
}

DataTable > .datatable--cursor {
    background: #00f3ff4d;
    color: #ffffff;
    text-style: bold;
}

DataTable > .datatable--hover {
    background: #00f3ff1a;
}

.kpi-card {
    background: #0a1931;
    border: tall #00f3ff;
    padding: 1 2;
    margin: 0 1;
}

.kpi-card .label {
    color: #4b86b4;
    text-style: bold;
}

.kpi-card .value {
    color: #39ff14;
    text-style: bold;
}

.kpi-card .value.warning {
    color: #ffff00;
}

.kpi-card .value.danger {
    color: #ff4500;
    text-style: bold blink;
}

#loading {
    align: center middle;
}

#loading Indicator {
    color: #00f3ff;
}

.error-banner {
    background: #ff450022;
    color: #ff4500;
    border: tall #ff4500;
    padding: 0 1;
}

.success-banner {
    background: #39ff1422;
    color: #39ff14;
    border: tall #39ff14;
    padding: 0 1;
}

Button {
    background: #0a1931;
    color: #00f3ff;
    border: tall #00f2ff;
    text-style: bold;
}

Button:hover {
    background: #00f3ff;
    color: #040814;
}

Button.-primary {
    background: #00f3ff;
    color: #040814;
    border: tall #e6f4f8;
}

Button.-primary:hover {
    background: #e6f4f8;
    color: #00f3ff;
}

Select {
    background: #060e1f;
    color: #00f3ff;
    border: tall #00f3ff;
}

Input {
    background: #060e1f;
    color: #00f3ff;
    border: tall #00f3ff;
}

TabbedContent > TabBar {
    background: #0a1931;
}

TabbedContent > TabBar > Tab {
    background: #060e1f;
    color: #4b86b4;
}

TabbedContent > TabBar > Tab.-active {
    background: #0a1931;
    color: #00f3ff;
    text-style: bold underline;
}

"""

# -- Light Theme --
LIGHT_THEME = """
Screen {
    background: #ffffff;
}

#header {
    dock: top;
    height: 3;
    background: #f6f8fa;
    color: #0969da;
    content-align: center middle;
}

#sidebar {
    dock: left;
    width: 24;
    background: #f6f8fa;
    border-right: solid #d0d7de;
}

#footer {
    dock: bottom;
    height: 1;
    background: #f6f8fa;
    color: #656d76;
}

#main-content {
    background: #ffffff;
}

DataTable {
    background: #ffffff;
    border: solid #d0d7de;
}

DataTable > .datatable--header {
    background: #f6f8fa;
    color: #0969da;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #eaeef2;
}

DataTable > .datatable--hover {
    background: #f6f8fa;
}

.kpi-card {
    background: #f6f8fa;
    border: solid #d0d7de;
    padding: 1 2;
    margin: 0 1;
}

.kpi-card .label {
    color: #656d76;
    text-style: dim;
}

.kpi-card .value {
    color: #1a7f37;
    text-style: bold;
}

.kpi-card .value.warning {
    color: #9a6700;
}

.kpi-card .value.danger {
    color: #cf222e;
}

Button {
    background: #f6f8fa;
    color: #24292f;
}

Button:hover {
    background: #eaeef2;
}

Button.-primary {
    background: #2da44e;
    color: #ffffff;
}

Select {
    background: #ffffff;
    color: #24292f;
    border: solid #d0d7de;
}

Input {
    background: #ffffff;
    color: #24292f;
    border: solid #d0d7de;
}

"""

# Theme map
THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


def get_theme_css(name: str = "dark") -> str:
    """Get theme CSS by name."""
    return THEMES.get(name, DARK_THEME)
