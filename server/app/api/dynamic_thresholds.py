"""`GET`/`DELETE /sites/{slug}/dynamic-thresholds` — contrat §6.23, §6.24 (WP-14).

Miroir lecture seule du dernier heartbeat de chaque nœud (aucun appel réseau vers le
nœud ici) : `node_status.dynamic_thresholds_snapshot_json` est déjà rempli par
`POST /nodes/{id}/heartbeat` (`app/api/ingest.py`, WP core), avec les noms déjà
canonicalisés (§1.6) à la réception.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.deps import get_db, get_species_data
from app.errors import ApiError
from app.ingest.canonical import aliases_for
from app.ingest.commands import serialize_command_info
from app.live.compute import resolve_common_name_fr
from app.models.node import Node, NodeStatus
from app.models.node_command import NodeCommand
from app.species_data.store import SpeciesDataStore
from app.time_utils import round4

router = APIRouter(tags=["dynamic-thresholds"])

_PENDING_RESET_STATUSES = ("pending", "delivered")


def _site_nodes(db: Session, site_id: int) -> list[Node]:
    return db.query(Node).filter(Node.site_id == site_id, Node.decommissioned_at.is_(None)).all()


def _pending_resets(db: Session, node_ids: list[int]) -> set[tuple[int, str]]:
    if not node_ids:
        return set()
    rows = (
        db.query(NodeCommand)
        .filter(
            NodeCommand.node_id.in_(node_ids),
            NodeCommand.kind == "reset_dynamic_threshold",
            NodeCommand.status.in_(_PENDING_RESET_STATUSES),
        )
        .all()
    )
    pending: set[tuple[int, str]] = set()
    for cmd in rows:
        payload = json.loads(cmd.payload_json)
        pending.add((cmd.node_id, payload["scientific_name"]))
    return pending


@router.get("/sites/{slug}/dynamic-thresholds")
def get_dynamic_thresholds(
    slug: str, db: Session = Depends(get_db), store: SpeciesDataStore = Depends(get_species_data)
) -> dict:
    site = get_site_or_404(db, slug)
    nodes = _site_nodes(db, site.id)
    pending = _pending_resets(db, [n.id for n in nodes])

    snapshot_at: str | None = None
    thresholds: list[dict] = []
    for node in nodes:
        status_row = db.get(NodeStatus, node.id)
        if status_row is None or not status_row.dynamic_thresholds_snapshot_json:
            continue
        if status_row.dynamic_thresholds_snapshot_at and (
            snapshot_at is None or status_row.dynamic_thresholds_snapshot_at > snapshot_at
        ):
            # Les chaînes `...Z` trient lexicographiquement comme des instants (§1.3).
            snapshot_at = status_row.dynamic_thresholds_snapshot_at
        entries = json.loads(status_row.dynamic_thresholds_snapshot_json)
        for entry in entries:
            scientific_name = entry["scientific_name"]
            thresholds.append(
                {
                    "node_id": node.id,
                    "scientific_name": scientific_name,
                    "common_name_fr": resolve_common_name_fr(scientific_name, store, db),
                    "node_species_name": entry["species_name"],
                    "level": entry["level"],
                    # Contrat §1.2 : seuils arrondis à 4 décimales dans les réponses navigateur
                    # (BirdNET-Go envoie des float32 : 0.6 arrivait en 0.6000000238418579).
                    "current_value": round4(entry["current_value"]),
                    "base_threshold": round4(entry["base_threshold"]),
                    "high_conf_count": entry["high_conf_count"],
                    "trigger_count": entry["trigger_count"],
                    "is_active": entry["is_active"],
                    "expires_at": entry.get("expires_at_utc"),
                    "last_triggered_at": entry.get("last_triggered_utc"),
                    "first_created_at": entry.get("first_created_utc"),
                    "reset_pending": (node.id, scientific_name) in pending,
                }
            )

    thresholds.sort(key=lambda t: t["scientific_name"])
    thresholds.sort(key=lambda t: t["level"], reverse=True)

    return {"site_slug": site.slug, "snapshot_at": snapshot_at, "thresholds": thresholds}


@router.delete("/sites/{slug}/dynamic-thresholds/{scientific_name}", status_code=202)
def reset_dynamic_threshold(
    slug: str,
    scientific_name: str,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    canonical = store.resolve_reference(scientific_name) or scientific_name.strip().replace("_", " ")
    nodes = _site_nodes(db, site.id)
    aliases = aliases_for(canonical, store.aliases)

    created: list[NodeCommand] = []
    for node in nodes:
        status_row = db.get(NodeStatus, node.id)
        if status_row is None or not status_row.dynamic_thresholds_snapshot_json:
            continue
        entries = json.loads(status_row.dynamic_thresholds_snapshot_json)
        if not any(e["scientific_name"] == canonical for e in entries):
            continue
        payload = {"scientific_name": canonical, "aliases": aliases}
        cmd = NodeCommand(
            node_id=node.id,
            kind="reset_dynamic_threshold",
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="pending",
            origin_type="dynamic_threshold",
        )
        db.add(cmd)
        created.append(cmd)

    if not created:
        raise ApiError(
            404, "threshold_not_found", f"Aucun seuil dynamique actif pour « {canonical} » sur ce site."
        )

    db.commit()
    return {"commands": [serialize_command_info(c) for c in created]}
