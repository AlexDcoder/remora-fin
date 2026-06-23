"""Commands package — CLI commands for Remora-Fin.

This package contains all command implementations and their argument parsers.
"""

# ─── Command Functions ───
# ─── Parser Builders ───
from remora_fin.commands.anomalies import add_anomalies_parser, anomalies
from remora_fin.commands.cache import add_cache_parser, cache_cmd
from remora_fin.commands.dashboard import add_dashboard_parser, dashboard
from remora_fin.commands.forecast import add_forecast_parser, forecast_cmd
from remora_fin.commands.login import add_login_parser, login
from remora_fin.commands.profile import add_profile_parser, show_profile
from remora_fin.commands.report import add_report_parser, report
from remora_fin.commands.utilization import add_utilization_parser, utilization

# ─── Utilities ───
from remora_fin.commands.utils import (
    aws_command,
    get_common_parser,
    parse_dates,
    validate_aws_session,
)

__all__ = [
    # Parser builders
    "add_anomalies_parser",
    "add_cache_parser",
    "add_dashboard_parser",
    "add_forecast_parser",
    "add_login_parser",
    "add_profile_parser",
    "add_report_parser",
    "add_utilization_parser",
    # Command functions
    "anomalies",
    # Utilities
    "aws_command",
    "cache_cmd",
    "dashboard",
    "forecast_cmd",
    "get_common_parser",
    "login",
    "parse_dates",
    "report",
    "show_profile",
    "utilization",
    "validate_aws_session",
]
