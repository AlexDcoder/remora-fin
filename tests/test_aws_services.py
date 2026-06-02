from unittest.mock import MagicMock

import pytest

from remora_fin.services.aws_service import AWSSession
from remora_fin.services.cloudfront_service import CloudFrontService
from remora_fin.services.dynamodb_service import DynamoDBService
from remora_fin.services.ec2_service import EC2Service
from remora_fin.services.elasticache_service import ElastiCacheService
from remora_fin.services.emr_service import EMRService
from remora_fin.services.lambda_service import LambdaService
from remora_fin.services.rds_service import RDSService
from remora_fin.services.redshift_service import RedshiftService
from remora_fin.services.s3_service import S3Service
from remora_fin.services.sagemaker_service import SageMakerService
from remora_fin.services.sns_service import SNSService
from remora_fin.services.sqs_service import SQSService


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


def test_ec2_service_list_instances(mock_session: MagicMock) -> None:
    from datetime import datetime
    mock_ec2 = mock_session.ec2.return_value
    mock_ec2.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "InstanceType": "t3.medium",
                            "State": {"Name": "running"},
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "LaunchTime": datetime(2023, 1, 1),
                        }
                    ]
                }
            ]
        }
    ]

    service = EC2Service(session=mock_session)
    instances = service.list_instances()

    assert len(instances) == 1
    assert instances[0]["id"] == "i-123"


def test_elasticache_service_list_clusters(mock_session: MagicMock) -> None:
    mock_elc = mock_session.elasticache.return_value
    mock_elc.get_paginator.return_value.paginate.return_value = [
        {
            "CacheClusters": [
                {
                    "CacheClusterId": "cache-1",
                    "Engine": "redis",
                    "CacheClusterStatus": "available",
                    "CacheNodeType": "cache.t3.micro",
                    "NumCacheNodes": 1,
                }
            ]
        }
    ]

    service = ElastiCacheService(session=mock_session)
    clusters = service.list_clusters()

    assert len(clusters) == 1
    assert clusters[0]["id"] == "cache-1"


def test_redshift_service_list_clusters(mock_session: MagicMock) -> None:
    mock_rs = mock_session.redshift.return_value
    mock_rs.get_paginator.return_value.paginate.return_value = [
        {
            "Clusters": [
                {
                    "ClusterIdentifier": "rs-1",
                    "NodeType": "dc2.large",
                    "ClusterStatus": "available",
                    "NumberOfNodes": 1,
                }
            ]
        }
    ]

    service = RedshiftService(session=mock_session)
    clusters = service.list_clusters()

    assert len(clusters) == 1
    assert clusters[0]["id"] == "rs-1"


def test_emr_service_list_clusters(mock_session: MagicMock) -> None:
    mock_emr = mock_session.emr.return_value
    mock_emr.get_paginator.return_value.paginate.return_value = [
        {
            "Clusters": [
                {
                    "Id": "j-123",
                    "Name": "emr-cluster",
                    "Status": {"State": "RUNNING"},
                }
            ]
        }
    ]

    service = EMRService(session=mock_session)
    clusters = service.list_clusters()

    assert len(clusters) == 1
    assert clusters[0]["id"] == "j-123"


def test_sagemaker_service_list_instances(mock_session: MagicMock) -> None:
    mock_sm = mock_session.sagemaker.return_value
    mock_sm.get_paginator.return_value.paginate.return_value = [
        {
            "NotebookInstances": [
                {
                    "NotebookInstanceName": "sm-1",
                    "NotebookInstanceStatus": "InService",
                    "InstanceType": "ml.t2.medium",
                    "NotebookInstanceArn": "arn:aws:sagemaker:us-east-1:123:notebook-instance/sm-1",
                }
            ]
        }
    ]

    service = SageMakerService(session=mock_session)
    instances = service.list_notebook_instances()

    assert len(instances) == 1
    assert instances[0]["name"] == "sm-1"


def test_sns_service_list_topics(mock_session: MagicMock) -> None:
    mock_sns = mock_session.sns.return_value
    mock_sns.get_paginator.return_value.paginate.return_value = [{"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123:topic-1"}]}]

    service = SNSService(session=mock_session)
    topics = service.list_topics()

    assert len(topics) == 1
    assert topics[0]["arn"] == "arn:aws:sns:us-east-1:123:topic-1"


def test_sqs_service_list_queues(mock_session: MagicMock) -> None:
    mock_sqs = mock_session.sqs.return_value
    mock_sqs.get_paginator.return_value.paginate.return_value = [{"QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123/queue-1"]}]
    
    # Mock for get_queue_attributes which is called for each queue
    mock_sqs.get_queue_attributes.return_value = {
        "Attributes": {
            "QueueArn": "arn:aws:sqs:us-east-1:123:queue-1",
            "CreatedTimestamp": "1672531200",
            "ApproximateNumberOfMessages": "1",
            "ApproximateNumberOfMessagesNotVisible": "0"
        }
    }

    service = SQSService(session=mock_session)
    queues = service.list_queues()

    assert len(queues) == 1
    assert queues[0]["name"] == "queue-1"
    assert queues[0]["message_count"] == 1
