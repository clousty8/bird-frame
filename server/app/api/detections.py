"""`GET /sites/{slug}/detections` — contrat §6.30.

Liste **brute** pour la revue : aucune exclusion (ni faux positif, ni règle `impossible`),
contrairement à la vue effective utilisée par le calendrier et les stats (§1.7).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.deps import get_db, get_species_data
from app.errors import ApiError
from app.ingest.valid_detection import current_review_kind_expr
from app.live.compute import resolve_common_name_fr
from app.models.detection import Detection, Prediction
from app.models.kept_clip import KeptClip
from app.models.review import Review
from app.models.species_site_rule import SpeciesSiteRule
from app.species_data.store import SpeciesDataStore
from app.time_utils import parse_local_date, round4

router = APIRouter(tags=["detections"])


@router.get("/sites/{slug}/detections")
def get_site_detections(
    slug: str,
    date: str | None = Query(default=None),
    species: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    review: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)

    if date is not None:
        try:
            parse_local_date(date)
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc
    if review is not None and review not in ("correct", "false_positive", "none"):
        raise ApiError(422, "validation_error", f"review invalide : {review!r}.")

    query = db.query(Detection).filter(Detection.site_id == site.id)
    if date is not None:
        query = query.filter(Detection.detected_local_date == date)
    if species is not None:
        canonical_species = store.resolve_reference(species) or species.strip().replace("_", " ")
        query = query.filter(
            (Detection.scientific_name == canonical_species)
            | (Detection.redirected_to_scientific_name == canonical_species)
        )
    if min_confidence is not None:
        query = query.filter(Detection.confidence >= min_confidence)
    if review is not None:
        kind_expr = current_review_kind_expr()
        query = query.filter(kind_expr.is_(None) if review == "none" else kind_expr == review)

    total = query.count()
    rows = (
        query.order_by(Detection.detected_at_utc.desc(), Detection.id.desc()).offset(offset).limit(limit).all()
    )

    rules = {
        r.scientific_name: r.rule for r in db.query(SpeciesSiteRule).filter(SpeciesSiteRule.site_id == site.id)
    }

    return {
        "detections": [_detection_out(db, store, d, rules) for d in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _detection_out(db: Session, store: SpeciesDataStore, d: Detection, rules: dict[str, str]) -> dict:
    effective = d.redirected_to_scientific_name or d.scientific_name
    review_kind, review_note = _current_review(db, d.id)

    kept_clip = (
        db.query(KeptClip)
        .filter(KeptClip.detection_id == d.id, KeptClip.evicted_at.is_(None), KeptClip.missing.is_(False))
        .first()
    )
    kept_clip_id = audio_url = spectrogram_url = None
    if kept_clip is not None:
        kept_clip_id = kept_clip.id
        if kept_clip.audio_path and Path(kept_clip.audio_path).is_file():
            audio_url = f"/api/v1/recordings/{kept_clip.id}/audio"
        if kept_clip.spectrogram_path and Path(kept_clip.spectrogram_path).is_file():
            spectrogram_url = f"/api/v1/recordings/{kept_clip.id}/spectrogram"

    return {
        "detection_id": d.id,
        "node_id": d.node_id,
        "node_local_id": d.node_local_id,
        "detected_at_utc": d.detected_at_utc,
        "local_date": d.detected_local_date,
        "scientific_name": d.scientific_name,
        "common_name_fr": resolve_common_name_fr(d.scientific_name, store, db),
        "effective_scientific_name": effective,
        "effective_common_name_fr": resolve_common_name_fr(effective, store, db),
        "confidence": round4(d.confidence),
        "source_display_name": d.source_display_name,
        "has_clip": d.has_clip,
        "kept_clip_id": kept_clip_id,
        "audio_url": audio_url,
        "spectrogram_url": spectrogram_url,
        "review": review_kind,
        "review_note": review_note,
        "rule": rules.get(d.scientific_name),
        "predictions": _predictions(db, store, d),
    }


def _current_review(db: Session, detection_id: int) -> tuple[str | None, str | None]:
    row = (
        db.query(Review.kind, Review.note)
        .filter(Review.detection_id == detection_id)
        .order_by(Review.id.desc())
        .first()
    )
    return (row[0], row[1]) if row else (None, None)


def _predictions(db: Session, store: SpeciesDataStore, d: Detection) -> list[dict]:
    result = [
        {
            "scientific_name": d.scientific_name,
            "common_name_fr": resolve_common_name_fr(d.scientific_name, store, db),
            "confidence": round4(d.confidence),
            "is_primary": True,
        }
    ]
    secondaries = (
        db.query(Prediction).filter(Prediction.detection_id == d.id).order_by(Prediction.confidence.desc()).all()
    )
    for p in secondaries:
        result.append(
            {
                "scientific_name": p.scientific_name,
                "common_name_fr": resolve_common_name_fr(p.scientific_name, store, db),
                "confidence": round4(p.confidence),
                "is_primary": False,
            }
        )
    return result
