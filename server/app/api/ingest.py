"""Routes d'ingestion bridge → serveur — contrat §4."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth import get_authenticated_node
from app.config import Settings
from app.deps import get_db, get_pending_bus, get_settings_dep, get_species_data
from app.errors import ApiError
from app.fsutil import write_atomic
from app.ingest.canonical import canonicalize_ingested_name, touch_species_name_cache
from app.ingest.clip_storage import clip_paths, looks_like_wav
from app.ingest.spectrogram import generate_spectrogram, probe_duration_s
from app.ingest.sync_service import process_sync
from app.ingest.top5 import recompute_top5
from app.live.compute import compute_site_pending
from app.live.pending_bus import PendingBus
from app.models.detection import Detection
from app.models.kept_clip import KeptClip
from app.models.node import Node, NodeStatus
from app.models.site import Site
from app.schemas.ingest import (
    ClipMissingBody,
    ClipMissingResponse,
    ClipUploadResponse,
    HeartbeatBody,
    HeartbeatResponse,
    PendingBody,
)
from app.schemas.sync import SyncRequestBody, SyncResponse
from app.species_data.store import SpeciesDataStore
from app.time_utils import utc_now, utc_now_str

logger = logging.getLogger("bird_frame.ingest")

router = APIRouter(tags=["ingest"])


@router.post("/nodes/{node_id}/sync", response_model=SyncResponse)
def sync_node(
    body: SyncRequestBody,
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
    bus: PendingBus = Depends(get_pending_bus),
) -> dict:
    return process_sync(db, node, body, store, bus)


def _find_detection(db: Session, node_id: int, node_local_id: int) -> Detection:
    detection = (
        db.query(Detection)
        .filter(Detection.node_id == node_id, Detection.node_local_id == node_local_id)
        .first()
    )
    if detection is None:
        raise ApiError(404, "detection_not_found", f"Aucune détection node_local_id={node_local_id} pour ce nœud.")
    return detection


def _active_kept_clip(db: Session, detection: Detection) -> KeptClip | None:
    return (
        db.query(KeptClip)
        .filter(
            KeptClip.site_id == detection.site_id,
            KeptClip.scientific_name == detection.scientific_name,
            KeptClip.detection_id == detection.id,
        )
        .first()
    )


@router.post("/nodes/{node_id}/clips/{node_local_id}", response_model=ClipUploadResponse, status_code=201)
async def upload_clip(
    node_local_id: int,
    response: Response,
    clip_name: str = Form(...),
    audio: UploadFile = File(...),
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
    app_settings: Settings = Depends(get_settings_dep),
) -> dict:
    detection = _find_detection(db, node.id, node_local_id)
    if detection.clip_name != clip_name:
        raise ApiError(
            422,
            "clip_name_mismatch",
            f"clip_name reçu ({clip_name!r}) différent de celui ingéré ({detection.clip_name!r}).",
        )

    kept_clip = _active_kept_clip(db, detection)
    if kept_clip is None or kept_clip.evicted_at is not None:
        raise ApiError(409, "clip_not_wanted", "Cette détection n'est plus dans le top-5 actif.")

    if kept_clip.audio_path is not None:
        response.status_code = 200
        return {
            "kept_clip_id": kept_clip.id,
            "detection_id": detection.id,
            "rank": kept_clip.rank_in_site_species,
            "already_stored": True,
            "spectrogram_generated": kept_clip.spectrogram_path is not None,
        }

    content = await audio.read()
    if len(content) > app_settings.max_upload_bytes:
        raise ApiError(413, "payload_too_large", f"Le clip dépasse {app_settings.max_upload_mb} Mo.")
    if len(content) == 0:
        raise ApiError(422, "invalid_audio", "Fichier audio vide.")

    ext = Path(audio.filename or "").suffix or Path(clip_name).suffix or ".wav"
    if ext.lower() == ".wav" and not looks_like_wav(content):
        raise ApiError(422, "invalid_audio", "En-tête WAV invalide (attendu RIFF…WAVE).")

    site = db.get(Site, detection.site_id)
    audio_path, png_path = clip_paths(
        app_settings.data_dir_resolved, site.slug, detection.scientific_name, kept_clip.id, ext
    )
    write_atomic(audio_path, content)

    spectrogram_generated = generate_spectrogram(app_settings.sox_path, audio_path, png_path)
    duration_s = probe_duration_s(app_settings.sox_path, audio_path)

    # Course avec recompute_top5 (déclenché par POST .../reviews en faux positif, ou
    # .../clips/{id}/missing) : le temps qu'on écrive le fichier ci-dessus, une AUTRE
    # requête (sa propre session/transaction) a pu évincer ce même kept_clip
    # (evicted_at posé + commit). Un simple `kept_clip.x = ...; db.commit()` ne le
    # verrait pas (la transaction de lecture ouverte plus haut fige un instantané
    # obsolète en SQLite/WAL) et écraserait silencieusement les chemins sur une ligne
    # déjà évincée — fichier jamais servi, jamais nettoyé. `db.rollback()` referme cette
    # transaction de lecture pour que l'UPDATE ci-dessous voie l'état réellement commité,
    # et la clause `WHERE evicted_at IS NULL` rend le check-and-write atomique.
    db.rollback()
    result = db.execute(
        update(KeptClip)
        .where(KeptClip.id == kept_clip.id, KeptClip.evicted_at.is_(None))
        .values(
            audio_path=str(audio_path),
            spectrogram_path=str(png_path) if spectrogram_generated else None,
            fetched_at=utc_now_str(),
            duration_s=duration_s,
        )
    )
    if result.rowcount == 0:
        db.rollback()
        audio_path.unlink(missing_ok=True)
        if png_path.exists():
            png_path.unlink(missing_ok=True)
        logger.info(
            "clip %s (détection %s) évincé pendant l'upload : fichier nettoyé, rien committé.",
            kept_clip.id,
            detection.id,
        )
        raise ApiError(409, "clip_not_wanted", "Cette détection n'est plus dans le top-5 actif.")
    db.commit()

    return {
        "kept_clip_id": kept_clip.id,
        "detection_id": detection.id,
        "rank": kept_clip.rank_in_site_species,
        "already_stored": False,
        "spectrogram_generated": spectrogram_generated,
    }


@router.post("/nodes/{node_id}/clips/{node_local_id}/missing", response_model=ClipMissingResponse)
def report_clip_missing(
    node_local_id: int,
    body: ClipMissingBody,
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
) -> dict:
    detection = _find_detection(db, node.id, node_local_id)
    kept_clip = _active_kept_clip(db, detection)
    if kept_clip is None or kept_clip.evicted_at is not None:
        return {"status": "ignored"}

    kept_clip.missing = True
    kept_clip.missing_reason = body.reason
    kept_clip.fetched_at = None
    db.commit()

    recompute_top5(db, kept_clip.site_id, kept_clip.scientific_name)
    return {"status": "marked_missing"}


@router.post("/nodes/{node_id}/pending", status_code=204)
def post_pending(
    body: PendingBody,
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
    bus: PendingBus = Depends(get_pending_bus),
) -> None:
    now = utc_now()
    items = []
    for raw_item in body.items:
        canonical_name = canonicalize_ingested_name(raw_item.scientific_name, store.aliases)
        touch_species_name_cache(db, canonical_name, raw_item.common_name)
        items.append(
            {
                "scientific_name": canonical_name,
                "status": raw_item.status,
                "hit_count": raw_item.hit_count,
                "confidence_hint": raw_item.confidence_hint,
                "first_detected_unix": raw_item.first_detected_unix,
                "last_updated_unix": raw_item.last_updated_unix,
                "source_id": raw_item.source_id,
            }
        )
    db.commit()

    bus.update_node_snapshot(node.id, int(now.timestamp()), items)

    site_id = node.site_id
    pending_list = compute_site_pending(db, site_id, bus, store, now=now)
    bus.publish_if_changed(site_id, pending_list, utc_now_str())


@router.post("/nodes/{node_id}/heartbeat", response_model=HeartbeatResponse)
def post_heartbeat(
    body: HeartbeatBody,
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    status_row = db.get(NodeStatus, node.id)
    if status_row is None:
        status_row = NodeStatus(node_id=node.id)
        db.add(status_row)

    status_row.last_heartbeat_at = utc_now_str()
    status_row.bridge_version = body.bridge_version
    status_row.birdnet_go_version = body.birdnet_go_version
    status_row.birdnet_go_reachable = body.birdnet_go_reachable
    status_row.birdnet_go_pid_alive = body.birdnet_go_pid_alive
    status_row.mic_device_name = body.mic_device_name
    status_row.mic_healthy = body.mic_healthy
    status_row.disk_free_pct = body.disk_free_pct
    status_row.node_db_max_id = body.node_db_max_id

    if body.dynamic_thresholds_snapshot is not None:
        snapshot = []
        for entry in body.dynamic_thresholds_snapshot:
            data = entry.model_dump(mode="json")
            data["scientific_name"] = canonicalize_ingested_name(entry.scientific_name, store.aliases)
            snapshot.append(data)
        status_row.dynamic_thresholds_snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        status_row.dynamic_thresholds_snapshot_at = utc_now_str()

    db.commit()
    return {"server_time_utc": utc_now_str()}
