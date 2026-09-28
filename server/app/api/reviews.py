"""Routes `/sites/{slug}/reviews` et `/sites/{slug}/false-negatives` — contrat §6.25 à
§6.28 (WP-13).

`mark_detection_reviewed` est un `kind` déjà prévu par le CHECK de `node_commands`
(contrat §5.2, colonne posée dès la migration initiale) — pas de migration à ajouter ici.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.deps import get_db, get_species_data
from app.errors import ApiError
from app.ingest.top5 import recompute_top5
from app.live.compute import resolve_common_name_fr
from app.models.detection import Detection
from app.models.false_negative import FalseNegativeReport
from app.models.node import Node
from app.models.node_command import NodeCommand
from app.models.review import Review
from app.schemas.reviews import PostFalseNegativeBody, PostReviewBody
from app.species_data.store import SpeciesDataStore
from app.time_utils import format_utc_instant, round4

router = APIRouter(tags=["reviews"])


def _detection_summary(db: Session, store: SpeciesDataStore, detection: Detection) -> dict:
    return {
        "scientific_name": detection.scientific_name,
        "common_name_fr": resolve_common_name_fr(detection.scientific_name, store, db),
        "confidence": round4(detection.confidence),
        "detected_at_utc": detection.detected_at_utc,
    }


def _review_out(
    db: Session, store: SpeciesDataStore, review: Review, detection: Detection, command: NodeCommand | None
) -> dict:
    return {
        "review_id": review.id,
        "detection_id": review.detection_id,
        "kind": review.kind,
        "note": review.note,
        "created_at": review.created_at,
        "created_by": review.created_by,
        "synced_to_node_at": review.synced_to_node_at,
        "command_status": command.status if command else None,
        "detection": _detection_summary(db, store, detection),
    }


def _latest_command_for_review(db: Session, review_id: int) -> NodeCommand | None:
    return (
        db.query(NodeCommand)
        .filter(NodeCommand.origin_type == "review", NodeCommand.origin_id == review_id)
        .order_by(NodeCommand.id.desc())
        .first()
    )


@router.post("/sites/{slug}/reviews", status_code=201)
def post_review(
    slug: str,
    body: PostReviewBody,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    detection = (
        db.query(Detection).filter(Detection.id == body.detection_id, Detection.site_id == site.id).first()
    )
    if detection is None:
        raise ApiError(404, "detection_not_found", f"Aucune détection {body.detection_id} sur ce site.")

    review = Review(detection_id=detection.id, kind=body.kind, note=body.note)
    db.add(review)
    db.flush()

    # Répercussion best-effort vers le nœud d'origine (architecture.md §7.5) : jamais
    # d'écriture directe dans les tables de BirdNET-Go, toujours via le cycle CSRF du
    # bridge. Nœud décommissionné → pas de commande (rien à répercuter).
    command: NodeCommand | None = None
    node = db.get(Node, detection.node_id)
    if node is not None and node.decommissioned_at is None:
        payload = {"node_local_id": detection.node_local_id, "verified": body.kind, "comment": body.note}
        command = NodeCommand(
            node_id=node.id,
            kind="mark_detection_reviewed",
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="pending",
            origin_type="review",
            origin_id=review.id,
        )
        db.add(command)
        db.flush()

    db.commit()

    # Top-5 (contrat §4.3.1) : un false_positive évince le clip du top-5, un correct qui
    # annule un false_positive précédent peut le faire redevenir candidat.
    recompute_top5(db, detection.site_id, detection.scientific_name)

    return {
        "review": _review_out(db, store, review, detection, command),
        "command_id": command.id if command else None,
    }


@router.get("/sites/{slug}/reviews")
def get_reviews(
    slug: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    if kind is not None and kind not in ("correct", "false_positive"):
        raise ApiError(422, "validation_error", f"kind invalide : {kind!r}.")

    query = db.query(Review).join(Detection, Detection.id == Review.detection_id).filter(
        Detection.site_id == site.id
    )
    if kind:
        query = query.filter(Review.kind == kind)

    total = query.count()
    rows = query.order_by(Review.created_at.desc(), Review.id.desc()).offset(offset).limit(limit).all()

    reviews_out = []
    for review in rows:
        detection = db.get(Detection, review.detection_id)
        command = _latest_command_for_review(db, review.id)
        reviews_out.append(_review_out(db, store, review, detection, command))

    return {"reviews": reviews_out, "total": total, "limit": limit, "offset": offset}


def _known_species(db: Session, store: SpeciesDataStore, scientific_name: str) -> bool:
    if store.in_france_universe(scientific_name):
        return True
    return bool(db.query(Detection.id).filter(Detection.scientific_name == scientific_name).first())


def _false_negative_out(db: Session, store: SpeciesDataStore, report: FalseNegativeReport) -> dict:
    return {
        "id": report.id,
        "scientific_name": report.scientific_name,
        "common_name_fr": resolve_common_name_fr(report.scientific_name, store, db),
        "known_species": _known_species(db, store, report.scientific_name),
        "approx_time_utc": report.approx_time_utc,
        "notes": report.notes,
        "reported_at": report.reported_at,
        "reported_by": report.reported_by,
    }


@router.post("/sites/{slug}/false-negatives", status_code=201)
def post_false_negative(
    slug: str,
    body: PostFalseNegativeBody,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    canonical = store.resolve_reference(body.scientific_name) or body.scientific_name.strip().replace("_", " ")

    report = FalseNegativeReport(
        site_id=site.id,
        scientific_name=canonical,
        approx_time_utc=format_utc_instant(body.approx_time_utc) if body.approx_time_utc else None,
        notes=body.notes,
    )
    db.add(report)
    db.commit()

    return {"false_negative": _false_negative_out(db, store, report)}


@router.get("/sites/{slug}/false-negatives")
def get_false_negatives(
    slug: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    query = db.query(FalseNegativeReport).filter(FalseNegativeReport.site_id == site.id)
    total = query.count()
    rows = (
        query.order_by(FalseNegativeReport.reported_at.desc(), FalseNegativeReport.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "false_negatives": [_false_negative_out(db, store, r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
