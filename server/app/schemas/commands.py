"""`POST /nodes/{node_id}/commands/{cmd_id}/ack` — contrat §4.8."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class AckCommandBody(BaseModel):
    status: Literal["applied", "failed"]
    result: dict | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _error_required_if_failed(self) -> AckCommandBody:
        if self.status == "failed" and not self.error:
            raise ValueError("error est requis (non nul) quand status = failed")
        return self
