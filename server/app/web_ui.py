"""Service de l'interface web (build Vite) par le serveur lui-même — déploiement Railway.

Activé seulement si `BIRDFRAME_WEB_DIST` pointe vers un build (`web/dist/`, qui DOIT contenir
`index.html`, sinon le serveur refuse de démarrer). En développement la variable reste vide : Vite
sert l'interface et proxifie `/api` (contrat §2.3).

Comportement :
- `GET`/`HEAD` d'un fichier existant du build → ce fichier ; `/assets/*` (noms hachés par Vite)
  avec `Cache-Control: public, max-age=31536000, immutable`, tout le reste avec `no-cache` ;
- toute autre route `GET`/`HEAD` qui n'est ni `/api/…` ni `/health…` → `index.html` (`no-cache`),
  pour que le routeur côté client (`web/src/lib/router.ts`, History API) prenne le relais sur
  un lien direct ou un rechargement (ex. `/species/Erithacus%20rubecula`) ;
- exception volontaire : un `/assets/…` **absent** reste un 404 — renvoyer `index.html` à la
  place d'un module JS (ancien chunk après un déploiement) produirait une erreur de type MIME
  opaque côté navigateur au lieu d'un 404 clair.

Branchement : pas de route « attrape-tout ». Le repli est fait dans le gestionnaire des 404 de
Starlette (« aucune route ne correspond »), installé par `install_web_ui()`. Les routes de l'API
gardent ainsi **strictement** leur comportement : elles sont toujours essayées d'abord, un
`POST` sur une route inconnue reste un 404 JSON (une route `GET /{path:path}` l'aurait
transformé en 405), et `/api/…`/`/health` inconnus gardent le 404 JSON du contrat (§1.8).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bird_frame.web_ui")

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
_RESERVED_PREFIXES = ("api", "health")


class WebUiError(Exception):
    """Build web configuré mais inutilisable (dossier ou index.html absent)."""


class WebUi:
    def __init__(self, dist_dir: Path) -> None:
        dist = dist_dir.resolve()
        index = dist / "index.html"
        if not index.is_file():
            raise WebUiError(
                f"BIRDFRAME_WEB_DIST={dist_dir} : {index} introuvable "
                "(lancer `npm run build` dans web/, ou vider la variable)"
            )
        self.dist = dist
        self.index = index

    @staticmethod
    def _is_reserved(rel_path: str) -> bool:
        first_segment = rel_path.split("/", 1)[0]
        return first_segment in _RESERVED_PREFIXES

    def _existing_file(self, rel_path: str) -> Path | None:
        if not rel_path or "\x00" in rel_path:
            return None
        try:
            candidate = (self.dist / rel_path).resolve()
        except (OSError, ValueError):
            return None
        # Protection contre la traversée (`/../../etc/passwd`, lien symbolique sortant du build).
        if not candidate.is_relative_to(self.dist) or not candidate.is_file():
            return None
        return candidate

    def response_for(self, request: Request) -> Response | None:
        """Réponse à servir pour une requête qu'aucune route n'a prise, ou `None` (→ 404 JSON)."""
        if request.method not in ("GET", "HEAD"):
            return None
        rel_path = request.scope["path"].lstrip("/")
        if self._is_reserved(rel_path):
            return None

        found = self._existing_file(rel_path)
        if found is not None:
            cache = IMMUTABLE_CACHE if rel_path.startswith("assets/") else NO_CACHE
            return FileResponse(found, headers={"Cache-Control": cache})
        if rel_path.startswith("assets/"):
            return None
        return FileResponse(self.index, media_type="text/html", headers={"Cache-Control": NO_CACHE})


def install_web_ui(app: FastAPI, dist_dir: Path) -> WebUi:
    """Branche le service de l'UI sur `app` (à appeler APRÈS `register_error_handlers`)."""
    web_ui = WebUi(dist_dir)
    default_handler = app.exception_handlers[StarletteHTTPException]

    async def spa_or_default(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            response = web_ui.response_for(request)
            if response is not None:
                return response
        return await default_handler(request, exc)

    app.add_exception_handler(StarletteHTTPException, spa_or_default)
    app.state.web_ui = web_ui
    logger.info("Interface web servie depuis %s", web_ui.dist)
    return web_ui
