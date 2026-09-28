"""Top-5 clips par (site, espèce) — contrat §4.3.1.

Recalcule à partir de zéro à chaque appel (fetch complet des candidats, tri Python) :
simple, correct, largement suffisant à l'échelle familiale visée (pas de
sur-ingénierie). Appelé après chaque détection avec `has_clip=true` acceptée en sync,
et après un signalement « clip manquant » (le rang libéré peut faire entrer un nouveau
candidat).
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.ingest.valid_detection import is_valid_detection_expr
from app.models.detection import Detection
from app.models.kept_clip import KeptClip
from app.time_utils import utc_now_str

logger = logging.getLogger("bird_frame.top5")

TOP_N = 5


def recompute_top5(db: Session, site_id: int, scientific_name: str) -> None:
    """Recalcule le top-5 de (site, espèce) et applique les effets observables du contrat :
    nouvelles lignes `kept_clips` sans audio (→ `want_clips` au prochain sync), éviction
    des sorties du top-5 avec suppression des fichiers **serveur** (jamais ceux du nœud).
    """
    missing_detection_ids = {
        row.detection_id
        for row in db.query(KeptClip.detection_id).filter(
            KeptClip.site_id == site_id,
            KeptClip.scientific_name == scientific_name,
            KeptClip.missing.is_(True),
        )
    }

    candidates = (
        db.query(Detection)
        .filter(
            Detection.site_id == site_id,
            Detection.scientific_name == scientific_name,
            Detection.has_clip.is_(True),
            is_valid_detection_expr(),
        )
        .order_by(Detection.confidence.desc(), Detection.detected_at_utc.desc(), Detection.id.desc())
        .all()
    )
    desired = [d for d in candidates if d.id not in missing_detection_ids][:TOP_N]
    desired_ids = {d.id for d in desired}

    existing_rows: dict[int, KeptClip] = {
        row.detection_id: row
        for row in db.query(KeptClip).filter(
            KeptClip.site_id == site_id, KeptClip.scientific_name == scientific_name
        )
    }

    now = utc_now_str()

    for rank, detection in enumerate(desired, start=1):
        row = existing_rows.get(detection.id)
        if row is None:
            db.add(
                KeptClip(
                    site_id=site_id,
                    scientific_name=scientific_name,
                    detection_id=detection.id,
                    confidence=detection.confidence,
                    rank_in_site_species=rank,
                    missing=False,
                )
            )
            continue
        row.rank_in_site_species = rank
        row.confidence = detection.confidence
        if row.evicted_at is not None:
            # Redevenue top-5 après une éviction (ex. faux positif ensuite annulé,
            # §4.3.1) : l'audio a été supprimé à l'éviction, il faut le redemander.
            row.evicted_at = None
            row.audio_path = None
            row.spectrogram_path = None
            row.fetched_at = None
            row.duration_s = None

    for detection_id, row in existing_rows.items():
        if detection_id in desired_ids or row.missing or row.evicted_at is not None:
            continue
        _evict(row, now)

    db.commit()


def _evict(row: KeptClip, now: str) -> None:
    for path_str in (row.audio_path, row.spectrogram_path):
        if path_str:
            try:
                Path(path_str).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("suppression du fichier évincé impossible (%s) : %s", path_str, exc)
    row.evicted_at = now
    row.audio_path = None
    row.spectrogram_path = None
