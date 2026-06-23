"""Commands package — CLI commands for Remora-Fin.

This package contains all command implementations and their argument parsers.
"""

# Command functions
from remora_fin.commands.anomalies import anomalies
from remora_fin.commands.cache import cache_cmd
from remora_fin.commands.dashboard import dashboard
from remora_fin.commands.forecast import forecast_cmd
from remora_fin.commands.login import login
from remora_fin.commands.profile import show_profile
from remora_fin.commands.report import report
from remora_fin.commands.utilization import utilization

# Parser builders
from remora_fin.commands.anomalies import add_anomalies_parser
from remora_fin.commands.cache import add_cache_parser
from remora_fin.commands.dashboard import add_dashboard_parser
from remora_fin.commands.forecast import add_forecast_parser
from remora_fin.commands.login import add_login_parser
from remora_fin.commands.profile import add_profile_parser
from remora_fin.commands.report import add_report_parser
from remora_fin.commands.utilization import add_utilization_parser

# Utilities
from remora_fin.commands.utils import (
    aws_command,
    get_common_parser,
    parse_dates,
    validate_aws_session,
)

__all__ = [
    # Command functions
    "anomalies",
    "cache_cmd",
    "dashboard",
    "forecast_cmd",
    "login",
    "show_profile",
    "report",
    "utilization",
    # Parser builders
    "add_anomalies_parser",
    "add_cache_parser",
    "add_dashboard_parser",
    "add_forecast_parser",
    "add_login_parser",
    "add_profile_parser",
    "add_report_parser",
    "add_utilization_parser",
    # Utilities
    "aws_command",
    "get_common_parser",
    "parse_dates",
    "validate_aws_session",
]