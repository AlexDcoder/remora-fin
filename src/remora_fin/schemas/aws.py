"""AWS infrastructure schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AWSCallerIdentity(BaseModel):
    """Result of sts.get_caller_identity()."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    account: str
    arn: str