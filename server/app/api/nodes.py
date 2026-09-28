"""`GET /nodes` — contrat §6.2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.node_status import build_node_status
from app.deps import get_db
from app.models.node import Node

router = APIRouter(tags=["nodes"])


@router.get("/nodes")
def list_nodes(
    include_decommissioned: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Node)
    if not include_decommissioned:
        query = query.filter(Node.decommissioned_at.is_(None))
    nodes = query.all()

    # tri par site_slug puis node_id (contrat §6.2)
    statuses = [build_node_status(db, n) for n in nodes]
    statuses.sort(key=lambda s: (s["site_slug"], s["node_id"]))
    return {"nodes": statuses}
