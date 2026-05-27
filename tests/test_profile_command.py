import argparse
from unittest.mock import MagicMock, patch

from remora_fin.commands.profile import show_profile


@patch("remora_fin.commands.profile.ConfigService")
@patch("remora_fin.commands.profile.AWSSession")
@patch("remora_fin.commands.profile.Console")
def test_show_profile(
    mock_console_class: MagicMock, mock_aws_session_class: MagicMock, mock_config_service_class: MagicMock
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

    mock_config_service = MagicMock()
    mock_config_service.settings = mock_settings
    mock_config_service_class.return_value = mock_config_service

    mock_aws_session = MagicMock()
    mock_aws_session.validate_credentials.return_value = True
    mock_aws_session.get_caller_identity.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/test",
        "user_id": "AIDATEST",
    }
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    # Execute
    args = argparse.Namespace()
    show_profile(args)

    # Verify
    # We check if console.print was called. Since it uses Rich, we can't easily check the exact strings
    # without deeper inspection, but we can verify the mocks were interacted with.
    mock_config_service_class.assert_called_once()
    mock_aws_session_class.get_instance.assert_called_once_with(region="us-west-2", profile="test-profile")
    mock_aws_session.validate_credentials.assert_called_once()
    mock_aws_session.get_caller_identity.assert_called_once()


@patch("remora_fin.commands.profile.ConfigService")
@patch("remora_fin.commands.profile.AWSSession")
@patch("remora_fin.commands.profile.Console")
def test_show_profile_credential_failure(
    mock_console_class: MagicMock, mock_aws_session_class: MagicMock, mock_config_service_class: MagicMock
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

    mock_config_service = MagicMock()
    mock_config_service.settings = mock_settings
    mock_config_service_class.return_value = mock_config_service

    mock_aws_session = MagicMock()
    mock_aws_session.validate_credentials.return_value = False
    mock_aws_session_class.get_instance.return_value = mock_aws_session

    # Execute
    args = argparse.Namespace()
    show_profile(args)

    # Verify
    mock_aws_session.validate_credentials.assert_called_once()
    # Ensure identity was NOT fetched
    mock_aws_session.get_caller_identity.assert_not_called()


def test_add_profile_parser() -> None:
    from unittest.mock import ANY

    from remora_fin.commands.profile import add_profile_parser

    mock_subparsers = MagicMock()
    add_profile_parser(mock_subparsers)

    mock_subparsers.add_parser.assert_called_once_with(
        "profile",
        help="View current profile and AWS identity",
        description="Displays remora-fin configuration and the active AWS caller identity.",
        formatter_class=ANY,
    )
