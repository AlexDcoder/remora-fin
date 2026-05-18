"""EC2 Service — AWS EC2 metadata and instance management.

This service provides methods to fetch EC2 instance details,
which can be used to correlate infrastructure with billing data.
"""

from __future__ import annotations

import logging
from typing import Any

from remora.services.aws_service import AWSSession, retry_with_backoff

logger = logging.getLogger(__name__)


class EC2Service:
    """Service layer for AWS EC2 instance management."""

    def __init__(self, session: AWSSession | None = None) -> None:
        """Initialize EC2Service with an optional AWS session."""
        self._session = session or AWSSession.get_instance()

    @retry_with_backoff(max_retries=3)
    def list_instances(self) -> list[dict[str, Any]]:
        """List all EC2 instances in the current region with basic metadata."""
        ec2 = self._session.ec2()
        instances = []
        
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    # Extract useful fields
                    name = ""
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break
                            
                    instances.append({
                        "id": instance["InstanceId"],
                        "name": name,
                        "type": instance["InstanceType"],
                        "state": instance["State"]["Name"],
                        "launch_time": instance["LaunchTime"].isoformat(),
                        "platform": instance.get("PlatformDetails", "Linux/UNIX"),
                        "vpc_id": instance.get("VpcId"),
                    })
        
        logger.info("Found [bold cyan]%d[/] EC2 instances", len(instances))
        return instances

    def get_instance_count(self) -> dict[str, int]:
        """Get a count of instances grouped by state."""
        instances = self.list_instances()
        stats: dict[str, int] = {}
        for inst in instances:
            state = inst["state"]
            stats[state] = stats.get(state, 0) + 1
        return stats
