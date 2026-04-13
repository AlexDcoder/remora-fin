"""Shared types used across all schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DateRange(BaseModel):
    """A time period with start and end dates."""

    model_config = ConfigDict(frozen=True)

    start: date
    end: date


class DateRangeInput(BaseModel):
    """Flexible date range input — accepts explicit dates or day counts."""

    model_config = ConfigDict(frozen=True)

    start: date | None = None
    end: date | None = None
    last_days: int | None = Field(default=None, ge=1, le=3650)


# -- Type aliases --

Money = Annotated[Decimal, Field(ge=0, decimal_places=2)]
Percent = Annotated[float, Field(ge=0, le=100)]
