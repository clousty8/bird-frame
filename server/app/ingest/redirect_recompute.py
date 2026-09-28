"""Job de rattrapage : recalcule `detections.redirected_to_scientific_name` pour toutes
les détections déjà en base d'un (site, espèce) quand une règle `redirect` est créée,
modifiée ou supprimée — architecture.md §7.6, contrat §6.21 effet 2.

Synchrone (exécuté dans la même requête que le PUT/DELETE de la règle) : le volume visé
(échelle familiale) ne justifie pas un job asynchrone séparé (pas de sur-ingénierie).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.detection import Detection


def recompute_redirect_for_site_species(
    db: Session, site_id: int, scientific_name: str, redirect_to: str | None
) -> None:
    db.query(Detection).filter(
        Detection.site_id == site_id, Detection.scientific_name == scientific_name
    ).update({"redirected_to_scientific_name": redirect_to}, synchronize_session=False)
