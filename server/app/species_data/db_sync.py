"""Réplique un `SpeciesDataStore` chargé dans la table `species_sheets` (WP-10).

La table est un cache : à chaque rechargement on la vide et la repeuple entièrement, pour
qu'un fichier supprimé ou devenu invalide disparaisse bien (pas de ligne fantôme).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.species_sheet import SpeciesSheet
from app.species_data.store import SpeciesDataStore
from app.time_utils import utc_now_str


def sync_species_sheets_table(db: Session, store: SpeciesDataStore) -> None:
    db.query(SpeciesSheet).delete()
    now = utc_now_str()
    names = set(store.base) | set(store.sheets)
    for name in names:
        db.add(
            SpeciesSheet(
                scientific_name=name,
                base_json=json.dumps(store.base[name], ensure_ascii=False) if name in store.base else None,
                sheet_json=json.dumps(store.sheets[name], ensure_ascii=False)
                if name in store.sheets
                else None,
                has_sheet=name in store.sheets,
                loaded_at=now,
            )
        )
    db.commit()
