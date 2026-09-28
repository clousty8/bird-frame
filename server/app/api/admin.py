"""Routes admin (`X-Admin-Token`) — contrat §3."""

from __future__ import annotations

import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import hash_secret, require_admin_token
from app.config import Settings
from app.deps import get_db, get_settings_dep
from app.errors import ApiError
from app.ingest.commands import enqueue_command
from app.models.node import Node, NodeSyncState
from app.models.site import Site
from app.schemas.admin import RegisterNodeBody, RegisterNodeResponse, SpeciesDataReloadResponse
from app.species_data.db_sync import sync_species_sheets_table
from app.species_data.store import load_species_data

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin_token)])


@router.post("/nodes/register", response_model=RegisterNodeResponse, status_code=201)
def register_node(body: RegisterNodeBody, db: Session = Depends(get_db)) -> dict:
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ApiError(422, "validation_error", f"Fuseau inconnu : {body.timezone!r}.") from exc

    site = db.query(Site).filter(Site.slug == body.site_slug).first()
    site_created = False
    if site is None:
        site = Site(name=body.site_name, slug=body.site_slug, timezone=body.timezone, lat=body.lat, lon=body.lon)
        db.add(site)
        db.flush()
        site_created = True

    secret = secrets.token_urlsafe(32)
    node = Node(site_id=site.id, name=body.node_name, bridge_shared_secret_hash=hash_secret(secret))
    db.add(node)
    db.flush()

    db.add(NodeSyncState(node_id=node.id, last_synced_detection_id=0))

    if body.auto_main_name:
        enqueue_command(
            db, node.id, "set_main_name", {"name": body.site_slug}, origin_type="register", origin_id=node.id
        )

    db.commit()

    return {
        "node_id": node.id,
        "site_id": site.id,
        "site_slug": site.slug,
        "site_created": site_created,
        "bridge_shared_secret": secret,
    }


@router.post("/admin/species-data/reload", response_model=SpeciesDataReloadResponse)
def reload_species_data(
    request: Request,
    db: Session = Depends(get_db),
    app_settings: Settings = Depends(get_settings_dep),
) -> dict:
    store = load_species_data(app_settings.species_data_dir_resolved)
    sync_species_sheets_table(db, store)
    request.app.state.species_data = store
    return {
        "universe_count": store.universe_count,
        "base_count": store.base_count,
        "sheet_count": store.sheet_count,
        "alias_count": store.alias_count,
        "invalid_files": [f.as_dict() for f in store.invalid_files],
        "loaded_at": store.loaded_at,
    }
