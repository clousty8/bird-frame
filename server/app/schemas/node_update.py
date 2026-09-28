"""Schémas de la mise à jour des nœuds — contrat §12."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class NodeUpdateInfo(ApiModel):
    latest_version: str
    bundle_sha256: str
    bundle_size: int
    bundle_url: str


class UpdateStatusIn(BaseModel):
    """État du dernier essai de mise à jour, rapporté par le bridge dans son heartbeat (§12.4).

    `state` est une chaîne libre bornée (et non une énumération fermée) : un bridge plus récent
    qui ajouterait un état ne doit pas voir tout son heartbeat rejeté en 422.
    """

    state: str = Field(min_length=1, max_length=32)
    target_version: str | None = Field(default=None, max_length=32)
    error: str | None = Field(default=None, max_length=2000)
