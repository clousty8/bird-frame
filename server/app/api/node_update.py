"""Mise à jour des nœuds — contrat §12.

`GET /nodes/{node_id}/update` annonce la dernière version du bridge (= version du serveur) et
l'empreinte du bundle ; `GET /nodes/{node_id}/update/bundle` sert l'archive. Même
authentification que l'ingestion (§2.1, Bearer du nœud, vérifiée AVANT toute autre chose : un
nœud inconnu reçoit 404 `node_not_found`, un secret faux 401, même si aucun bundle n'existe).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.auth import get_authenticated_node
from app.errors import ApiError
from app.models.node import Node
from app.node_bundle import NodeBundle
from app.schemas.node_update import NodeUpdateInfo
from app.version import __version__

router = APIRouter(tags=["ingest"])


def current_node_bundle(request: Request) -> NodeBundle | None:
    return getattr(request.app.state, "node_bundle", None)


def _require_bundle(request: Request) -> NodeBundle:
    bundle = current_node_bundle(request)
    if bundle is not None:
        return bundle
    problem = getattr(request.app.state, "node_bundle_error", None)
    if problem:
        raise ApiError(
            503,
            "node_bundle_unavailable",
            f"Le bundle du bridge est configuré mais inutilisable : {problem}",
        )
    raise ApiError(
        404,
        "node_bundle_not_configured",
        "Ce serveur ne publie pas de bundle de mise à jour du bridge (BIRDFRAME_NODE_BUNDLE vide).",
    )


@router.get("/nodes/{node_id}/update", response_model=NodeUpdateInfo)
def get_node_update(request: Request, node: Node = Depends(get_authenticated_node)) -> dict:
    bundle = _require_bundle(request)
    return {
        "latest_version": __version__,
        "bundle_sha256": bundle.sha256,
        "bundle_size": bundle.size,
        "bundle_url": f"/api/v1/nodes/{node.id}/update/bundle",
    }


@router.get("/nodes/{node_id}/update/bundle")
def get_node_update_bundle(
    request: Request, node: Node = Depends(get_authenticated_node)
) -> FileResponse:
    bundle = _require_bundle(request)
    return FileResponse(
        bundle.path,
        media_type="application/gzip",
        filename=f"node-bundle-{bundle.version}.tar.gz",
        headers={"Cache-Control": "no-store", "X-Bundle-SHA256": bundle.sha256},
    )
