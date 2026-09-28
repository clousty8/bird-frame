"""`PUT /sites/{slug}/species-rules/{scientific_name}` — contrat §6.21."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PutSpeciesRuleBody(BaseModel):
    rule: Literal["present", "impossible", "redirect"]
    threshold_override: float | None = None
    redirect_to_scientific_name: str | None = None
    reason: str | None = Field(default=None, max_length=500)
