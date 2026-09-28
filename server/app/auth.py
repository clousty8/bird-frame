"""Authentification — contrat §2 et §3.

Deux familles distinctes : `Authorization: Bearer <bridge_shared_secret>` pour
l'ingestion nœud→serveur (§2.1), `X-Admin-Token` pour les routes admin (§3).
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_db, get_settings_dep
from app.errors import ApiError
from app.models.node import Node, NodeStatus
from app.time_utils import utc_now_str


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def require_admin_token(
    x_admin_token: str | None = Header(default=None),
    app_settings: Settings = Depends(get_settings_dep),
) -> None:
    """Dépendance FastAPI pour les routes sous `X-Admin-Token` (contrat §3).

    Jeton absent côté serveur (non configuré) → refusé aussi, comme documenté :
    « la route est donc inutilisable tant que le jeton n'est pas configuré ».
    """
    configured = app_settings.admin_token
    if not configured or not x_admin_token or not hmac.compare_digest(x_admin_token, configured):
        raise ApiError(401, "invalid_admin_token", "Jeton d'administration absent ou invalide.")


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
        return None
    return parts[1]


def get_authenticated_node(
    node_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Node:
    """Résout et authentifie le nœud `{node_id}` d'une route d'ingestion (contrat §2.1).

    Ordre imposé par le contrat : 404 si le nœud n'existe pas, puis 401 si l'en-tête est
    absent/mal formé/faux, puis 403 si le nœud est décommissionné. Toute requête
    authentifiée avec succès (quel que soit le code métier renvoyé ensuite) met à jour
    `node_status.last_seen_at` — donc *avant* toute validation du corps (FastAPI résout
    les dépendances de la route avant de parser le corps).
    """
    node = db.get(Node, node_id)
    if node is None:
        raise ApiError(404, "node_not_found", f"Aucun nœud avec l'id {node_id}.")

    secret = _extract_bearer(authorization)
    if secret is None or not hmac.compare_digest(hash_secret(secret), node.bridge_shared_secret_hash):
        raise ApiError(
            401,
            "unauthorized",
            "Authentification manquante ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if node.decommissioned_at is not None:
        raise ApiError(403, "node_decommissioned", "Ce nœud a été mis hors service.")

    status_row = db.get(NodeStatus, node.id)
    if status_row is None:
        status_row = NodeStatus(node_id=node.id)
        db.add(status_row)
    status_row.last_seen_at = utc_now_str()
    db.commit()

    return node
