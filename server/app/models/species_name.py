from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str


class SpeciesName(Base):
    """Cache de noms communs FR alimenté par le bridge (§1.6 niveau 3, contrat §9.5).

    Utilisé quand `species-data/base/` et `species_universe_fr.json` n'ont pas le nom
    (espèce hors univers France, ex. détectée par erreur ou nouvelle pour le modèle).
    """

    __tablename__ = "species_names"

    scientific_name: Mapped[str] = mapped_column(String, primary_key=True)
    common_name_fr: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="bridge")
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
