"""Governance Service — Tag hygiene and compliance.

This service identifies resources missing mandatory tags and provides compliance
scoring and details, along with AWS Organization account listing.
"""

from __future__ import annotations

import logging
from typing import Any

from remora_fin.services.aws_service import AWSSession

logger = logging.getLogger(__name__)


class GovernanceService:
    """Handles AWS tag compliance and resource hygiene management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize GovernanceService with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    def get_tag_compliance(self, required_tags: list[str]) -> dict[str, Any]:
        """Scan resources and evaluate compliance against a list of required tags.

        Args:
            required_tags: A list of tag keys that must be present on all resources.

        Returns:
            A dictionary containing compliance summary and detailed resource list.
        """
        tagging = self._session.tagging()
        resources = []

        paginator = tagging.get_paginator("get_resources")
        for page in paginator.paginate():
            for mapping in page.get("ResourceTagMappingList", []):
                arn = mapping["ResourceARN"]
                tags = {t["Key"]: t["Value"] for t in mapping.get("Tags", [])}

                missing = [rt for rt in required_tags if rt not in tags]
                resources.append({"arn": arn, "tags": tags, "missing_tags": missing, "is_compliant": len(missing) == 0})

        total = len(resources)
        compliant = sum(1 for r in resources if r["is_compliant"])
        score = (compliant / total * 100) if total > 0 else 100

        return {
            "score": score,
            "total_resources": total,
            "compliant_resources": compliant,
            "non_compliant_resources": total - compliant,
            "details": resources,
        }

    def list_organization_accounts(self) -> list[dict[str, str]]:
        """List all accounts within the current AWS Organization.

        Falls back to the current account if the organization cannot be accessed.

        Returns:
            A list of dictionaries, each representing an AWS account.
        """
        orgs = self._session.organizations()
        accounts = []

        try:
            paginator = orgs.get_paginator("list_accounts")
            for page in paginator.paginate():
                for acct in page.get("Accounts", []):
                    accounts.append(
                        {"id": acct["Id"], "name": acct["Name"], "email": acct["Email"], "status": acct["Status"]}
                    )
        except Exception as e:
            logger.warning("Failed to list organization accounts (falling back to current account): %s", e)
            identity = self._session.get_caller_identity()
            accounts.append({"id": identity["account"], "name": "Current Account", "email": "N/A", "status": "ACTIVE"})

        return accounts
