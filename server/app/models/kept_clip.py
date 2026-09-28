from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KeptClip(Base):
    """Une entrée du top-5 clips par (site, espèce) — architecture.md §4, amendé §3.2 :
    le transfert est un push du bridge (upload multipart), jamais un GET du serveur vers
    le nœud. `+ duration_s`, `+ missing_reason` imposés par le contrat §9.2.
    """

    __tablename__ = "kept_clips"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "scientific_name", "detection_id", name="uq_kept_clips_site_species_det"
        ),
        Index("idx_kept_clips_lookup", "site_id", "scientific_name", "evicted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    spectrogram_path: Mapped[str | None] = mapped_column(String, nullable=True)
    rank_in_site_species: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[str | None] = mapped_column(String, nullable=True)
    evicted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    missing: Mapped[bool] = mapped_column(nullable=False, default=False)
    missing_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
