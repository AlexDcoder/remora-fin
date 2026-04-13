"""AWS Service — Singleton session management and client factory.

Design Patterns: Singleton + Factory + Retry with backoff
"""

from __future__ import annotations

import functools
import logging
import time
from typing import TYPE_CHECKING, Any, Generator

import aioboto3
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_ce import CostExplorerClient
    from mypy_boto3_ce.client import CostExplorerClient as SyncCEClient
    from mypy_boto3_budgets.client import BudgetsClient
    from mypy_boto3_organizations.client import OrganizationsClient
    from mypy_boto3_pricing.client import PricingClient
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_sts.client import STSClient

logger = logging.getLogger(__name__)


class AWSSession:
    """Thread-safe singleton for AWS sessions (sync + async).

    Usage:
        session = AWSSession.get_instance()
        ce_client = session.cost_explorer()
    """

    _instance: AWSSession | None = None

    def __new__(
        cls,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> "AWSSession":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> None:
        if self._initialized:
            return
        self._region = region
        self._profile = profile
        self._sync_session = boto3.Session(
            region_name=region,
            profile_name=profile,
        )
        self._async_session = aioboto3.Session(
            region_name=region,
            profile_name=profile,
        )
        self._initialized = True
        logger.info("AWSSession initialized (region=%s, profile=%s)", region, profile)

    @classmethod
    def get_instance(
        cls,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> "AWSSession":
        return cls(region=region, profile=profile)

    # -- Sync client factory (with lru_cache-like reuse) --

    def _sync_client(self, service: str, **kwargs: Any) -> Any:
        cfg = Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
        )
        return self._sync_session.client(service, config=cfg, **kwargs)

    def cost_explorer(self) -> "SyncCEClient":
        return self._sync_client("ce")

    def budgets(self) -> "BudgetsClient":
        return self._sync_client("budgets")

    def organizations(self) -> "OrganizationsClient":
        return self._sync_client("organizations")

    def pricing(self) -> "PricingClient":
        return self._sync_client("pricing")

    def s3(self) -> "S3Client":
        return self._sync_client("s3")

    def sts(self) -> "STSClient":
        return self._sync_client("sts")

    def cloudwatch(self):
        return self._sync_client("monitoring")

    def tagging(self):
        return self._sync_client("resource-groups-tagging-api")

    # -- Async session --

    @property
    def async_session(self) -> aioboto3.Session:
        return self._async_session

    # -- Validation --

    def validate_credentials(self) -> bool:
        """Check if AWS credentials are valid."""
        try:
            identity = self.sts().get_caller_identity()
            logger.info("AWS identity: Account=%s, ARN=%s",
                       identity["Account"], identity["Arn"])
            return True
        except ClientError as e:
            logger.error("AWS credential validation failed: %s", e)
            return False

    def get_caller_identity(self) -> dict[str, str]:
        """Return caller identity info."""
        resp = self.sts().get_caller_identity()
        return {
            "user_id": resp["UserId"],
            "account": resp["Account"],
            "arn": resp["Arn"],
        }


# -- Paginator Helper --


def paginate_all(
    client_method: Any,
    **kwargs: Any,
) -> Generator[dict[str, Any], None, None]:
    """Yield all pages from a paginated AWS API call.

    Usage:
        ce = session.cost_explorer()
        for page in paginate_all(ce.get_cost_and_usage, **params):
            process(page)
    """
    paginator = client_method.__self__.get_paginator(
        client_method.__name__
    )
    for page in paginator.paginate(**kwargs):
        yield page


# -- Retry Decorator --


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
):
    """Decorator: retry on throttling/transient errors with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    code = e.response["Error"]["Code"]
                    if code not in (
                        "ThrottlingException",
                        "LimitExceededException",
                        "RequestLimitExceeded",
                    ):
                        raise
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "AWS throttling on %s (attempt %d/%d). "
                            "Retrying in %.1fs...",
                            func.__name__, attempt + 1, max_retries, delay,
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
            raise last_exception  # type: ignore[misc]
        return wrapper
    return decorator
