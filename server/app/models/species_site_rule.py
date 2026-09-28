from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str


class SpeciesSiteRule(Base):
    """Règle présente/impossible/redirection pour une espèce sur un site (architecture.md §4).

    Hors périmètre WP-12 (aucune route de ce lot ne les crée) : table présente pour la
    complétude du schéma dès la première migration.
    """

    __tablename__ = "species_site_rules"
    __table_args__ = (
        UniqueConstraint("site_id", "scientific_name", name="uq_species_site_rules_site_species"),
        CheckConstraint(
            "rule IN ('present', 'impossible', 'redirect')", name="ck_species_site_rule_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    rule: Mapped[str] = mapped_column(String, nullable=False)
    threshold_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    redirect_to_scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    # Pointe vers `node_commands.origin_batch` du dernier PUT — voir le commentaire sur
    # `NodeCommand.origin_batch`. `NULL` = aucun PUT n'a encore eu lieu.
    last_command_batch: Mapped[str | None] = mapped_column(String, nullable=True)
