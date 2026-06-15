"""Inventory Service — Centralized AWS resource management.

Consolidates all AWS resource listing logic into a single dynamic service
using a registry-based approach. This reduces file count while maintaining
optimized async fetching and caching.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, NamedTuple

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff
from remora_fin.services.base_service import BaseService, ServiceType

logger = logging.getLogger(__name__)


class ResourceConfig(NamedTuple):
    """Configuration for a specific AWS resource type."""

    client_name: str
    paginator_name: str | None
    list_method: str | None = None  # Used if no paginator
    result_path: list[str] | None = None  # Path to the list in the response
    mapper: Callable[[Any], dict[str, Any]] | None = None
    service_type: ServiceType = ServiceType.REGIONAL


# Dynamic registry of AWS resources
RESOURCE_REGISTRY: dict[str, ResourceConfig] = {
    "ec2": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_instances",
        result_path=["Reservations", "Instances"],
        mapper=lambda x: {
            "id": x["InstanceId"],
            "name": next((t["Value"] for t in x.get("Tags", []) if t["Key"] == "Name"), ""),
            "type": x["InstanceType"],
            "state": x["State"]["Name"],
            "platform": x.get("PlatformDetails", "Linux/UNIX"),
        },
    ),
    "s3": ResourceConfig(
        client_name="s3",
        paginator_name=None,
        list_method="list_buckets",
        result_path=["Buckets"],
        mapper=lambda x: {"name": x["Name"], "creation_date": x["CreationDate"].isoformat()},
        service_type=ServiceType.GLOBAL,
    ),
    "rds": ResourceConfig(
        client_name="rds",
        paginator_name="describe_db_instances",
        result_path=["DBInstances"],
        mapper=lambda x: {
            "id": x["DBInstanceIdentifier"],
            "class": x["DBInstanceClass"],
            "engine": x["Engine"],
            "status": x["DBInstanceStatus"],
        },
    ),
    "lambda": ResourceConfig(
        client_name="lambda",
        paginator_name="list_functions",
        result_path=["Functions"],
        mapper=lambda x: {
            "name": x["FunctionName"],
            "runtime": x.get("Runtime"),
            "memory": x.get("MemorySize"),
        },
    ),
    "dynamodb": ResourceConfig(
        client_name="dynamodb",
        paginator_name="list_tables",
        result_path=["TableNames"],
        mapper=lambda x: {"name": x} if isinstance(x, str) else x,
    ),
    "cloudfront": ResourceConfig(
        client_name="cloudfront",
        paginator_name="list_distributions",
        result_path=["DistributionList", "Items"],
        mapper=lambda x: {"id": x["Id"], "domain": x["DomainName"], "status": x["Status"]},
        service_type=ServiceType.GLOBAL,
    ),
    "elasticache": ResourceConfig(
        client_name="elasticache",
        paginator_name="describe_cache_clusters",
        result_path=["CacheClusters"],
        mapper=lambda x: {"id": x["CacheClusterId"], "node_type": x["CacheNodeType"], "engine": x["Engine"]},
    ),
    "emr": ResourceConfig(
        client_name="emr",
        paginator_name="list_clusters",
        result_path=["Clusters"],
        mapper=lambda x: {"id": x["Id"], "name": x["Name"], "status": x["Status"]["State"]},
    ),
    "redshift": ResourceConfig(
        client_name="redshift",
        paginator_name="describe_clusters",
        result_path=["Clusters"],
        mapper=lambda x: {"id": x["ClusterIdentifier"], "node_type": x["NodeType"], "status": x["ClusterStatus"]},
    ),
    "sagemaker": ResourceConfig(
        client_name="sagemaker",
        paginator_name="list_notebook_instances",
        result_path=["NotebookInstances"],
        mapper=lambda x: {
            "name": x["NotebookInstanceName"],
            "status": x["NotebookInstanceStatus"],
            "type": x["InstanceType"],
        },
    ),
    "kms": ResourceConfig(
        client_name="kms",
        paginator_name="list_keys",
        result_path=["Keys"],
        mapper=lambda x: {"id": x["KeyId"], "arn": x["KeyArn"]},
    ),
    "secretsmanager": ResourceConfig(
        client_name="secretsmanager",
        paginator_name="list_secrets",
        result_path=["SecretList"],
        mapper=lambda x: {"name": x["Name"], "arn": x["ARN"]},
    ),
    "sns": ResourceConfig(
        client_name="sns",
        paginator_name="list_topics",
        result_path=["Topics"],
        mapper=lambda x: {"arn": x["TopicArn"], "name": x["TopicArn"].split(":")[-1]},
    ),
    "sqs": ResourceConfig(
        client_name="sqs",
        paginator_name="list_queues",
        result_path=["QueueUrls"],
        mapper=lambda x: {"url": x, "name": x.split("/")[-1]},
    ),
    "ecs": ResourceConfig(
        client_name="ecs",
        paginator_name="list_clusters",
        result_path=["clusterArns"],
        mapper=lambda x: {"arn": x, "name": x.split("/")[-1]},
    ),
    "eks": ResourceConfig(
        client_name="eks",
        paginator_name="list_clusters",
        result_path=["clusters"],
        mapper=lambda x: {"name": x},
    ),
    "opensearch": ResourceConfig(
        client_name="opensearch",
        paginator_name=None,
        list_method="list_domain_names",
        result_path=["DomainNames"],
        mapper=lambda x: {"name": x["DomainName"]},
    ),
    "apprunner": ResourceConfig(
        client_name="apprunner",
        paginator_name="list_services",
        result_path=["ServiceSummaryList"],
        mapper=lambda x: {"id": x["ServiceId"], "name": x["ServiceName"], "status": x["Status"]},
    ),
    "stepfunctions": ResourceConfig(
        client_name="stepfunctions",
        paginator_name="list_state_machines",
        result_path=["stateMachines"],
        mapper=lambda x: {"arn": x["stateMachineArn"], "name": x["name"]},
    ),
    "glue": ResourceConfig(
        client_name="glue",
        paginator_name="get_databases",
        result_path=["DatabaseList"],
        mapper=lambda x: {"name": x["Name"], "description": x.get("Description", "")},
    ),
    "transfer": ResourceConfig(
        client_name="transfer",
        paginator_name="list_servers",
        result_path=["Servers"],
    ),
    "ebs": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_volumes",
        result_path=["Volumes"],
        mapper=lambda x: {
            "id": x["VolumeId"],
            "size": x["Size"],
            "type": x["VolumeType"],
            "state": x["State"],
            "iops": x.get("Iops"),
        },
    ),
    "efs": ResourceConfig(
        client_name="efs",
        paginator_name="describe_file_systems",
        result_path=["FileSystems"],
        mapper=lambda x: {"id": x["FileSystemId"], "name": x.get("Name", ""), "size": x["SizeInBytes"]["Value"]},
    ),
    "elb": ResourceConfig(
        client_name="elbv2",
        paginator_name="describe_load_balancers",
        result_path=["LoadBalancers"],
        mapper=lambda x: {"name": x["LoadBalancerName"], "type": x["Type"], "scheme": x["Scheme"]},
    ),
    "nat_gateway": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_nat_gateways",
        result_path=["NatGateways"],
        mapper=lambda x: {"id": x["NatGatewayId"], "state": x["State"], "vpc": x["VpcId"]},
    ),
    "apigateway": ResourceConfig(
        client_name="apigateway",
        paginator_name="get_rest_apis",
        result_path=["items"],
        mapper=lambda x: {
            "id": x["id"],
            "name": x["name"],
            "created": x.get("createdDate", "").isoformat()
            if hasattr(x.get("createdDate"), "isoformat")
            else str(x.get("createdDate")),
        },
    ),
    "apigatewayv2": ResourceConfig(
        client_name="apigatewayv2",
        paginator_name="get_apis",
        result_path=["Items"],
        mapper=lambda x: {"id": x["ApiId"], "name": x["Name"], "protocol": x["ProtocolType"]},
    ),
    "vpc": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_vpcs",
        result_path=["Vpcs"],
        mapper=lambda x: {"id": x["VpcId"], "cidr": x["CidrBlock"], "state": x["State"], "default": x["IsDefault"]},
    ),
    "subnet": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_subnets",
        result_path=["Subnets"],
        mapper=lambda x: {"id": x["SubnetId"], "vpc": x["VpcId"], "cidr": x["CidrBlock"], "az": x["AvailabilityZone"]},
    ),
    "security_group": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_security_groups",
        result_path=["SecurityGroups"],
        mapper=lambda x: {"id": x["GroupId"], "name": x["GroupName"], "vpc": x.get("VpcId", "N/A")},
    ),
    "route53": ResourceConfig(
        client_name="route53",
        paginator_name="list_hosted_zones",
        result_path=["HostedZones"],
        mapper=lambda x: {"id": x["Id"], "name": x["Name"], "private": x["Config"]["PrivateZone"]},
        service_type=ServiceType.GLOBAL,
    ),
    "eventbridge": ResourceConfig(
        client_name="events",
        paginator_name="list_rules",
        result_path=["Rules"],
        mapper=lambda x: {"name": x["Name"], "state": x["State"], "bus": x.get("EventBusName", "default")},
    ),
    "logs": ResourceConfig(
        client_name="logs",
        paginator_name="describe_log_groups",
        result_path=["logGroups"],
        mapper=lambda x: {
            "name": x["logGroupName"],
            "retention": x.get("retentionInDays", "Infinite"),
            "size": x.get("storedBytes", 0),
        },
    ),
    "iam_role": ResourceConfig(
        client_name="iam",
        paginator_name="list_roles",
        result_path=["Roles"],
        mapper=lambda x: {"name": x["RoleName"], "id": x["RoleId"], "arn": x["Arn"]},
        service_type=ServiceType.GLOBAL,
    ),
    "wafv2": ResourceConfig(
        client_name="wafv2",
        paginator_name="list_web_acls",
        result_path=["WebACLs"],
        mapper=lambda x: {"name": x["Name"], "id": x["Id"], "arn": x["ARN"]},
    ),
}


class InventoryService(BaseService):
    """Consolidated service for all AWS resource inventory."""

    def __init__(self, session: AWSSession | None = None) -> None:
        super().__init__("inventory", session)

    @async_retry_with_backoff(max_retries=3)
    async def list_resources_async(self, resource_type: str, use_cache: bool = True) -> list[dict[str, Any]]:
        """List resources of any registered type with unified logic."""
        config = RESOURCE_REGISTRY.get(resource_type.lower())
        if not config:
            logger.error(f"Resource type '{resource_type}' not found in registry")
            return []

        query = {
            "service": "inventory",
            "resource": resource_type,
            "region": self._session.region if config.service_type == ServiceType.REGIONAL else "global",
        }

        async def _fetch() -> list[dict[str, Any]]:
            items = []
            async with self._session.async_client(config.client_name) as client:
                if config.paginator_name:
                    paginator = client.get_paginator(config.paginator_name)
                    async for page in paginator.paginate():
                        raw_items = self._resolve_path(page, config.result_path)
                        for item in raw_items:
                            if config.mapper:
                                items.append(config.mapper(item))
                            else:
                                items.append(item)
                elif config.list_method:
                    method = getattr(client, config.list_method)
                    resp = await method()
                    raw_items = self._resolve_path(resp, config.result_path)
                    for item in raw_items:
                        if config.mapper:
                            items.append(config.mapper(item))
                        else:
                            items.append(item)

            logger.info("Inventory: Found [bold cyan]%d[/] %s resources", len(items), resource_type)
            return items

        return await self.get_cached_or_fetch_async(query, _fetch, use_cache=use_cache)

    def _resolve_path(self, data: dict[str, Any], path: list[str] | None) -> list[Any]:
        """Helper to navigate nested response structures."""
        if not path:
            return []

        # Special case for EC2 where we have Reservations -> Instances
        if path == ["Reservations", "Instances"]:
            instances = []
            for reservation in data.get("Reservations", []):
                instances.extend(reservation.get("Instances", []))
            return instances

        current = data
        for key in path:
            if isinstance(current, dict):
                current = current.get(key, [])
            else:
                return []

        return current if isinstance(current, list) else []
