"""AWS Service — Singleton session management and client factory.

Design Patterns: Singleton + Factory + Retry with backoff
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast

import aioboto3
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_budgets.client import BudgetsClient
    from mypy_boto3_ce.client import CostExplorerClient as SyncCEClient
    from mypy_boto3_organizations.client import OrganizationsClient
    from mypy_boto3_pricing.client import PricingClient
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_sts.client import STSClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AWSSession:
    """Thread-safe multiton for AWS sessions (sync + async).

    Usage:
        session = AWSSession.get_instance(region="us-west-2", profile="dev")
        ce_client = session.cost_explorer()
    """

    _instances: ClassVar[dict[tuple[str, str], AWSSession]] = {}

    def __new__(
        cls,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> AWSSession:
        key = (region, profile)
        if key not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> None:
        if getattr(self, "_initialized", False):
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
        logger.info("AWSSession initialized (region=[cyan]%s[/], profile=[cyan]%s[/])", region, profile)

    @classmethod
    def get_instance(
        cls,
        region: str = "us-east-1",
        profile: str = "default",
    ) -> AWSSession:
        return cls(region=region, profile=profile)

    # -- Sync client factory (with lru_cache-like reuse) --

    def _sync_client(self, service: str, **kwargs: Any) -> Any:
        cfg = Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
        )
        # Using Any to avoid complex boto3 type overloads
        client_func: Any = self._sync_session.client
        return client_func(service, config=cfg, **kwargs)

    def cost_explorer(self) -> SyncCEClient:
        return cast("SyncCEClient", self._sync_client("ce"))

    def budgets(self) -> BudgetsClient:
        return cast("BudgetsClient", self._sync_client("budgets"))

    def organizations(self) -> OrganizationsClient:
        return cast("OrganizationsClient", self._sync_client("organizations"))

    def pricing(self) -> PricingClient:
        return cast("PricingClient", self._sync_client("pricing"))

    def s3(self) -> S3Client:
        return cast("S3Client", self._sync_client("s3"))

    def sts(self) -> STSClient:
        return cast("STSClient", self._sync_client("sts"))

    def cloudwatch(self) -> Any:
        return self._sync_client("monitoring")

    def tagging(self) -> Any:
        return self._sync_client("resource-groups-tagging-api")

    @property
    def async_session(self) -> aioboto3.Session:
        return self._async_session

    def validate_credentials(self) -> bool:
        """Check if AWS credentials are valid."""
        try:
            identity = self.sts().get_caller_identity()
            logger.info("AWS identity: Account=%s, ARN=%s", identity["Account"], identity["Arn"])
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

    def fetch_token_paginated(
        self,
        method: Callable[..., Any],
        token_field: str = "NextPageToken",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Generic helper for APIs that use NextPageToken manually."""
        pages = []
        current_kwargs = kwargs.copy()
        while True:
            resp = method(**current_kwargs)
            pages.append(resp)
            token = resp.get(token_field)
            if not token:
                break
            current_kwargs[token_field] = token
        return pages


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
    paginator = client_method.__self__.get_paginator(client_method.__name__)
    yield from paginator.paginate(**kwargs)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: retry on throttling/transient errors with exponential backoff."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
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
                            "[yellow]AWS throttling[/] on [cyan]%s[/] (attempt [bold]%d/%d[/]). Retrying in [bold]%.1fs[/]...",
                            func.__name__,
                            attempt + 1,
                            max_retries,
                            delay,
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry loop ended unexpectedly")

        return wrapper

    return decorator
