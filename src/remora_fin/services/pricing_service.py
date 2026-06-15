"""Pricing Service — AWS Pricing API integration.

Handles fetching unit prices for AWS services and caching them locally.
The Pricing API is only available in us-east-1 and ap-south-1.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, cast

from remora_fin.schemas.pricing import AWSPrice, PricingDetail, ProductAttributes
from remora_fin.services.aws_service import AWSSession, retry_with_backoff
from remora_fin.services.base_service import BaseService
from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PricingService(BaseService):
    """Service for querying AWS Pricing information."""

    def __init__(self, session: AWSSession | None = None, cache: CacheService | None = None) -> None:
        super().__init__("pricing", session, cache)

    @retry_with_backoff(max_retries=3)
    def get_products(self, service_code: str, filters: list[dict[str, str]]) -> list[PricingDetail]:
        """Fetch products from AWS Pricing API with filters."""
        query = {
            "service": "pricing",
            "method": "get_products",
            "service_code": service_code,
            "filters": sorted([f"{f['Field']}={f['Value']}" for f in filters]),
        }

        # Use cache if available
        cached = self._cache.get_json(query, max_age_hours=24)
        if cached:
            return [PricingDetail(**p) for p in cached]

        client = self._session.pricing()

        # Convert filters to AWS format
        aws_filters = [{"Type": "TERM_MATCH", "Field": f["Field"], "Value": f["Value"]} for f in filters]

        try:
            paginator = client.get_paginator("get_products")
            details = []
            for page in paginator.paginate(ServiceCode=service_code, Filters=cast(Any, aws_filters)):
                for price_list_str in page.get("PriceList", []):
                    # PriceList items are actually JSON strings...
                    item = json.loads(price_list_str)
                    details.append(self._parse_item(item))

            # Store in cache
            self._cache.set_json(query, [d.model_dump(mode="json") for d in details])
            return details

        except Exception as e:
            logger.error(f"Failed to fetch pricing for {service_code}: {e}")
            return []

    def _parse_item(self, item: dict[str, Any]) -> PricingDetail:
        """Parse the complex nested JSON from AWS Pricing API."""
        product = item.get("product", {})
        sku = product.get("sku", "N/A")
        attributes = product.get("attributes", {})

        prices = []
        terms = item.get("terms", {}).get("OnDemand", {})
        for term in terms.values():
            price_dimensions = term.get("priceDimensions", {})
            for dim in price_dimensions.values():
                unit_price = dim.get("pricePerUnit", {}).get("USD", "0")
                prices.append(
                    AWSPrice(
                        rate_code=dim.get("rateCode", ""),
                        description=dim.get("description", ""),
                        unit=dim.get("unit", ""),
                        price_per_unit=Decimal(str(unit_price)),
                        currency="USD",
                        effective_date=term.get("effectiveDate"),
                    )
                )

        # Extract base fields to avoid "multiple values for keyword argument"
        attrs = attributes.copy()
        region = attrs.pop("regionCode", attrs.pop("region", None))
        location = attrs.pop("location", None)
        service_code = attrs.pop("serviceCode", product.get("serviceCode", ""))

        return PricingDetail(
            sku=sku,
            attributes=ProductAttributes(
                service_code=service_code,
                region=region,
                location=location,
                **attrs,
            ),
            prices=prices,
        )

    def get_ec2_price(
        self, instance_type: str, region_code: str, operating_system: str = "Linux"
    ) -> PricingDetail | None:
        """Helper for EC2 instance pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
            {"Field": "operatingSystem", "Value": operating_system},
            {"Field": "preInstalledSw", "Value": "NA"},
            {"Field": "tenancy", "Value": "Shared"},
            {"Field": "capacitystatus", "Value": "Used"},
        ]
        results = self.get_products("AmazonEC2", filters)
        return results[0] if results else None

    def get_s3_price(self, volume_type: str, region_code: str) -> PricingDetail | None:
        """Helper for S3 storage pricing."""
        filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "volumeType", "Value": volume_type},
        ]
        results = self.get_products("AmazonS3", filters)
        return results[0] if results else None

    def get_rds_price(
        self, instance_class: str, region_code: str, database_engine: str = "MySQL"
    ) -> PricingDetail | None:
        """Helper for RDS instance pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_class},
            {"Field": "regionCode", "Value": region_code},
            {"Field": "databaseEngine", "Value": database_engine},
            {"Field": "deploymentOption", "Value": "Single-AZ"},
        ]
        results = self.get_products("AmazonRDS", filters)
        return results[0] if results else None

    def get_lambda_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for Lambda pricing (Request and Duration)."""
        # We need two different products for Lambda usually
        filters_duration = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "productFamily", "Value": "Serverless"},
            {"Field": "group", "Value": "AWS-Lambda-Duration"},
        ]
        filters_requests = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "productFamily", "Value": "Serverless"},
            {"Field": "group", "Value": "AWS-Lambda-Requests"},
        ]

        duration = self.get_products("AWSLambda", filters_duration)
        requests = self.get_products("AWSLambda", filters_requests)

        return cast(
            dict[str, PricingDetail | None],
            {
                "duration": duration[0] if duration else None,
                "requests": requests[0] if requests else None,
            },
        )

    def get_ebs_price(self, volume_api_name: str, region_code: str) -> PricingDetail | None:
        """Helper for EBS volume pricing."""
        filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "volumeApiName", "Value": volume_api_name},
            {"Field": "productFamily", "Value": "Storage"},
        ]
        results = self.get_products("AmazonEC2", filters)
        return results[0] if results else None

    def get_dynamodb_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for DynamoDB pricing."""
        filters_storage = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "productFamily", "Value": "Database Storage"},
        ]
        filters_wcu = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "DDB-WriteUnits"},
        ]
        filters_rcu = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "DDB-ReadUnits"},
        ]

        storage = self.get_products("AmazonDynamoDB", filters_storage)
        wcu = self.get_products("AmazonDynamoDB", filters_wcu)
        rcu = self.get_products("AmazonDynamoDB", filters_rcu)

        return cast(
            dict[str, PricingDetail | None],
            {
                "storage": storage[0] if storage else None,
                "wcu": wcu[0] if wcu else None,
                "rcu": rcu[0] if rcu else None,
            },
        )

    def get_nat_gateway_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for NAT Gateway pricing."""
        filters_hour = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "NAT Gateway - Hour"},
        ]
        filters_data = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "NAT Gateway - Data Processed"},
        ]

        hourly = self.get_products("AmazonEC2", filters_hour)
        data = self.get_products("AmazonEC2", filters_data)

        return cast(
            dict[str, PricingDetail | None],
            {
                "hourly": hourly[0] if hourly else None,
                "data": data[0] if data else None,
            },
        )

    def get_elb_price(self, region_code: str, lb_type: str = "Application") -> dict[str, PricingDetail | None]:
        """Helper for ELB pricing (ALB, NLB, or CLB)."""
        # lb_type mapping to AWS Pricing groups
        if lb_type == "Application":
            hourly_group = "Application Load Balancer-Hour"
            lcu_group = "LCU"
        elif lb_type == "Network":
            hourly_group = "Network Load Balancer-Hour"
            lcu_group = "NLAU"
        else:  # Classic
            hourly_group = "Load Balancer-Hour"
            lcu_group = None

        hourly = self.get_products(
            "ElasticLoadBalancing",
            [{"Field": "regionCode", "Value": region_code}, {"Field": "group", "Value": hourly_group}],
        )

        lcu = []
        if lcu_group:
            lcu = self.get_products(
                "ElasticLoadBalancing",
                [{"Field": "regionCode", "Value": region_code}, {"Field": "group", "Value": lcu_group}],
            )

        return cast(
            dict[str, PricingDetail | None],
            {
                "hourly": hourly[0] if hourly else None,
                "lcu": lcu[0] if lcu else None,
            },
        )

    def get_elasticache_price(self, node_type: str, region_code: str, engine: str = "Redis") -> PricingDetail | None:
        """Helper for ElastiCache pricing."""
        filters = [
            {"Field": "instanceType", "Value": node_type},
            {"Field": "regionCode", "Value": region_code},
            {"Field": "cacheEngine", "Value": engine},
        ]
        results = self.get_products("AmazonElastiCache", filters)
        return results[0] if results else None

    def get_redshift_price(self, node_type: str, region_code: str) -> PricingDetail | None:
        """Helper for Redshift pricing."""
        filters = [
            {"Field": "instanceType", "Value": node_type},
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("AmazonRedshift", filters)
        return results[0] if results else None

    def get_opensearch_price(self, instance_type: str, region_code: str) -> PricingDetail | None:
        """Helper for OpenSearch pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("AmazonOpenSearchService", filters)
        return results[0] if results else None

    def get_efs_price(self, region_code: str, storage_class: str = "General Purpose") -> PricingDetail | None:
        """Helper for EFS pricing."""
        filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "storageClass", "Value": storage_class},
        ]
        results = self.get_products("AmazonEFS", filters)
        return results[0] if results else None

    def get_fargate_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for Fargate pricing (vCPU and RAM)."""
        cpu_filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "Fargate-vCPU"},
        ]
        ram_filters = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "Fargate-RAM"},
        ]

        cpu = self.get_products("AmazonECS", cpu_filters)
        ram = self.get_products("AmazonECS", ram_filters)

        return cast(
            dict[str, PricingDetail | None],
            {
                "vcpu": cpu[0] if cpu else None,
                "ram": ram[0] if ram else None,
            },
        )

    def get_cloudfront_price(self, region_code: str) -> dict[str, list[PricingDetail]]:
        """Helper for CloudFront pricing."""
        # CloudFront has many types of requests and data transfer
        data_transfer = self.get_products(
            "AmazonCloudFront",
            [{"Field": "regionCode", "Value": region_code}, {"Field": "productFamily", "Value": "Data Transfer"}],
        )
        requests = self.get_products(
            "AmazonCloudFront",
            [{"Field": "regionCode", "Value": region_code}, {"Field": "productFamily", "Value": "CloudFront Requests"}],
        )

        return {
            "data_transfer": data_transfer,
            "requests": requests,
        }

    def get_eks_price(self, region_code: str) -> PricingDetail | None:
        """Helper for EKS cluster fee pricing."""
        filters = [
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("AmazonEKS", filters)
        return results[0] if results else None

    def get_kms_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for KMS pricing (Keys and Requests)."""
        filters_keys = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "KMS-Keys"},
        ]
        filters_requests = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "KMS-Requests"},
        ]

        keys = self.get_products("AWSKMS", filters_keys)
        requests = self.get_products("AWSKMS", filters_requests)

        return cast(
            dict[str, PricingDetail | None],
            {
                "keys": keys[0] if keys else None,
                "requests": requests[0] if requests else None,
            },
        )

    def get_sns_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for SNS pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AmazonSNS", filters)

    def get_sqs_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for SQS pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AmazonSQS", filters)

    def get_msk_price(self, instance_type: str, region_code: str) -> PricingDetail | None:
        """Helper for MSK pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("AmazonMSK", filters)
        return results[0] if results else None

    def get_emr_price(self, instance_type: str, region_code: str) -> PricingDetail | None:
        """Helper for EMR pricing (EC2 + EMR fee)."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("ElasticMapReduce", filters)
        return results[0] if results else None

    def get_sagemaker_price(self, instance_type: str, region_code: str) -> PricingDetail | None:
        """Helper for SageMaker instance pricing."""
        filters = [
            {"Field": "instanceType", "Value": instance_type},
            {"Field": "regionCode", "Value": region_code},
        ]
        results = self.get_products("AmazonSageMaker", filters)
        return results[0] if results else None

    def get_glue_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for Glue pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AWSGlue", filters)

    def get_secrets_manager_price(self, region_code: str) -> dict[str, PricingDetail | None]:
        """Helper for Secrets Manager pricing."""
        filters_storage = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "Secret Storage"},
        ]
        filters_api = [
            {"Field": "regionCode", "Value": region_code},
            {"Field": "group", "Value": "API Calls"},
        ]

        storage = self.get_products("AWSSecretsManager", filters_storage)
        api = self.get_products("AWSSecretsManager", filters_api)

        return cast(
            dict[str, PricingDetail | None],
            {
                "storage": storage[0] if storage else None,
                "api": api[0] if api else None,
            },
        )

    def get_app_runner_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for App Runner pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AWSAppRunner", filters)

    def get_step_functions_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for Step Functions pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AWSStepFunctions", filters)

    def get_transfer_family_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for AWS Transfer Family pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AWSTransfer", filters)

    def get_apigateway_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for API Gateway pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AmazonApiGateway", filters)

    def get_waf_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for AWS WAF pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("awswaf", filters)

    def get_route53_price(self) -> list[PricingDetail]:
        """Helper for Route53 pricing (Global)."""
        # Route53 doesn't use regionCode in the same way usually
        return self.get_products("AmazonRoute53", [])

    def get_athena_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for Athena pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AmazonAthena", filters)

    def get_kinesis_price(self, region_code: str) -> list[PricingDetail]:
        """Helper for Kinesis Data Streams pricing."""
        filters = [{"Field": "regionCode", "Value": region_code}]
        return self.get_products("AmazonKinesis", filters)

    def get_region_pricing_summary(self, region_code: str) -> dict[str, Any]:
        """Get a summary of key pricing benchmarks for a region."""
        summary = {}

        # S3 Standard
        s3 = self.get_s3_price("Standard", region_code)
        if s3 and s3.on_demand_price:
            summary["S3 Standard (per GB)"] = s3.on_demand_price.price_per_unit

        # EC2 common types
        for itype in ["t3.medium", "m5.large", "c5.xlarge"]:
            ec2 = self.get_ec2_price(itype, region_code)
            if ec2 and ec2.on_demand_price:
                summary[f"EC2 {itype} (On-Demand)"] = ec2.on_demand_price.price_per_unit

        # Lambda
        lambda_p = self.get_lambda_price(region_code)
        if lambda_p["duration"] and lambda_p["duration"].on_demand_price:
            summary["Lambda Duration (per GB-sec)"] = lambda_p["duration"].on_demand_price.price_per_unit
        if lambda_p["requests"] and lambda_p["requests"].on_demand_price:
            summary["Lambda Requests (per 1M)"] = lambda_p["requests"].on_demand_price.price_per_unit

        # DynamoDB
        ddb = self.get_dynamodb_price(region_code)
        if ddb["storage"] and ddb["storage"].on_demand_price:
            summary["DynamoDB Storage (per GB)"] = ddb["storage"].on_demand_price.price_per_unit

        return summary
