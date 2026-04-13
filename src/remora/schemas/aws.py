"""AWS infrastructure schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AWSCredentials(BaseModel):
    """AWS credentials for authentication."""

    model_config = ConfigDict(frozen=True)

    access_key_id: str = Field(min_length=16, max_length=128)
    secret_access_key: str = Field(min_length=1, max_length=256)
    session_token: str | None = None

    @field_validator("access_key_id")
    @classmethod
    def _validate_key_id(cls, v: str) -> str:
        if not v.startswith(("AKIA", "ASIA")):
            raise ValueError("access_key_id must start with AKIA (IAM) or ASIA (session)")
        return v


class AWSAccount(BaseModel):
    """An AWS account within an organization."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=12, max_length=12)
    name: str | None = None
    email: str | None = None
    status: str = "ACTIVE"

    @field_validator("id")
    @classmethod
    def _validate_account_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 12:
            raise ValueError("AWS account ID must be exactly 12 digits")
        return v


class AWSService(BaseModel):
    """An AWS service with associated cost."""

    model_config = ConfigDict(frozen=True)

    code: str  # e.g. "AmazonEC2"
    name: str | None = None  # e.g. "Amazon Elastic Compute Cloud"
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)


class AWSRegion(BaseModel):
    """An AWS region."""

    model_config = ConfigDict(frozen=True)

    code: str  # e.g. "us-east-1"
    name: str | None = None  # e.g. "US East (N. Virginia)"


class AWSCallerIdentity(BaseModel):
    """Result of sts.get_caller_identity()."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    account: str
    arn: str
