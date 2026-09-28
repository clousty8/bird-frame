"""Canonicalisation des noms d'espèces à l'ingestion — contrat §1.6.

`nom_canonique = aliases.get(nom_reçu, nom_reçu)` — comparaison exacte (pas de casse/
accents ici, contrairement à la résolution d'un nom d'espèce dans une URL, §1.6 aussi
mais qui, elle, est insensible à la casse).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.species_name import SpeciesName
from app.species_data.store import SpeciesDataStore
from app.time_utils import utc_now_str

logger = logging.getLogger("bird_frame.species_data")

# Noms déjà signalés par warn_if_unknown_species (une fois par nom et par processus).
_warned_unknown_names: set[str] = set()


def canonicalize_ingested_name(raw_name: str, aliases: dict[str, str]) -> str:
    return aliases.get(raw_name, raw_name)


def warn_if_unknown_species(scientific_name: str, store: SpeciesDataStore) -> None:
    """Contrat §7.3 : WARNING, une fois par nom, pour toute espèce ingérée (détection
    confirmée) absente de l'univers et de `base/` — le signal pour compléter
    `species-data/aliases.json` si c'est un synonyme. Les étiquettes non taxonomiques de
    BirdNET (`Dog`, `Human vocal`…) sont aussi signalées, une fois."""
    if scientific_name in _warned_unknown_names:
        return
    if store.in_france_universe(scientific_name) or scientific_name in store.base:
        return
    _warned_unknown_names.add(scientific_name)
    logger.warning(
        "espèce ingérée absente de l'univers et de base/ : %r — si c'est un synonyme, "
        "l'ajouter à species-data/aliases.json (contrat §7.3)",
        scientific_name,
    )


def aliases_for(scientific_name: str, aliases: dict[str, str]) -> list[str]:
    """Tous les noms bruts de `aliases.json` qui pointent vers `scientific_name` (contrat §5.2,
    champ commun `aliases` des commandes portant sur une espèce)."""
    return [raw for raw, canon in aliases.items() if canon == scientific_name]


def touch_species_name_cache(db: Session, scientific_name: str, common_name: str | None) -> None:
    """§1.6 niveau 3 : cache de noms alimenté par les payloads d'ingestion (sync, pending)."""
    if not common_name:
        return
    now = utc_now_str()
    existing = db.get(SpeciesName, scientific_name)
    if existing is None:
        db.add(
            SpeciesName(scientific_name=scientific_name, common_name_fr=common_name, source="bridge", updated_at=now)
        )
        # Sessions en autoflush=False : sans flush, un second appel pour le même nom dans
        # la même transaction (primaire et prédiction canonicalisées vers le même nom, ou
        # deux prédictions alias/canonique) ne verrait pas cette ligne en attente et en
        # ajouterait une seconde → IntegrityError, sync entier en 500.
        db.flush()
    elif existing.common_name_fr != common_name:
        existing.common_name_fr = common_name
        existing.updated_at = now
