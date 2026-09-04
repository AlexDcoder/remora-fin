"""Inventory Service — Centralized AWS resource management.

Consolidates all AWS resource listing logic into a single dynamic service
using a registry-based approach.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, NamedTuple

from remora_fin.services.aws_service import AWSSession, async_retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class ResourceConfig(NamedTuple):
    client_name: str
    paginator_name: str | None
    list_method: str | None = None
    result_path: list[str] | None = None
    mapper: Callable[[Any], dict[str, Any]] | None = None


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
    "vpc": ResourceConfig(
        client_name="ec2",
        paginator_name="describe_vpcs",
        result_path=["Vpcs"],
        mapper=lambda x: {
            "id": x["VpcId"],
            "cidr": x["CidrBlock"],
            "state": x["State"],
            "is_default": x["IsDefault"],
        },
    ),
}


class InventoryService(BaseService):
    """Consolidated service for AWS resource inventory."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        super().__init__("inventory", session, cache)

    @async_retry_with_backoff(max_retries=3)
    async def list_resources_async(self, resource_type: str, use_cache: bool = True) -> list[dict[str, Any]]:
        config = RESOURCE_REGISTRY.get(resource_type.lower())
        if not config:
            logger.warning(f"Resource type '{resource_type}' not found in registry")
            return []

        query = {
            "service": "inventory",
            "resource": resource_type,
            "region": self._session.region,
        }

        async def _fetch() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
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
        if not path:
            return []

        if path == ["Reservations", "Instances"]:
            instances = []
            for reservation in data.get("Reservations", []):
                instances.extend(reservation.get("Instances", []))
            return instances

        current: Any = data
        for key in path:
            if isinstance(current, dict):
                current = current.get(key, [])
            else:
                return []

        return current if isinstance(current, list) else []
