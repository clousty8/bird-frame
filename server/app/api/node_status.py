"""Construction de l'objet `NodeStatus` (contrat §6.1) — partagé par `GET /nodes` et
`GET /sites/{slug}/now`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.live.compute import node_is_online
from app.models.node import Node, NodeStatus, NodeSyncState
from app.models.site import Site
from app.time_utils import round1


def build_node_status(db: Session, node: Node, site: Site | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    site = site or db.get(Site, node.site_id)
    status_row = db.get(NodeStatus, node.id)
    sync_state = db.get(NodeSyncState, node.id)

    synced_up_to_id = sync_state.last_synced_detection_id if sync_state else 0
    node_db_max_id = status_row.node_db_max_id if status_row else None
    # Contrat §6.1 : `sync_lag` ≥ 0. Le heartbeat (≈ 1/min) rapporte un `node_db_max_id` plus
    # ancien que le curseur de sync (≈ toutes les quelques secondes) : la différence brute
    # devenait négative (« -2 détections en attente »).
    sync_lag = max(0, node_db_max_id - synced_up_to_id) if node_db_max_id is not None else None

    return {
        "node_id": node.id,
        "node_name": node.name,
        "site_slug": site.slug,
        "site_name": site.name,
        "online": node_is_online(status_row, now),
        "last_seen_at": status_row.last_seen_at if status_row else None,
        "last_sync_at": sync_state.last_sync_at if sync_state else None,
        "last_heartbeat_at": status_row.last_heartbeat_at if status_row else None,
        "last_detection_at": _last_detection_at(db, node.id),
        "mic_device_name": status_row.mic_device_name if status_row else None,
        "mic_healthy": status_row.mic_healthy if status_row else None,
        "disk_free_pct": round1(status_row.disk_free_pct) if status_row else None,
        "birdnet_go_reachable": status_row.birdnet_go_reachable if status_row else None,
        "birdnet_go_pid_alive": status_row.birdnet_go_pid_alive if status_row else None,
        "birdnet_go_version": status_row.birdnet_go_version if status_row else None,
        "bridge_version": status_row.bridge_version if status_row else None,
        "synced_up_to_id": synced_up_to_id,
        "node_db_max_id": node_db_max_id,
        "sync_lag": sync_lag,
        "decommissioned_at": node.decommissioned_at,
    }


def _last_detection_at(db: Session, node_id: int) -> str | None:
    from sqlalchemy import func

    from app.models.detection import Detection

    return db.query(func.max(Detection.detected_at_utc)).filter(Detection.node_id == node_id).scalar()


def pick_principal_node(db: Session, site_id: int) -> Node | None:
    """Nœud non décommissionné au `last_seen_at` le plus récent, à défaut le plus petit
    `node_id` (contrat §6.3). Les chaînes `...Z` trient lexicographiquement comme des
    instants (contrat §1.3), donc `max()` sur la chaîne suffit.
    """
    nodes = db.query(Node).filter(Node.site_id == site_id, Node.decommissioned_at.is_(None)).all()
    if not nodes:
        return None

    def last_seen(n: Node) -> str | None:
        status_row = db.get(NodeStatus, n.id)
        return status_row.last_seen_at if status_row else None

    with_last_seen = [n for n in nodes if last_seen(n)]
    if with_last_seen:
        return max(with_last_seen, key=lambda n: last_seen(n) or "")
    return min(nodes, key=lambda n: n.id)
