"""Algorithme de `POST /nodes/{node_id}/sync` — contrat §4.2.

Orchestré ici plutôt que dans le routeur pour rester testable sans passer par une vraie
requête HTTP, et parce que la logique (curseur canonique, idempotence, top-5,
redirection, SSE) est trop dense pour vivre dans un handler FastAPI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.ingest.canonical import (
    canonicalize_ingested_name,
    touch_species_name_cache,
    warn_if_unknown_species,
)
from app.ingest.commands import deliver_due_commands
from app.ingest.top5 import recompute_top5
from app.live.compute import photo_url_for, resolve_common_name_fr
from app.live.pending_bus import PendingBus
from app.models.detection import Detection, Prediction
from app.models.kept_clip import KeptClip
from app.models.node import Node, NodeSyncState
from app.models.site import Site
from app.models.species_site_rule import SpeciesSiteRule
from app.schemas.sync import SyncDetectionIn, SyncRequestBody
from app.species_data.naming import is_safe_scientific_name
from app.species_data.store import SpeciesDataStore
from app.time_utils import (
    format_utc_instant,
    local_date_and_hour,
    parse_utc_instant,
    round4,
    utc_now,
    utc_now_str,
)

logger = logging.getLogger("bird_frame.sync")

_RECENT_SSE_WINDOW_S = 15 * 60
_WANT_CLIPS_LIMIT = 50


_MAX_BATCH_SIZE = 200


def process_sync(db: Session, node: Node, body: SyncRequestBody, store: SpeciesDataStore, bus: PendingBus) -> dict:
    if len(body.detections) > _MAX_BATCH_SIZE:
        raise ApiError(422, "batch_too_large", f"Le lot dépasse {_MAX_BATCH_SIZE} détections.")

    site = db.get(Site, node.site_id)

    sync_state = db.get(NodeSyncState, node.id)
    if sync_state is None:
        sync_state = NodeSyncState(node_id=node.id, last_synced_detection_id=0)
        db.add(sync_state)
        db.flush()
    cursor = sync_state.last_synced_detection_id

    if body.node_max_id < cursor:
        raise ApiError(
            409,
            "node_db_reset",
            "La base BirdNET-Go du nœud semble avoir été remplacée (id max en régression).",
            details={"synced_up_to_id": cursor, "node_max_id": body.node_max_id},
        )
    if body.since_id > cursor:
        raise ApiError(
            409,
            "cursor_ahead",
            "since_id est en avance sur le curseur serveur.",
            details={"synced_up_to_id": cursor},
        )

    accepted = 0
    duplicates = 0
    rejected: list[dict] = []
    max_local_id_seen: int | None = None
    touched_species: set[str] = set()
    sse_events: list[dict] = []
    now = utc_now()

    for item in body.detections:
        max_local_id_seen = item.node_local_id if max_local_id_seen is None else max(max_local_id_seen, item.node_local_id)

        error = _validate_item(item)
        if error:
            rejected.append({"node_local_id": item.node_local_id, "error": error})
            continue

        canonical_name = canonicalize_ingested_name(item.scientific_name, store.aliases)
        warn_if_unknown_species(canonical_name, store)
        detected_at = parse_utc_instant(item.detected_at_utc)
        local_date, local_hour = local_date_and_hour(detected_at, site.timezone)

        touch_species_name_cache(db, canonical_name, item.common_name)
        for pred in item.predictions:
            pred_canonical = canonicalize_ingested_name(pred.scientific_name, store.aliases)
            touch_species_name_cache(db, pred_canonical, pred.common_name)

        already_known = (
            db.query(Detection.id)
            .filter(Detection.node_id == node.id, Detection.node_local_id == item.node_local_id)
            .first()
        )
        if already_known:
            duplicates += 1
            continue

        redirect_rule = (
            db.query(SpeciesSiteRule)
            .filter(
                SpeciesSiteRule.site_id == site.id,
                SpeciesSiteRule.scientific_name == canonical_name,
                SpeciesSiteRule.rule == "redirect",
            )
            .first()
        )
        redirected_to = redirect_rule.redirect_to_scientific_name if redirect_rule else None

        detection_row = Detection(
            node_id=node.id,
            site_id=site.id,
            node_local_id=item.node_local_id,
            detected_at_utc=format_utc_instant(detected_at),
            scientific_name=canonical_name,
            raw_scientific_name=item.scientific_name,
            confidence=item.confidence,
            source_id=item.source_id,
            source_display_name=item.source_display_name,
            clip_name=item.clip_name,
            has_clip=bool(item.has_clip),
            redirected_to_scientific_name=redirected_to,
            detected_local_date=local_date,
            detected_local_hour=local_hour,
        )
        db.add(detection_row)
        db.flush()
        accepted += 1

        for pred in item.predictions:
            pred_canonical = canonicalize_ingested_name(pred.scientific_name, store.aliases)
            db.add(
                Prediction(
                    detection_id=detection_row.id,
                    scientific_name=pred_canonical,
                    confidence=pred.confidence,
                )
            )

        if detection_row.has_clip:
            touched_species.add(canonical_name)

        effective_name = redirected_to or canonical_name
        if _within_sse_window(detected_at, now) and not _is_impossible(db, site.id, effective_name):
            sse_events.append(
                {
                    "detection_id": detection_row.id,
                    "scientific_name": effective_name,
                    "common_name_fr": resolve_common_name_fr(effective_name, store, db),
                    "confidence": round4(detection_row.confidence),
                    "detected_at_utc": format_utc_instant(detected_at),
                    "photo_url": photo_url_for(effective_name, store),
                }
            )

    new_cursor = cursor if max_local_id_seen is None else max(cursor, max_local_id_seen)
    sync_state.last_synced_detection_id = new_cursor
    sync_state.last_sync_at = utc_now_str()
    db.commit()

    for name in touched_species:
        recompute_top5(db, site.id, name)

    commands = deliver_due_commands(db, node.id)

    want_clips = _compute_want_clips(db, node.id)

    for event in sse_events:
        bus.publish_detection(site.id, event)

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "synced_up_to_id": new_cursor,
        "want_clips": want_clips,
        "commands": [
            {
                "id": cmd.id,
                "kind": cmd.kind,
                "payload": json.loads(cmd.payload_json),
                "created_at": cmd.created_at,
                "expires_at": cmd.expires_at,
            }
            for cmd in commands
        ],
    }


def _validate_item(item: SyncDetectionIn) -> str | None:
    if item.node_local_id < 1:
        return "node_local_id doit être ≥ 1"
    if not (1 <= len(item.scientific_name) <= 200):
        return "scientific_name doit faire 1 à 200 caractères"
    if not is_safe_scientific_name(item.scientific_name):
        # scientific_name devient un segment de chemin de fichier (clip_paths, contrat
        # §4.3) : jamais de `/`, `\` ni `.` — refusé ici plutôt que de laisser une
        # traversée de répertoire atteindre le système de fichiers à l'upload du clip.
        return "scientific_name contient des caractères non autorisés"
    if not (0.0 <= item.confidence <= 1.0):
        return f"confidence hors de [0, 1] : {item.confidence!r}"
    try:
        parse_utc_instant(item.detected_at_utc)
    except ValueError as exc:
        return str(exc)
    return None


def _is_impossible(db: Session, site_id: int, scientific_name: str) -> bool:
    rule = (
        db.query(SpeciesSiteRule.id)
        .filter(
            SpeciesSiteRule.site_id == site_id,
            SpeciesSiteRule.scientific_name == scientific_name,
            SpeciesSiteRule.rule == "impossible",
        )
        .first()
    )
    return rule is not None


def _within_sse_window(detected_at: datetime, now: datetime) -> bool:
    return 0 <= (now - detected_at).total_seconds() < _RECENT_SSE_WINDOW_S


def _compute_want_clips(db: Session, node_id: int, limit: int = _WANT_CLIPS_LIMIT) -> list[int]:
    rows = (
        db.query(Detection.node_local_id)
        .join(KeptClip, KeptClip.detection_id == Detection.id)
        .filter(
            Detection.node_id == node_id,
            KeptClip.evicted_at.is_(None),
            KeptClip.missing.is_(False),
            KeptClip.audio_path.is_(None),
        )
        .order_by(KeptClip.rank_in_site_species.asc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]
