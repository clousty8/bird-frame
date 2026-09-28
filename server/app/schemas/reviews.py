"""`POST /sites/{slug}/reviews` et `POST /sites/{slug}/false-negatives` — contrat §6.25, §6.27."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import UtcInstant


class PostReviewBody(BaseModel):
    detection_id: int
    kind: Literal["correct", "false_positive"]
    note: str | None = Field(default=None, max_length=1000)


class PostFalseNegativeBody(BaseModel):
    scientific_name: str = Field(min_length=1, max_length=200)
    approx_time_utc: UtcInstant | None = None
    notes: str | None = Field(default=None, max_length=1000)
