"""`POST /nodes/{node_id}/sync` — contrat §4.2.

Les champs par-détection sont volontairement peu contraints ici (pas de `ge=0, le=1` sur
`confidence`, par exemple) : une valeur hors domaine sur UN élément ne doit PAS faire
échouer tout le lot (422), elle doit finir dans `rejected` avec le curseur qui avance
quand même — c'est `app/ingest/sync_service.py` qui fait cette validation métier
par élément. Seules les non-conformités structurelles (mauvais type, `detections`
absent) restent de vraies 422 Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel, UtcInstant


class SyncPredictionIn(BaseModel):
    scientific_name: str
    common_name: str | None = None
    confidence: float


class SyncDetectionIn(BaseModel):
    node_local_id: int
    detected_at_utc: str
    scientific_name: str
    common_name: str | None = None
    confidence: float
    source_id: int | None = None
    source_display_name: str | None = None
    clip_name: str | None = None
    has_clip: bool
    predictions: list[SyncPredictionIn] = Field(default_factory=list)


class SyncRequestBody(BaseModel):
    since_id: int = Field(ge=0)
    node_max_id: int = Field(ge=0)
    detections: list[SyncDetectionIn]


class RejectedItemOut(ApiModel):
    node_local_id: int
    error: str


class SyncCommandOut(ApiModel):
    id: int
    kind: str
    payload: dict
    created_at: UtcInstant
    expires_at: UtcInstant | None


class SyncResponse(ApiModel):
    accepted: int
    duplicates: int
    rejected: list[RejectedItemOut]
    synced_up_to_id: int
    want_clips: list[int]
    commands: list[SyncCommandOut]
