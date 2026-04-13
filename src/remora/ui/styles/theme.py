"""Theme definitions for Remora TUI."""

from __future__ import annotations

# -- Dark Theme (default) --
DARK_THEME = """
Screen {
    background: #0a0e14;
}

#header {
    dock: top;
    height: 3;
    background: #161b22;
    color: #58a6ff;
    content-align: center middle;
}

#sidebar {
    dock: left;
    width: 24;
    background: #161b22;
    border-right: solid #30363d;
}

#footer {
    dock: bottom;
    height: 1;
    background: #161b22;
    color: #8b949e;
}

#main-content {
    background: #0a0e14;
}

DataTable {
    background: #0d1117;
    border: solid #30363d;
}

DataTable > .datatable--header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1f2937;
}

DataTable > .datatable--hover {
    background: #161b22;
}

.kpi-card {
    background: #161b22;
    border: solid #30363d;
    padding: 1 2;
    margin: 0 1;
}

.kpi-card .label {
    color: #8b949e;
    text-style: dim;
}

.kpi-card .value {
    color: #3fb950;
    text-style: bold;
}

.kpi-card .value.warning {
    color: #d29922;
}

.kpi-card .value.danger {
    color: #f85149;
}

#loading {
    align: center middle;
}

#loading Indicator {
    color: #58a6ff;
}

.error-banner {
    background: #f8514922;
    color: #f85149;
    padding: 0 1;
}

.success-banner {
    background: #3fb95022;
    color: #3fb950;
    padding: 0 1;
}

Button {
    background: #21262d;
    color: #c9d1d9;
}

Button:hover {
    background: #30363d;
}

Button.-primary {
    background: #238636;
    color: #ffffff;
}

Button.-primary:hover {
    background: #2ea043;
}

Select {
    background: #0d1117;
    color: #c9d1d9;
    border: solid #30363d;
}

Input {
    background: #0d1117;
    color: #c9d1d9;
    border: solid #30363d;
}

TabbedContent > TabBar {
    background: #161b22;
}

TabbedContent > TabBar > Tab {
    background: #0d1117;
    color: #8b949e;
}

TabbedContent > TabBar > Tab.-active {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
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
