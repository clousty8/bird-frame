"""Routes `/sites` — contrat §6.2 à §6.7 (liste, « en écoute », SSE, calendrier, espèces du site)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.common_lookups import (
    get_site_or_404,
    impossible_names_for_site,
    rules_by_species_for_site,
)
from app.api.node_status import build_node_status, pick_principal_node
from app.deps import get_db, get_pending_bus, get_session_factory, get_species_data
from app.errors import ApiError
from app.ingest.valid_detection import is_valid_detection_expr
from app.live.compute import (
    compute_site_pending,
    node_is_online,
    photo_url_for,
    resolve_common_name_fr,
)
from app.live.pending_bus import PendingBus
from app.models.detection import Detection
from app.models.node import Node, NodeStatus
from app.models.site import Site
from app.species_data.naming import fold_diacritics
from app.species_data.store import SpeciesDataStore
from app.time_utils import (
    parse_local_date,
    round4,
    round_latlon,
    site_zone,
    today_local,
    utc_now_str,
)

logger = logging.getLogger("bird_frame.sites")

router = APIRouter(tags=["sites"])

_RECENT_LIMIT = 10
_SSE_HEARTBEAT_S = 15


@router.get("/sites")
def list_sites(db: Session = Depends(get_db)) -> dict:
    sites = db.query(Site).order_by(Site.name.asc()).all()
    return {"sites": [_site_summary(db, s) for s in sites]}


def _site_summary(db: Session, site: Site) -> dict:
    now = datetime.now(UTC)
    nodes = db.query(Node).filter(Node.site_id == site.id, Node.decommissioned_at.is_(None)).all()
    online = any(node_is_online(db.get(NodeStatus, n.id), now) for n in nodes)

    total_detections = (
        db.query(func.count(Detection.id))
        .filter(Detection.site_id == site.id, is_valid_detection_expr())
        .scalar()
        or 0
    )
    last_detection_at = (
        db.query(func.max(Detection.detected_at_utc))
        .filter(Detection.site_id == site.id, is_valid_detection_expr())
        .scalar()
    )
    return {
        "slug": site.slug,
        "name": site.name,
        "timezone": site.timezone,
        "lat": round_latlon(site.lat),
        "lon": round_latlon(site.lon),
        "created_at": site.created_at,
        "node_count": len(nodes),
        "online": online,
        "last_detection_at": last_detection_at,
        "total_detections": total_detections,
    }


@router.get("/sites/{slug}/now")
def get_now(
    slug: str,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
    bus: PendingBus = Depends(get_pending_bus),
) -> dict:
    site = get_site_or_404(db, slug)
    now = datetime.now(UTC)

    pending_list = compute_site_pending(db, site.id, bus, store, now=now)
    principal = pick_principal_node(db, site.id)
    node_status = build_node_status(db, principal, site=site, now=now) if principal else None
    recent = _recent_detections(db, site, store, limit=_RECENT_LIMIT)

    return {
        "site_slug": site.slug,
        "server_time_utc": utc_now_str(),
        "pending": pending_list,
        "node_status": node_status,
        "recent": recent,
    }


def _recent_detections(db: Session, site: Site, store: SpeciesDataStore, limit: int) -> list[dict]:
    impossible = impossible_names_for_site(db, site.id)
    # Sur-fetch pour absorber les exclusions "impossible" côté Python sans re-round-trip
    # (en pratique cet ensemble est presque toujours vide tant que WP-12 n'existe pas).
    candidates = (
        db.query(Detection)
        .filter(Detection.site_id == site.id, is_valid_detection_expr())
        .order_by(Detection.detected_at_utc.desc(), Detection.id.desc())
        .limit(limit * 10 + 50)
        .all()
    )
    result = []
    for d in candidates:
        effective = d.redirected_to_scientific_name or d.scientific_name
        if effective in impossible:
            continue
        result.append(
            {
                "detection_id": d.id,
                "scientific_name": effective,
                "common_name_fr": resolve_common_name_fr(effective, store, db),
                "confidence": round4(d.confidence),
                "detected_at_utc": d.detected_at_utc,
                "photo_url": photo_url_for(effective, store),
            }
        )
        if len(result) >= limit:
            break
    return result


@router.get("/sites/{slug}/pending/stream")
async def pending_stream(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
    bus: PendingBus = Depends(get_pending_bus),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
) -> StreamingResponse:
    site = get_site_or_404(db, slug)
    # `db` (Depends(get_db)) ne sert qu'à cette résolution du site : ce flux peut vivre
    # des heures, et FastAPI ne referme une dépendance à `yield` qu'une fois la réponse
    # entièrement envoyée — la garder ouverte tiendrait une connexion du pool SQLite
    # pendant toute la durée du flux (contrat de disponibilité pour le bridge, §4).
    # `sse_event_stream` reçoit donc la fabrique de sessions, pas une session, et ouvre/
    # referme une session courte à chaque poll.
    generator = sse_event_stream(session_factory, store, bus, site.id, site.slug, request.is_disconnected)
    return StreamingResponse(
        generator,
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def sse_event_stream(
    session_factory: Callable[[], Session],
    store: SpeciesDataStore,
    bus: PendingBus,
    site_id: int,
    site_slug: str,
    is_disconnected,
):
    """Corps du flux SSE, extrait de la route pour être testable directement (appel
    `.__anext__()`/`.aclose()`) sans dépendre des subtilités de déconnexion du transport
    HTTP de test — voir `tests/test_pending_now.py`.
    """
    queue = bus.subscribe(site_id)
    try:
        yield "retry: 3000\n\n"
        pending_list = await run_in_threadpool(_read_site_pending, session_factory, site_id, bus, store)
        yield _format_sse("pending", {"site_slug": site_slug, "updated_at_utc": utc_now_str(), "pending": pending_list})

        while True:
            if await is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_S)
            except TimeoutError:
                online = await run_in_threadpool(_read_site_online, session_factory, site_id)
                yield _format_sse("heartbeat", {"server_time_utc": utc_now_str(), "node_online": online})
                continue

            if message["event"] == "pending":
                data = dict(message["data"])
                data["site_slug"] = site_slug
                yield _format_sse("pending", data)
            else:
                yield _format_sse(message["event"], message["data"])
    finally:
        bus.unsubscribe(site_id, queue)


def _read_site_pending(
    session_factory: Callable[[], Session], site_id: int, bus: PendingBus, store: SpeciesDataStore
) -> list[dict]:
    # Session courte, ouverte et refermée pour ce seul poll (voir get_session_factory) :
    # pas de connexion tenue hors d'usage pendant les ~15 s entre deux polls du flux SSE.
    db = session_factory()
    try:
        return compute_site_pending(db, site_id, bus, store)
    finally:
        db.close()


def _read_site_online(session_factory: Callable[[], Session], site_id: int) -> bool:
    # `online` du nœud PRINCIPAL uniquement (`pick_principal_node`, comme `GET
    # /sites/{slug}/now`) — pas de n'importe quel nœud du site : sinon un nœud
    # secondaire encore en ligne masquerait la panne du nœud principal dans l'event
    # `heartbeat`, en contradiction avec `/now` sur le même site (contrat §6.4).
    db = session_factory()
    try:
        now = datetime.now(UTC)
        principal = pick_principal_node(db, site_id)
        if principal is None:
            return False
        return node_is_online(db.get(NodeStatus, principal.id), now)
    finally:
        db.close()


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


@router.get("/sites/{slug}/calendar")
def get_calendar(
    slug: str,
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    local_date = date or today_local(site.timezone)
    try:
        parse_local_date(local_date)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc

    impossible = impossible_names_for_site(db, site.id)
    rows = (
        db.query(Detection)
        .filter(
            Detection.site_id == site.id,
            Detection.detected_local_date == local_date,
            is_valid_detection_expr(),
        )
        .all()
    )

    by_species: dict[str, dict] = {}
    for d in rows:
        effective = d.redirected_to_scientific_name or d.scientific_name
        if effective in impossible:
            continue
        entry = by_species.get(effective)
        if entry is None:
            entry = {
                "total": 0,
                "max_confidence": 0.0,
                "first_utc": d.detected_at_utc,
                "last_utc": d.detected_at_utc,
                "hours": [0] * 24,
            }
            by_species[effective] = entry
        entry["total"] += 1
        entry["max_confidence"] = max(entry["max_confidence"], d.confidence)
        entry["first_utc"] = min(entry["first_utc"], d.detected_at_utc)
        entry["last_utc"] = max(entry["last_utc"], d.detected_at_utc)
        entry["hours"][d.detected_local_hour] += 1

    species_list = [
        {
            "scientific_name": name,
            "common_name_fr": resolve_common_name_fr(name, store, db),
            "total": entry["total"],
            "max_confidence": round4(entry["max_confidence"]),
            "first_utc": entry["first_utc"],
            "last_utc": entry["last_utc"],
            "hours": entry["hours"],
            "photo_url": photo_url_for(name, store),
        }
        for name, entry in by_species.items()
    ]
    species_list.sort(key=lambda s: s["scientific_name"])
    species_list.sort(key=lambda s: s["total"], reverse=True)

    sunrise_utc, sunset_utc = _sun_times(site, local_date)

    return {
        "site_slug": site.slug,
        "date": local_date,
        "timezone": site.timezone,
        "sunrise_utc": sunrise_utc,
        "sunset_utc": sunset_utc,
        "total_detections": sum(s["total"] for s in species_list),
        "species": species_list,
    }


def _sun_times(site: Site, local_date_str: str) -> tuple[str | None, str | None]:
    if site.lat is None or site.lon is None:
        return None, None
    try:
        from astral import LocationInfo
        from astral.sun import sun

        from app.time_utils import format_utc_instant

        location = LocationInfo(latitude=site.lat, longitude=site.lon)
        day = parse_local_date(local_date_str)
        result = sun(location.observer, date=day, tzinfo=site_zone(site.timezone))
        return (
            format_utc_instant(result["sunrise"].astimezone(UTC)),
            format_utc_instant(result["sunset"].astimezone(UTC)),
        )
    except Exception as exc:  # noqa: BLE001 — jour polaire, bibliothèque absente… jamais bloquant
        logger.warning("lever/coucher du soleil indisponible pour %s le %s : %s", site.slug, local_date_str, exc)
        return None, None


@router.get("/sites/{slug}/species")
def get_site_species(
    slug: str,
    sort: str = Query(default="total"),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    if sort not in ("total", "last_seen", "common_name"):
        raise ApiError(422, "validation_error", f"sort invalide : {sort!r}")

    rows = db.query(Detection).filter(Detection.site_id == site.id, is_valid_detection_expr()).all()

    by_species: dict[str, dict] = {}
    for d in rows:
        entry = by_species.get(d.scientific_name)
        if entry is None:
            entry = {
                "total": 0,
                "max_confidence": 0.0,
                "first_seen_utc": d.detected_at_utc,
                "last_seen_utc": d.detected_at_utc,
                "days": set(),
            }
            by_species[d.scientific_name] = entry
        entry["total"] += 1
        entry["max_confidence"] = max(entry["max_confidence"], d.confidence)
        entry["first_seen_utc"] = min(entry["first_seen_utc"], d.detected_at_utc)
        entry["last_seen_utc"] = max(entry["last_seen_utc"], d.detected_at_utc)
        entry["days"].add(d.detected_local_date)

    rules = rules_by_species_for_site(db, site.id)

    species_list = []
    for name, entry in by_species.items():
        common_name = resolve_common_name_fr(name, store, db)
        rule = rules.get(name)
        species_list.append(
            {
                "scientific_name": name,
                "common_name_fr": common_name,
                "total": entry["total"],
                "first_seen_utc": entry["first_seen_utc"],
                "last_seen_utc": entry["last_seen_utc"],
                "max_confidence": round4(entry["max_confidence"]),
                "days_seen": len(entry["days"]),
                "photo_url": photo_url_for(name, store),
                "has_sheet": store.has_sheet(name),
                "in_france_universe": store.in_france_universe(name),
                "rule": rule.rule if rule else None,
                "redirect_to_scientific_name": (
                    rule.redirect_to_scientific_name if rule and rule.rule == "redirect" else None
                ),
            }
        )

    species_list.sort(key=lambda s: s["scientific_name"])
    if sort == "last_seen":
        species_list.sort(key=lambda s: s["last_seen_utc"], reverse=True)
    elif sort == "common_name":
        species_list.sort(key=lambda s: fold_diacritics(s["common_name_fr"] or s["scientific_name"]))
    else:
        species_list.sort(key=lambda s: s["total"], reverse=True)

    return {"site_slug": site.slug, "species": species_list}
