from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str


class SpeciesSheet(Base):
    """Cache en base des fichiers `species-data/base/*.json` + `sheets/*.json` (WP-10).

    La source de vérité reste les fichiers versionnés (architecture.md §9) ; cette table
    n'est qu'un cache rechargé au démarrage et par `POST /admin/species-data/reload`. Le
    contrat §9.7 autorise explicitement à stocker le JSON brut plutôt que des colonnes
    éclatées — seul le format de réponse `GET /species/{name}` compte.
    """

    __tablename__ = "species_sheets"

    scientific_name: Mapped[str] = mapped_column(String, primary_key=True)
    base_json: Mapped[str | None] = mapped_column(String, nullable=True)
    sheet_json: Mapped[str | None] = mapped_column(String, nullable=True)
    has_sheet: Mapped[bool] = mapped_column(nullable=False, default=False)
    loaded_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
