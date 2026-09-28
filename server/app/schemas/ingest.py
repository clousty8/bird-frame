"""Schémas des routes d'ingestion restantes — contrat §4.5, §4.6, §4.4."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ApiModel, UtcInstant
from app.schemas.node_update import UpdateStatusIn


class PendingItemIn(BaseModel):
    scientific_name: str
    common_name: str | None = None
    status: Literal["active", "approved", "rejected"]
    hit_count: int
    confidence_hint: float | None = None
    first_detected_unix: int
    last_updated_unix: int
    source_id: str | None = None


class PendingBody(BaseModel):
    snapshot_at_unix: int
    items: list[PendingItemIn]


class ClipMissingBody(BaseModel):
    clip_name: str | None
    reason: Literal["not_found", "unreadable", "no_clip_name"]


class ClipUploadResponse(ApiModel):
    kept_clip_id: int
    detection_id: int
    rank: int
    already_stored: bool
    spectrogram_generated: bool


class ClipMissingResponse(ApiModel):
    status: Literal["marked_missing", "ignored"]


class DynamicThresholdEntryIn(BaseModel):
    species_name: str
    scientific_name: str
    level: int
    current_value: float
    base_threshold: float
    high_conf_count: int
    trigger_count: int
    is_active: bool
    expires_at_utc: UtcInstant | None = None
    last_triggered_utc: UtcInstant | None = None
    first_created_utc: UtcInstant | None = None


class HeartbeatBody(BaseModel):
    sent_at_utc: UtcInstant
    bridge_version: str
    birdnet_go_version: str | None = None
    birdnet_go_reachable: bool
    birdnet_go_pid_alive: bool | None = None
    mic_device_name: str | None = None
    mic_healthy: bool | None = None
    disk_free_pct: float | None = None
    node_db_max_id: int
    dynamic_thresholds_snapshot: list[DynamicThresholdEntryIn] | None = None
    # Contrat §12.4 : optionnel (un bridge antérieur à la mise à jour automatique ne l'envoie pas).
    update_status: UpdateStatusIn | None = None


class HeartbeatResponse(ApiModel):
    server_time_utc: UtcInstant
    # Contrat §12.4 : version du bridge publiée par ce serveur, `null` si aucun bundle utilisable.
    latest_node_version: str | None
