"""Calcul de la liste « en écoute » effective d'un site — contrat §4.5 et §6.1 (`online`).

Utilisé par `GET /sites/{slug}/now`, la diffusion SSE (§6.4) et la boucle qui réévalue
l'expiration toutes les 5 s même sans nouvel instantané reçu.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.live.pending_bus import PendingBus
from app.models.node import Node, NodeStatus
from app.species_data.naming import quote_species_name
from app.species_data.store import SpeciesDataStore
from app.time_utils import parse_stored_utc

ONLINE_TTL_S = 90
ACTIVE_TTL_S = 90
TERMINAL_TTL_S = 20  # approved / rejected


def node_is_online(status_row: NodeStatus | None, now: datetime) -> bool:
    if status_row is None or status_row.last_seen_at is None:
        return False
    last_seen = parse_stored_utc(status_row.last_seen_at)
    if last_seen is None:
        return False
    return (now - last_seen).total_seconds() < ONLINE_TTL_S


def resolve_common_name_fr(scientific_name: str, store: SpeciesDataStore, db: Session) -> str | None:
    name = store.common_name_fr(scientific_name)
    if name:
        return name
    from app.models.species_name import SpeciesName

    cached = db.get(SpeciesName, scientific_name)
    return cached.common_name_fr if cached else None


def photo_url_for(scientific_name: str, store: SpeciesDataStore) -> str | None:
    if not store.has_photo(scientific_name):
        return None
    return f"/api/v1/species/{quote_species_name(scientific_name)}/photo?size=320"


def _expire_items(items: list[dict], received_at_unix: int, now_unix: int) -> list[dict]:
    age = now_unix - received_at_unix
    kept = []
    for item in items:
        if item["status"] in ("approved", "rejected"):
            if age < TERMINAL_TTL_S:
                kept.append(item)
        else:
            if now_unix - item["last_updated_unix"] < ACTIVE_TTL_S:
                kept.append(item)
    return kept


def compute_site_pending(
    db: Session, site_id: int, bus: PendingBus, store: SpeciesDataStore, now: datetime | None = None
) -> list[dict]:
    """Liste `PendingItem` effective du site, triée `first_detected_unix` puis `scientific_name`."""
    now = now or datetime.now(UTC)
    now_unix = int(now.timestamp())

    nodes = (
        db.query(Node)
        .filter(Node.site_id == site_id, Node.decommissioned_at.is_(None))
        .all()
    )
    result: list[dict] = []
    for node in nodes:
        status_row = db.get(NodeStatus, node.id)
        if not node_is_online(status_row, now):
            continue
        snapshot = bus.node_snapshot(node.id)
        if snapshot is None:
            continue
        items = _expire_items(snapshot["items"], snapshot["received_at_unix"], now_unix)
        for item in items:
            result.append(
                {
                    "node_id": node.id,
                    "scientific_name": item["scientific_name"],
                    "common_name_fr": resolve_common_name_fr(item["scientific_name"], store, db),
                    "status": item["status"],
                    "hit_count": item["hit_count"],
                    "confidence_hint": item.get("confidence_hint"),
                    "first_detected_unix": item["first_detected_unix"],
                    "last_updated_unix": item["last_updated_unix"],
                    "source_id": item.get("source_id"),
                    "photo_url": photo_url_for(item["scientific_name"], store),
                }
            )
    result.sort(key=lambda it: (it["first_detected_unix"], it["scientific_name"]))
    return result
