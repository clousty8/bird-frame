"""`POST /nodes/register` et `POST /admin/species-data/reload` — contrat §3."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel, UtcInstant

_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class RegisterNodeBody(BaseModel):
    site_slug: str = Field(pattern=_SLUG_PATTERN, min_length=2, max_length=40)
    site_name: str = Field(min_length=1, max_length=100)
    node_name: str = Field(min_length=1, max_length=100)
    timezone: str
    lat: float | None = Field(ge=-90, le=90)
    lon: float | None = Field(ge=-180, le=180)
    auto_main_name: bool = True


class RegisterNodeResponse(ApiModel):
    node_id: int
    site_id: int
    site_slug: str
    site_created: bool
    bridge_shared_secret: str


class InvalidSpeciesFileOut(ApiModel):
    file: str
    error: str


class SpeciesDataReloadResponse(ApiModel):
    universe_count: int
    base_count: int
    sheet_count: int
    alias_count: int
    invalid_files: list[InvalidSpeciesFileOut]
    loaded_at: UtcInstant
