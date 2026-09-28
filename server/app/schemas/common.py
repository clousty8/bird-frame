"""Types Pydantic partagés — miroir de l'annexe TypeScript du contrat (§11).

`UtcInstant` accepte en entrée toute chaîne ISO 8601 avec fuseau explicite (rejette un
instant sans fuseau, §1.3) et sérialise toujours en sortie au format canonique
`YYYY-MM-DDTHH:MM:SSZ`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, PlainSerializer

from app.time_utils import format_utc_instant, parse_utc_instant


def _validate(v: object) -> datetime:
    if isinstance(v, datetime):
        return parse_utc_instant(format_utc_instant(v))
    if isinstance(v, str):
        return parse_utc_instant(v)
    raise ValueError("instant attendu sous forme de chaîne ISO 8601 avec fuseau")


UtcInstant = Annotated[datetime, BeforeValidator(_validate), PlainSerializer(format_utc_instant, return_type=str)]


class ApiModel(BaseModel):
    """Base commune : sérialise par nom de champ (snake_case déjà partout, contrat §1.2)."""

    model_config = {"populate_by_name": True}


class Prediction(ApiModel):
    scientific_name: str
    common_name_fr: str | None
    confidence: float
    is_primary: bool


class UpdateStatusOut(ApiModel):
    """État de la mise à jour automatique du bridge (contrat §12.4)."""

    state: str
    target_version: str | None
    error: str | None


class NodeStatusOut(ApiModel):
    node_id: int
    node_name: str
    site_slug: str
    site_name: str
    online: bool
    last_seen_at: UtcInstant | None
    last_sync_at: UtcInstant | None
    last_heartbeat_at: UtcInstant | None
    last_detection_at: UtcInstant | None
    mic_device_name: str | None
    mic_healthy: bool | None
    disk_free_pct: float | None
    birdnet_go_reachable: bool | None
    birdnet_go_pid_alive: bool | None
    birdnet_go_version: str | None
    bridge_version: str | None
    synced_up_to_id: int
    node_db_max_id: int | None
    sync_lag: int | None
    decommissioned_at: UtcInstant | None
    update_status: UpdateStatusOut | None  # contrat §12.4


class PendingItemOut(ApiModel):
    node_id: int
    scientific_name: str
    common_name_fr: str | None
    status: str
    hit_count: int
    confidence_hint: float | None
    first_detected_unix: int
    last_updated_unix: int
    source_id: str | None
    photo_url: str | None


class RecentDetectionOut(ApiModel):
    detection_id: int
    scientific_name: str
    common_name_fr: str | None
    confidence: float
    detected_at_utc: UtcInstant
    photo_url: str | None
