from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.time_utils import utc_now_str


class Detection(Base):
    """Copie serveur d'une détection (jamais les tables natives de BirdNET-Go).

    `scientific_name` stocke le nom **canonique** bird-frame (après résolution
    `aliases.json`, §1.6 du contrat) ; `raw_scientific_name` garde le nom brut reçu du
    nœud, pour l'audit (contrat §9.1).
    """

    __tablename__ = "detections"
    __table_args__ = (
        UniqueConstraint("node_id", "node_local_id", name="uq_detections_node_local_id"),
        Index("idx_detections_site_species", "site_id", "scientific_name"),
        Index("idx_detections_detected_at", "detected_at_utc"),
        Index("idx_detections_site_local_date", "site_id", "detected_local_date"),
        Index("idx_detections_node_detected_at", "node_id", "detected_at_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    node_local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    raw_scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    clip_name: Mapped[str | None] = mapped_column(String, nullable=True)
    has_clip: Mapped[bool] = mapped_column(nullable=False, default=False)
    redirected_to_scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    detected_local_date: Mapped[str] = mapped_column(String, nullable=False)
    detected_local_hour: Mapped[int] = mapped_column(Integer, nullable=False)

    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="detection", cascade="all, delete-orphan"
    )


class Prediction(Base):
    """Prédiction secondaire d'une détection (jamais la primaire, cf. contrat §10.1-2)."""

    __tablename__ = "predictions"
    __table_args__ = (Index("idx_predictions_detection", "detection_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    detection_id: Mapped[int] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), nullable=False
    )
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    detection: Mapped[Detection] = relationship(back_populates="predictions")
