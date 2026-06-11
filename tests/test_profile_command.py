import argparse
from unittest.mock import ANY, MagicMock, patch

import pytest

from remora_fin.commands.profile import show_profile


@pytest.mark.asyncio
@patch("remora_fin.commands.utils.ConfigService")
@patch("remora_fin.commands.utils.AWSSession")
@patch("remora_fin.commands.utils.validate_aws_session")
@patch("remora_fin.commands.profile.ConfigService")
@patch("remora_fin.commands.profile.Console")
async def test_show_profile(
    mock_console_class: MagicMock,
    mock_profile_config_class: MagicMock,
    mock_validate_aws: MagicMock,
    mock_aws_session_class: MagicMock,
    mock_utils_config_class: MagicMock,
) -> None:
    # Setup mocks
    mock_console = MagicMock()
    mock_console_class.return_value = mock_console

    mock_settings = MagicMock()
    mock_settings.aws.profile = "test-profile"
    mock_settings.aws.region = "us-west-2"
    mock_settings.aws.role_arn = None
    mock_settings.cache.enabled = True
    mock_settings.cache.ttl_seconds = 3600
    mock_settings.ui.theme = "dark"

    # Both ConfigService calls should return mock settings
    mock_profile_config_class.return_value.settings = mock_settings
    mock_utils_config_class.return_value.settings = mock_settings

    mock_validate_aws.return_value = True

    mock_aws_session = MagicMock()
    mock_aws_session.get_caller_identity.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/test",
        "user_id": "AIDATEST",
    }
    mock_aws_session.check_billing_access.return_value = True
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    # Execute
    args = argparse.Namespace()
    args.profile = None
    args.region = None
    await show_profile(args)

    # Verify
    mock_profile_config_class.assert_called_once()
    mock_aws_session.get_caller_identity.assert_called_once()


@pytest.mark.asyncio
@patch("remora_fin.commands.utils.ConfigService")
@patch("remora_fin.commands.utils.AWSSession")
@patch("remora_fin.commands.utils.validate_aws_session")
@patch("remora_fin.commands.profile.ConfigService")
@patch("remora_fin.commands.profile.Console")
async def test_show_profile_credential_failure(
    mock_console_class: MagicMock,
    mock_profile_config_class: MagicMock,
    mock_validate_aws: MagicMock,
    mock_aws_session_class: MagicMock,
    mock_utils_config_class: MagicMock,
) -> None:
    # Setup mocks
    mock_validate_aws.return_value = False

    # Execute
    args = argparse.Namespace()
    args.profile = None
    args.region = None
    await show_profile(args)

    # Verify
    mock_validate_aws.assert_called_once()
    # Body should not be called if validation fails
    mock_profile_config_class.assert_not_called()


def test_add_profile_parser() -> None:
    from remora_fin.commands.profile import add_profile_parser

    mock_subparsers = MagicMock()
    add_profile_parser(mock_subparsers)

    mock_subparsers.add_parser.assert_called_once_with(
        "profile",
        help="View current profile and AWS identity",
        description="Displays remora-fin configuration and the active AWS caller identity.",
        formatter_class=ANY,
        parents=ANY,
    )
