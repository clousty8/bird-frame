"""Point d'entrée FastAPI — `create_app()` construit une instance complète et isolée
(sa propre config, son propre moteur DB, son propre bus « en écoute »), pour que les
tests puissent en créer plusieurs en parallèle sans se marcher dessus. `app` en bas du
fichier est l'instance de production, celle que `uvicorn app.main:app` sert.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    commands,
    detections,
    dynamic_thresholds,
    health,
    ingest,
    nodes,
    recordings,
    reviews,
    sites,
    species,
    species_rules,
    stats,
)
from app.browser_auth import ConfigError, build_browser_auth
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.errors import ApiError, register_error_handlers
from app.live.compute import compute_site_pending
from app.live.pending_bus import PendingBus
from app.models.site import Site
from app.species_data.db_sync import sync_species_sheets_table
from app.species_data.store import load_species_data
from app.time_utils import utc_now_str

logger = logging.getLogger("bird_frame.main")

SERVER_VERSION = "0.1.0"
PENDING_EXPIRY_TICK_S = 5

_SERVER_DIR = Path(__file__).resolve().parent.parent


def run_migrations(app_settings: Settings) -> None:
    """`alembic upgrade head` contre la base de CETTE configuration (contrat : au
    démarrage, si `BIRDFRAME_AUTO_MIGRATE=1`, l'app applique les migrations elle-même).
    """
    cfg = Config(str(_SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_SERVER_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", app_settings.sqlalchemy_url)
    command.upgrade(cfg, "head")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    app_settings = app_settings or get_settings()
    # Avant tout le reste : en production, une configuration d'authentification
    # incomplète doit empêcher le serveur de démarrer (`ConfigError`), pas l'ouvrir.
    browser_auth = build_browser_auth(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_settings.data_dir_resolved.mkdir(parents=True, exist_ok=True)
        app_settings.clips_dir_resolved.mkdir(parents=True, exist_ok=True)
        app_settings.photos_dir_resolved.mkdir(parents=True, exist_ok=True)

        if app_settings.auto_migrate:
            run_migrations(app_settings)

        app.state.settings = app_settings
        engine = make_engine(app_settings)
        app.state.engine = engine
        app.state.session_local = make_session_factory(engine)
        app.state.pending_bus = PendingBus()
        app.state.pending_bus.bind_loop(asyncio.get_running_loop())
        app.state.photo_failures = {}

        store = load_species_data(app_settings.species_data_dir_resolved)
        app.state.species_data = store
        db = app.state.session_local()
        try:
            sync_species_sheets_table(db, store)
        finally:
            db.close()

        expiry_task = asyncio.create_task(_pending_expiry_loop(app))
        try:
            yield
        finally:
            expiry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await expiry_task
            engine.dispose()

    app = FastAPI(title="bird-frame server", version=SERVER_VERSION, lifespan=lifespan)
    app.state.browser_auth = browser_auth

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins_list,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Range", "Authorization", "X-Admin-Token"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
        allow_credentials=False,
    )

    # Constat #11 : `upload_clip` (app/api/ingest.py) ne vérifiait `len(content) >
    # max_upload_bytes` qu'APRÈS `await audio.read()` — Starlette a alors déjà reçu et
    # spoolé tout le corps multipart (potentiellement sur disque) avant que le code
    # applicatif ne s'exécute. Un `Content-Length` annoncé rejette la requête ici, avant
    # tout parsing de corps — seule défense fiable au niveau ASGI pour ce cas (un client
    # en transfert chunké sans Content-Length n'est pas couvert ; tous les clients de
    # cette API, bridge inclus, envoient Content-Length pour un upload en mémoire).
    # Marge au-delà de max_upload_bytes pour les en-têtes/limites multipart eux-mêmes
    # (`clip_name`, nom de fichier, boundary…), pour ne pas rejeter un clip légitime
    # tout juste sous la limite.
    _max_request_bytes = app_settings.max_upload_bytes + 64 * 1024

    @app.middleware("http")
    async def _limit_request_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > _max_request_bytes:
                return ApiError(
                    413,
                    "payload_too_large",
                    f"Corps de requête trop volumineux (> {app_settings.max_upload_mb} Mo).",
                ).to_response()
        return await call_next(request)

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(ingest.router, prefix="/api/v1")
    app.include_router(nodes.router, prefix="/api/v1")
    app.include_router(sites.router, prefix="/api/v1")
    app.include_router(recordings.router, prefix="/api/v1")
    app.include_router(species.router, prefix="/api/v1")
    app.include_router(species_rules.router, prefix="/api/v1")
    app.include_router(reviews.router, prefix="/api/v1")
    app.include_router(dynamic_thresholds.router, prefix="/api/v1")
    app.include_router(commands.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(detections.router, prefix="/api/v1")

    return app


async def _pending_expiry_loop(app: FastAPI) -> None:
    """Réévalue toutes les 5 s la liste « en écoute » de chaque site, même sans nouvel
    instantané reçu — c'est ce qui fait disparaître un élément expiré (contrat §4.5)
    quand plus rien n'arrive du bridge.
    """
    bus: PendingBus = app.state.pending_bus
    session_local = app.state.session_local
    while True:
        await asyncio.sleep(PENDING_EXPIRY_TICK_S)
        db = session_local()
        try:
            db.rollback()
            now = datetime.now(UTC)
            for site in db.query(Site).all():
                pending_list = compute_site_pending(db, site.id, bus, app.state.species_data, now=now)
                bus.publish_if_changed(site.id, pending_list, utc_now_str())
        except Exception:  # ne doit jamais tuer la boucle de fond, mais jamais en silence
            logger.exception("boucle d'expiration « en écoute » : erreur inattendue")
        finally:
            db.close()


try:
    app = create_app()
except ConfigError as exc:
    # Message lisible (sans trace) pour `uvicorn app.main:app` : le serveur refuse de démarrer.
    raise SystemExit(f"bird-frame refuse de démarrer : {exc}") from exc
