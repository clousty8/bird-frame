"""Dépendances FastAPI partagées, toutes lues depuis `request.app.state`.

Chaque application (le process de production, ou une par test) construit son propre
moteur DB / config / bus « en écoute » dans `create_app()` (`app/main.py`) — ça isole
complètement les tests entre eux et du process réel, sans dépendance à un singleton module.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.live.pending_bus import PendingBus
from app.species_data.store import SpeciesDataStore


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session]:
    db = request.app.state.session_local()
    try:
        yield db
    finally:
        db.close()


def get_session_factory(request: Request) -> Callable[[], Session]:
    """La fabrique de sessions elle-même (pas une session déjà ouverte) : pour une route
    dont le corps de réponse vit potentiellement des heures (SSE, `app/api/sites.py`
    `pending_stream`), `Depends(get_db)` retiendrait une connexion du pool SQLite pendant
    toute la durée du flux (le `db.close()` du `finally` ne s'exécute qu'après l'envoi
    complet de la réponse). Cette dépendance n'ouvre rien : chaque poll du flux ouvre et
    referme sa propre session courte via cette fabrique.
    """
    return request.app.state.session_local


def get_species_data(request: Request) -> SpeciesDataStore:
    return request.app.state.species_data


def get_pending_bus(request: Request) -> PendingBus:
    return request.app.state.pending_bus


def get_photo_failures(request: Request) -> dict[str, datetime]:
    return request.app.state.photo_failures
