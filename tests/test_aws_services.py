from unittest.mock import MagicMock

import pytest

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.cloudfront_service import CloudFrontService
from remora_fin.services.dynamodb_service import DynamoDBService
from remora_fin.services.lambda_service import LambdaService
from remora_fin.services.rds_service import RDSService
from remora_fin.services.s3_service import S3Service


@pytest.fixture
def mock_session() -> MagicMock:
    mock = MagicMock(spec=AWSSession)
    mock.region = "us-east-1"
    return mock


def test_rds_service_list_instances(mock_session: MagicMock) -> None:
    mock_rds = mock_session.rds.return_value
    mock_rds.get_paginator.return_value.paginate.return_value = [
        {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "db-1",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "postgres",
                    "DBInstanceStatus": "available",
                    "MultiAZ": False,
                    "StorageType": "gp2",
                    "AllocatedStorage": 20,
                }
            ]
        }
    ]

    service = RDSService(session=mock_session)
    instances = service.list_db_instances()

    assert len(instances) == 1
    assert instances[0]["id"] == "db-1"
    assert instances[0]["engine"] == "postgres"


def test_s3_service_list_buckets(mock_session: MagicMock) -> None:
    from datetime import datetime

    mock_s3 = mock_session.s3.return_value
    mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "bucket-1", "CreationDate": datetime(2023, 1, 1)}]}

    service = S3Service(session=mock_session)
    buckets = service.list_buckets()

    assert len(buckets) == 1
    assert buckets[0]["name"] == "bucket-1"


def test_lambda_service_list_functions(mock_session: MagicMock) -> None:
    mock_lambda = mock_session.lambda_client.return_value
    mock_lambda.get_paginator.return_value.paginate.return_value = [
        {
            "Functions": [
                {
                    "FunctionName": "func-1",
                    "Runtime": "python3.9",
                    "MemorySize": 128,
                    "LastModified": "2023-01-01T00:00:00Z",
                    "Handler": "main.handler",
                    "Timeout": 30,
                }
            ]
        }
    ]

    service = LambdaService(session=mock_session)
    functions = service.list_functions()

    assert len(functions) == 1
    assert functions[0]["name"] == "func-1"
    assert functions[0]["runtime"] == "python3.9"


def test_dynamodb_service_list_tables(mock_session: MagicMock) -> None:
    mock_ddb = mock_session.dynamodb.return_value
    mock_ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["table-1"]}]

    service = DynamoDBService(session=mock_session)
    tables = service.list_tables()

    assert len(tables) == 1
    assert tables[0] == "table-1"


def test_cloudfront_service_list_distributions(mock_session: MagicMock) -> None:
    mock_cf = mock_session.cloudfront.return_value
    mock_cf.get_paginator.return_value.paginate.return_value = [
        {
            "DistributionList": {
                "Items": [
                    {
                        "Id": "dist-1",
                        "ARN": "arn:aws:cloudfront::123:dist/dist-1",
                        "Status": "Deployed",
                        "DomainName": "abc.cloudfront.net",
                        "Enabled": True,
                    }
                ]
            }
        }
    ]

    service = CloudFrontService(session=mock_session)
    distributions = service.list_distributions()

    assert len(distributions) == 1
    assert distributions[0]["id"] == "dist-1"
