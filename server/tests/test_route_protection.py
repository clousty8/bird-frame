"""Garde-fou permanent (contrat §2.2) : énumère TOUTES les routes de l'application.

Échoue si :
- une route navigateur non-GET ne dépend pas de `require_browser_session` (seules
  `/auth/login` et `/auth/logout` en sont dispensées, avec le contrôle d'origine seul) ;
- une route qui sert (ou pilote) de l'audio — enregistrements, futur live WP-19 — ne
  dépend pas de `require_browser_session` ;
- une nouvelle route GET navigateur publique apparaît sans avoir été ajoutée
  consciemment à `PUBLIC_GET_ROUTES` (vérifier d'abord qu'elle ne sert pas d'audio) ;
- une route WebSocket, ou un montage statique qui exposerait `data/` (les clips), apparaît.

Puis vérifie à l'exécution que chaque route protégée répond bien 401 sans session, et
que chaque route publique ne répond jamais 401.

Ajouter une route mutante ou audio : `dependencies=[Depends(require_browser_session)]`
(`app/browser_auth.py`). Ne jamais affaiblir ce test pour le faire passer.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles

from app.auth import get_authenticated_node, require_admin_token
from app.browser_auth import require_browser_session, require_same_origin
from app.config import Settings
from app.main import create_app
from app.passwords import hash_password

try:
    from fastapi.routing import iter_route_contexts
except ImportError:  # FastAPI < 0.141 : `app.routes` contient déjà les APIRoute aplaties.
    iter_route_contexts = None

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Ouverture/fermeture de session : mutations sans session requise (contrôle d'origine seul).
SESSION_ENDPOINTS = {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout")}

# Toute route dont le chemin évoque de l'audio : enregistrements, direct (WP-19 :
# /sites/{slug}/live/…, HLS), fichiers audio. Le spectrogramme (PNG) n'en fait pas partie.
AUDIO_PATH = re.compile(
    r"audio|/live(/|$)|hls|\.(wav|mp3|flac|ogg|opus|m4a|aac|m3u8)(\b|$)", re.IGNORECASE
)

# Liste EXHAUSTIVE des GET navigateur publics sous /api. Une nouvelle route GET fait
# échouer ce test tant qu'elle n'y est pas ajoutée : vérifier d'abord qu'elle ne sert pas
# d'audio (sinon la protéger par `require_browser_session`).
PUBLIC_GET_ROUTES = {
    "/api/v1/auth/me",
    "/api/v1/sites",
    "/api/v1/nodes",
    "/api/v1/sites/{slug}/now",
    "/api/v1/sites/{slug}/pending/stream",
    "/api/v1/sites/{slug}/calendar",
    "/api/v1/sites/{slug}/species",
    "/api/v1/species",
    "/api/v1/species/{scientific_name}",
    "/api/v1/species/{scientific_name}/photo",
    "/api/v1/species/{scientific_name}/sites/{slug}/top-clips",
    "/api/v1/species/{scientific_name}/presence",
    "/api/v1/recordings/{kept_clip_id}/spectrogram",
    "/api/v1/sites/{slug}/stats/kpis",
    "/api/v1/sites/{slug}/stats/daily",
    "/api/v1/sites/{slug}/stats/hourly",
    "/api/v1/sites/{slug}/stats/species",
    "/api/v1/sites/{slug}/stats/heatmap",
    "/api/v1/sites/{slug}/stats/confidence",
    "/api/v1/sites/{slug}/species-rules",
    "/api/v1/sites/{slug}/dynamic-thresholds",
    "/api/v1/sites/{slug}/reviews",
    "/api/v1/sites/{slug}/false-negatives",
    "/api/v1/sites/{slug}/commands",
    "/api/v1/sites/{slug}/detections",
}

# Plancher : ces routes DOIVENT figurer parmi les routes protégées trouvées (garantit que
# l'énumération n'est pas vide par erreur). Une route protégée de plus est bienvenue.
KNOWN_PROTECTED = {
    ("PUT", "/api/v1/sites/{slug}/species-rules/{scientific_name}"),
    ("DELETE", "/api/v1/sites/{slug}/species-rules/{scientific_name}"),
    ("POST", "/api/v1/sites/{slug}/reviews"),
    ("POST", "/api/v1/sites/{slug}/false-negatives"),
    ("DELETE", "/api/v1/sites/{slug}/dynamic-thresholds/{scientific_name}"),
    ("GET", "/api/v1/recordings/{kept_clip_id}/audio"),
}


# ---- Énumération ------------------------------------------------------------------------


@dataclass
class Endpoint:
    path: str  # chemin effectif, préfixes de routeurs inclus
    methods: set[str]
    route: BaseRoute  # route d'origine (APIRoute, Route Starlette, Mount, WebSocket…)
    calls: set = field(default_factory=set)  # toutes les dépendances, récursivement


def _dependency_calls(dependant) -> set:
    calls: set = set()
    stack = list(dependant.dependencies) if dependant is not None else []
    while stack:
        dep = stack.pop()
        calls.add(dep.call)
        stack.extend(dep.dependencies)
    return calls


def iter_endpoints(routes: list[BaseRoute], prefix: str = "") -> Iterator[Endpoint]:
    """Routes effectives de l'application. FastAPI ≥ 0.141 inclut les routeurs
    paresseusement (`app.routes` contient des `_IncludedRouter`) : `iter_route_contexts`
    donne pour chacune le chemin préfixé et l'arbre de dépendances complet (celles du
    routeur incluses)."""
    contexts = iter_route_contexts(routes) if iter_route_contexts is not None else routes
    for ctx in contexts:
        route = getattr(ctx, "original_route", ctx)
        if isinstance(route, Mount) and getattr(route.app, "routes", None) is not None:
            yield from iter_endpoints(route.app.routes, prefix + route.path)
            continue
        is_api = isinstance(route, (APIRoute, APIWebSocketRoute))
        yield Endpoint(
            path=prefix + (getattr(ctx, "path", None) or ""),
            methods=set(getattr(ctx, "methods", None) or set()),
            route=route,
            calls=_dependency_calls(ctx.dependant) if is_api else set(),
        )


@pytest.fixture
def app(app_settings: Settings):
    settings = app_settings.model_copy(
        update={
            "ui_password_hash": hash_password("mot-de-passe-de-test", n=2**10),
            "session_secret": "secret-de-session-de-test-au-moins-32-caracteres",
        }
    )
    return create_app(settings)


def analyse(app, data_dir: Path) -> tuple[set[tuple[str, str]], set[str], list[str]]:
    """(routes protégées par session, GET navigateur publics sous /api, violations).

    `data_dir` : dossier des clips/photos, qu'aucun montage statique ne doit exposer.
    """
    protected: set[tuple[str, str]] = set()
    public_gets: set[str] = set()
    violations: list[str] = []
    data_dir = data_dir.resolve()

    for endpoint in iter_endpoints(app.routes):
        path, route, calls = endpoint.path, endpoint.route, endpoint.calls
        if isinstance(route, (WebSocketRoute, APIWebSocketRoute)):
            violations.append(
                f"WebSocket {path} : aucune route WebSocket n'est prévue ; la protéger par "
                "session (voix privées) et adapter ce test avant de l'ajouter."
            )
            continue

        if isinstance(route, Mount):
            if path.startswith("/api"):
                violations.append(f"montage {path} sous /api : routes non énumérables, interdit.")
            elif isinstance(route.app, StaticFiles) and route.app.directory is not None:
                directory = Path(route.app.directory).resolve()
                if directory == data_dir or data_dir in directory.parents:
                    violations.append(
                        f"montage statique {path} → {directory} : expose data/ (clips audio) "
                        "sans session."
                    )
            continue

        methods = endpoint.methods
        unsafe = methods - SAFE_METHODS
        is_audio = bool(AUDIO_PATH.search(path))

        if not isinstance(route, APIRoute):
            # Route Starlette brute (ex. /docs, /openapi.json) : aucune dépendance possible.
            if unsafe or is_audio:
                violations.append(
                    f"{sorted(methods)} {path} : route non-FastAPI mutante ou audio, "
                    "impossible à protéger par dépendance."
                )
            continue

        has_session = require_browser_session in calls

        if get_authenticated_node in calls:  # ingestion : Bearer du nœud (§2.1)
            if not path.startswith("/api/v1/nodes/{node_id}/"):
                violations.append(f"{path} : route d'ingestion (Bearer) hors /nodes/{{node_id}}/.")
            continue
        if require_admin_token in calls:  # admin : X-Admin-Token (§3)
            continue

        for method in sorted(unsafe):
            if (method, path) in SESSION_ENDPOINTS:
                if require_same_origin not in calls:
                    violations.append(f"{method} {path} : contrôle d'origine manquant.")
            elif not has_session:
                violations.append(
                    f"{method} {path} : route navigateur mutante sans "
                    "Depends(require_browser_session)."
                )
            elif require_same_origin not in calls:
                violations.append(f"{method} {path} : contrôle d'origine manquant.")
            else:
                protected.add((method, path))

        if is_audio and not has_session:
            violations.append(f"{path} : sert de l'audio sans Depends(require_browser_session).")

        if "GET" in methods:
            if has_session:
                protected.add(("GET", path))
            elif path.startswith("/api"):
                public_gets.add(path)
                if path not in PUBLIC_GET_ROUTES:
                    violations.append(
                        f"GET {path} : nouvelle route publique. Vérifier qu'elle ne sert pas "
                        "d'audio, puis l'ajouter à PUBLIC_GET_ROUTES (ou la protéger)."
                    )

    return protected, public_gets, violations



# ---- Tests ------------------------------------------------------------------------------


def test_every_mutating_or_audio_browser_route_requires_a_session(app, app_settings):
    protected, public_gets, violations = analyse(app, app_settings.data_dir_resolved)

    assert not violations, "Routes mal protégées :\n- " + "\n- ".join(violations)
    assert KNOWN_PROTECTED <= protected, KNOWN_PROTECTED - protected
    stale = PUBLIC_GET_ROUTES - public_gets
    assert not stale, f"PUBLIC_GET_ROUTES contient des routes disparues ou protégées : {stale}"


def _fill(path: str) -> str:
    def value(match: re.Match) -> str:
        return "1" if match.group(1).endswith("_id") else "inconnu"

    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", value, path)


def test_protected_routes_answer_401_without_session_and_public_ones_never(app, app_settings):
    protected, public_gets, _ = analyse(app, app_settings.data_dir_resolved)

    with TestClient(app) as client:
        for method, path in sorted(protected):
            resp = client.request(method, _fill(path))
            assert resp.status_code == 401, (method, path, resp.status_code, resp.text[:200])
            assert resp.json()["error"] == "auth_required"

        for path in sorted(public_gets):
            resp = client.get(_fill(path))
            assert resp.status_code != 401, (path, resp.text[:200])
            assert resp.status_code != 403, (path, resp.text[:200])


def test_guard_detects_an_unprotected_mutation_and_audio_route(app, app_settings):
    """Le garde-fou lui-même : une route oubliée DOIT être signalée."""

    @app.post("/api/v1/sites/{slug}/oubli")
    def forgotten_mutation(slug: str) -> dict:
        return {}

    @app.get("/api/v1/sites/{slug}/live/hls/{segment}")
    def forgotten_live_audio(slug: str, segment: str) -> dict:
        return {}

    @app.get("/api/v1/sites/{slug}/nouvelle-lecture")
    def new_public_get(slug: str) -> dict:
        return {}

    app.mount("/clips", StaticFiles(directory=app_settings.data_dir_resolved, check_dir=False))

    _, _, violations = analyse(app, app_settings.data_dir_resolved)
    joined = "\n".join(violations)
    assert "POST /api/v1/sites/{slug}/oubli" in joined
    assert "/api/v1/sites/{slug}/live/hls/{segment} : sert de l'audio" in joined
    assert "GET /api/v1/sites/{slug}/nouvelle-lecture : nouvelle route publique" in joined
    assert "montage statique /clips" in joined
