from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str


class FalseNegativeReport(Base):
    """Signalement manuel d'une espèce entendue mais non détectée (architecture.md §4).

    `approx_time` renommé `approx_time_utc` par le contrat §9.6. Hors périmètre WP-13 :
    table présente pour la complétude du schéma, aucune route de ce lot n'y écrit.
    """

    __tablename__ = "false_negative_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    reported_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    reported_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approx_time_utc: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
