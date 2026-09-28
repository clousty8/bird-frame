"""Commandes `node_commands` — deux côtés distincts (contrat §4.7, §4.8, §6.29) :

- côté bridge (Bearer nœud) : `GET /nodes/{id}/commands` (poll), `POST .../ack` (WP-11,
  complété ici) ;
- côté navigateur (S1 sans auth) : `GET /sites/{slug}/commands`, audit multi-nœuds.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.auth import get_authenticated_node
from app.deps import get_db
from app.errors import ApiError
from app.ingest.commands import deliver_due_commands, serialize_command_info
from app.models.node import Node
from app.models.node_command import COMMAND_KINDS, COMMAND_STATUSES, NodeCommand
from app.models.review import Review
from app.schemas.commands import AckCommandBody
from app.time_utils import utc_now_str

router = APIRouter(tags=["commands"])


@router.get("/nodes/{node_id}/commands")
def get_node_commands(
    limit: int = Query(default=20, ge=1, le=50),
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
) -> dict:
    commands = deliver_due_commands(db, node.id, limit=limit)
    return {
        "commands": [
            {
                "id": c.id,
                "kind": c.kind,
                "payload": json.loads(c.payload_json),
                "created_at": c.created_at,
                "expires_at": c.expires_at,
            }
            for c in commands
        ]
    }


def _review_for_command(db: Session, cmd: NodeCommand) -> Review | None:
    if cmd.origin_type != "review" or cmd.origin_id is None:
        return None
    return db.get(Review, cmd.origin_id)


@router.post("/nodes/{node_id}/commands/{cmd_id}/ack")
def ack_command(
    cmd_id: int,
    body: AckCommandBody,
    node: Node = Depends(get_authenticated_node),
    db: Session = Depends(get_db),
) -> dict:
    cmd = db.query(NodeCommand).filter(NodeCommand.id == cmd_id, NodeCommand.node_id == node.id).first()
    if cmd is None:
        raise ApiError(404, "command_not_found", f"Commande {cmd_id} inconnue pour ce nœud.")

    if cmd.status in ("applied", "failed", "expired"):
        # Idempotent : un ack identique à l'état final déjà enregistré est un 200 sans
        # effet (contrat §4.8) ; un ack différent d'un état final est un conflit.
        if cmd.status == body.status:
            return {"id": cmd.id, "status": cmd.status}
        raise ApiError(409, "command_already_final", f"Commande déjà finalisée avec le statut {cmd.status!r}.")

    now_str = utc_now_str()
    cmd.status = body.status
    cmd.applied_at = now_str
    cmd.result_json = json.dumps(body.result, ensure_ascii=False) if body.result is not None else None
    cmd.error_message = body.error

    if body.status == "applied" and cmd.kind == "mark_detection_reviewed":
        # Jamais d'écriture directe dans les tables de BirdNET-Go (architecture.md §7.5) :
        # ce champ trace seulement que la répercussion a réussi, côté serveur.
        review = _review_for_command(db, cmd)
        if review is not None:
            review.synced_to_node_at = now_str

    db.commit()
    return {"id": cmd.id, "status": cmd.status}


@router.get("/sites/{slug}/commands")
def get_site_commands(
    slug: str,
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    site = get_site_or_404(db, slug)
    if status is not None and status not in COMMAND_STATUSES:
        raise ApiError(422, "validation_error", f"status invalide : {status!r}.")
    if kind is not None and kind not in COMMAND_KINDS:
        raise ApiError(422, "validation_error", f"kind invalide : {kind!r}.")

    query = (
        db.query(NodeCommand).join(Node, Node.id == NodeCommand.node_id).filter(Node.site_id == site.id)
    )
    if status:
        query = query.filter(NodeCommand.status == status)
    if kind:
        query = query.filter(NodeCommand.kind == kind)

    total = query.count()
    rows = query.order_by(NodeCommand.id.desc()).offset(offset).limit(limit).all()

    return {
        "commands": [serialize_command_info(c) for c in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
