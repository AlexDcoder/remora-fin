from typing import Any
from unittest.mock import MagicMock, patch

from remora_fin.services.governance_service import GovernanceService


@patch("remora_fin.services.governance_service.AWSSession")
def test_tag_compliance_scoring(mock_session_class: Any) -> None:
    mock_session = MagicMock()
    mock_session_class.get_instance.return_value = mock_session

    # Simulate ResourceGroupsTaggingAPI response
    mock_tagging = mock_session.tagging.return_value
    mock_tagging.get_paginator.return_value.paginate.return_value = [
        {
            "ResourceTagMappingList": [
                {"ResourceARN": "arn1", "Tags": [{"Key": "Project", "Value": "X"}]},  # Compliant
                {"ResourceARN": "arn2", "Tags": []},  # Non-compliant
            ]
        }
    ]

    service = GovernanceService(session=mock_session)
    result = service.get_tag_compliance(required_tags=["Project"])

    assert result["score"] == 50.0
    assert result["total_resources"] == 2
    assert result["non_compliant_resources"] == 1
