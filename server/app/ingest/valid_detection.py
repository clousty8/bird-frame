"""Expression SQL partagée : « détection valide » — contrat §1.7.

Une détection est valide si sa revue courante (id max pour cette détection) n'est pas
`false_positive`. Sans revue du tout (cas normal tant que WP-13 n'existe pas), la
sous-requête vaut NULL — traité explicitement, sinon `NULL != 'x'` est NULL en SQL et
exclurait silencieusement toutes les détections non revues.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.detection import Detection
from app.models.review import Review


def current_review_kind_expr() -> ColumnElement:
    """Sous-requête scalaire : `kind` de la revue courante (id max) d'une détection, ou
    NULL si jamais revue — réutilisée par `is_valid_detection_expr` et par le filtre
    `review=` de `GET /sites/{slug}/detections` (contrat §6.30)."""
    return (
        select(Review.kind)
        .where(Review.detection_id == Detection.id)
        .order_by(Review.id.desc())
        .limit(1)
        .scalar_subquery()
    )


def is_valid_detection_expr() -> ColumnElement:
    latest_kind = current_review_kind_expr()
    return or_(latest_kind.is_(None), latest_kind != "false_positive")


def current_review_kind(db, detection_id: int) -> str | None:
    """Version Python (une détection à la fois) de `current_review_kind_expr`."""
    row = (
        db.query(Review.kind)
        .filter(Review.detection_id == detection_id)
        .order_by(Review.id.desc())
        .first()
    )
    return row[0] if row else None
