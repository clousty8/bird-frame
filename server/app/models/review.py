from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str


class Review(Base):
    """Revue (faux positif / correct) d'une détection — architecture.md §4.

    Plusieurs revues par détection sont autorisées ; la plus récente (`id` max) fait foi
    (contrat §1.7). Hors périmètre WP-13 : aucune route de ce lot n'écrit ici pour
    l'instant, la table existe pour que le schéma soit complet dès la première migration.
    """

    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("kind IN ('correct', 'false_positive')", name="ck_review_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    synced_to_node_at: Mapped[str | None] = mapped_column(String, nullable=True)
