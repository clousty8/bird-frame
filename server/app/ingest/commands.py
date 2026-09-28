"""File de commandes serveur → nœud — architecture.md §7.2, contrat §5.

Portée de ce lot : seul `POST /nodes/register` (WP-07) enqueue une commande
(`set_main_name`). La boucle de poll dédiée (`GET /nodes/{id}/commands`,
`POST .../ack`) est hors périmètre (WP-11) ; `deliver_due_commands` n'est utilisée ici
que pour peupler le champ bonus `commands` de la réponse de sync (contrat §4.2), avec la
même sémantique de livraison qu'imposerait `GET /commands` (§4.7).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.node_command import NodeCommand
from app.time_utils import parse_stored_utc, utc_now, utc_now_str

REDELIVER_AFTER_S = 120


def enqueue_command(
    db: Session,
    node_id: int,
    kind: str,
    payload: dict,
    *,
    expires_at: str | None = None,
    origin_type: str | None = None,
    origin_id: int | None = None,
) -> NodeCommand:
    cmd = NodeCommand(
        node_id=node_id,
        kind=kind,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="pending",
        expires_at=expires_at,
        origin_type=origin_type,
        origin_id=origin_id,
    )
    db.add(cmd)
    db.flush()
    return cmd


def serialize_command_info(cmd: NodeCommand) -> dict:
    """Forme `CommandInfo` (contrat §6.1), utilisée par toutes les routes navigateur qui
    exposent des commandes (règles, seuils dynamiques, revues, audit `/commands`)."""
    return {
        "command_id": cmd.id,
        "node_id": cmd.node_id,
        "kind": cmd.kind,
        "payload": json.loads(cmd.payload_json),
        "status": cmd.status,
        "created_at": cmd.created_at,
        "delivered_at": cmd.delivered_at,
        "applied_at": cmd.applied_at,
        "expires_at": cmd.expires_at,
        "error_message": cmd.error_message,
        "result": json.loads(cmd.result_json) if cmd.result_json else None,
    }


def deliver_due_commands(db: Session, node_id: int, limit: int = 20) -> list[NodeCommand]:
    """Commandes `pending` (livrées maintenant) ou `delivered` depuis > 120 s sans ack
    (redélivrance), triées par `id` croissant — sémantique de livraison du contrat §4.7.
    """
    now = utc_now()
    now_str = utc_now_str()
    candidates = (
        db.query(NodeCommand)
        .filter(NodeCommand.node_id == node_id, NodeCommand.status.in_(("pending", "delivered")))
        .order_by(NodeCommand.id.asc())
        .all()
    )
    delivered: list[NodeCommand] = []
    for cmd in candidates:
        if cmd.expires_at is not None:
            expires_dt = parse_stored_utc(cmd.expires_at)
            if expires_dt is not None and expires_dt <= now:
                cmd.status = "expired"
                continue
        if cmd.status == "pending":
            cmd.status = "delivered"
            cmd.delivered_at = now_str
            delivered.append(cmd)
        else:  # "delivered" depuis assez longtemps
            delivered_dt = parse_stored_utc(cmd.delivered_at)
            if delivered_dt is not None and (now - delivered_dt).total_seconds() >= REDELIVER_AFTER_S:
                cmd.delivered_at = now_str
                delivered.append(cmd)
        if len(delivered) >= limit:
            break
    db.commit()
    return delivered
