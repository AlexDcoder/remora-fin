import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.inventory_service import InventoryService


@pytest.fixture
def mock_session() -> tuple[MagicMock, MagicMock]:
    mock = MagicMock(spec=AWSSession)
    mock.region = "us-east-1"

    # Setup for async context manager mock
    async_client_mock = MagicMock()

    class AsyncClientContext:
        async def __aenter__(self) -> MagicMock:
            return async_client_mock

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    mock.async_client.return_value = AsyncClientContext()
    return mock, async_client_mock


@pytest.mark.asyncio
async def test_inventory_service_ec2(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, client = mock_session

    # Mock paginator for EC2
    paginator = MagicMock()
    client.get_paginator.return_value = paginator

    async def mock_paginate() -> Any:
        yield {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "InstanceType": "t3.medium",
                            "State": {"Name": "running"},
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "Tags": [{"Key": "Name", "Value": "prod-server"}],
                        }
                    ]
                }
            ]
        }

    paginator.paginate.return_value.__aiter__.side_effect = mock_paginate

    service = InventoryService(session=session)
    resources = await service.list_resources_async("ec2", use_cache=False)

    assert len(resources) == 1
    assert resources[0]["id"] == "i-123"
    assert resources[0]["name"] == "prod-server"


@pytest.mark.asyncio
async def test_inventory_service_rds(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, client = mock_session

    # Mock paginator for RDS
    paginator = MagicMock()
    client.get_paginator.return_value = paginator

    async def mock_paginate() -> Any:
        yield {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "db-1",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "postgres",
                    "DBInstanceStatus": "available",
                }
            ]
        }

    paginator.paginate.return_value.__aiter__.side_effect = mock_paginate

    service = InventoryService(session=session)
    resources = await service.list_resources_async("rds", use_cache=False)

    assert len(resources) == 1
    assert resources[0]["id"] == "db-1"
    assert resources[0]["engine"] == "postgres"


@pytest.mark.asyncio
async def test_inventory_service_lambda(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, client = mock_session

    # Mock paginator for Lambda
    paginator = MagicMock()
    client.get_paginator.return_value = paginator

    async def mock_paginate() -> Any:
        yield {
            "Functions": [
                {
                    "FunctionName": "func-1",
                    "Runtime": "python3.9",
                    "MemorySize": 128,
                }
            ]
        }

    paginator.paginate.return_value.__aiter__.side_effect = mock_paginate

    service = InventoryService(session=session)
    resources = await service.list_resources_async("lambda", use_cache=False)

    assert len(resources) == 1
    assert resources[0]["name"] == "func-1"
    assert resources[0]["runtime"] == "python3.9"


@pytest.mark.asyncio
async def test_inventory_service_s3(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, client = mock_session
    from datetime import datetime

    # S3 uses list_method, not paginator in our registry
    client.list_buckets.return_value = asyncio.Future()
    client.list_buckets.return_value.set_result(
        {"Buckets": [{"Name": "my-bucket", "CreationDate": datetime(2023, 1, 1)}]}
    )

    service = InventoryService(session=session)
    resources = await service.list_resources_async("s3", use_cache=False)

    assert len(resources) == 1
    assert resources[0]["name"] == "my-bucket"


@pytest.mark.asyncio
async def test_inventory_service_vpc(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, client = mock_session

    # VPC uses paginator describe_vpcs
    paginator = MagicMock()
    client.get_paginator.return_value = paginator

    async def mock_paginate() -> Any:
        yield {
            "Vpcs": [
                {
                    "VpcId": "vpc-123",
                    "CidrBlock": "10.0.0.0/16",
                    "State": "available",
                    "IsDefault": False,
                }
            ]
        }

    paginator.paginate.return_value.__aiter__.side_effect = mock_paginate

    service = InventoryService(session=session)
    resources = await service.list_resources_async("vpc", use_cache=False)

    assert len(resources) == 1
    assert resources[0]["id"] == "vpc-123"
    assert resources[0]["cidr"] == "10.0.0.0/16"


@pytest.mark.asyncio
async def test_inventory_service_invalid_type(mock_session: tuple[MagicMock, MagicMock]) -> None:
    session, _ = mock_session
    service = InventoryService(session=session)
    resources = await service.list_resources_async("invalid_service", use_cache=False)
    assert resources == []
