"""Session navigateur : `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` — contrat §2.2.

Logique (jeton signé, anti-force brute, contrôle d'origine) : `app/browser_auth.py`.
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Request, Response

from app.browser_auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_S,
    client_ip,
    get_browser_auth,
    require_same_origin,
)
from app.errors import ApiError
from app.schemas.auth import AuthStatus, LoginBody

logger = logging.getLogger("bird_frame.auth")

router = APIRouter(tags=["auth"])

_NO_STORE = {"Cache-Control": "no-store"}


def _cookie_attributes(request: Request) -> dict:
    # `Secure` seulement en https : derrière le proxy Railway, uvicorn (`--proxy-headers`)
    # reflète `X-Forwarded-Proto` dans `request.url.scheme` ; en local (http), un cookie
    # `Secure` ne serait jamais renvoyé par le navigateur.
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": request.url.scheme == "https",
    }


@router.post("/auth/login", response_model=AuthStatus, dependencies=[Depends(require_same_origin)])
def login(body: LoginBody, request: Request, response: Response) -> dict:
    auth = get_browser_auth(request)
    if not auth.enabled:
        raise ApiError(
            409,
            "auth_disabled",
            "L'authentification est désactivée sur ce serveur (mode dev sans mot de passe).",
        )

    ip = client_ip(request)
    retry_after = auth.limiter.try_acquire(ip)
    if retry_after is not None:
        seconds = max(1, math.ceil(retry_after))
        raise ApiError(
            429,
            "too_many_attempts",
            f"Trop de tentatives de connexion. Nouvel essai possible dans {math.ceil(seconds / 60)} min.",
            details={"retry_after_s": seconds},
            headers={"Retry-After": str(seconds), **_NO_STORE},
        )

    ok = False
    try:
        ok = auth.check_password(body.password)
    finally:
        auth.limiter.release(ip, success=ok)

    if not ok:
        logger.warning("Connexion refusée (mot de passe incorrect) depuis %s.", ip)
        raise ApiError(401, "invalid_password", "Mot de passe incorrect.", headers=_NO_STORE)

    response.set_cookie(
        SESSION_COOKIE_NAME,
        auth.issue_token(),
        max_age=SESSION_MAX_AGE_S,
        **_cookie_attributes(request),
    )
    response.headers.update(_NO_STORE)
    logger.info("Connexion réussie depuis %s.", ip)
    return {"authenticated": True, "auth_enabled": True}


@router.post("/auth/logout", response_model=AuthStatus, dependencies=[Depends(require_same_origin)])
def logout(request: Request, response: Response) -> dict:
    # Idempotent, sans session requise : efface le cookie côté navigateur. Le jeton étant
    # sans état serveur, une copie volée resterait valable jusqu'à son expiration — seul
    # un changement de BIRDFRAME_SESSION_SECRET (ou du mot de passe) révoque tout.
    response.delete_cookie(SESSION_COOKIE_NAME, **_cookie_attributes(request))
    response.headers.update(_NO_STORE)
    return {"authenticated": False, "auth_enabled": get_browser_auth(request).enabled}


@router.get("/auth/me", response_model=AuthStatus)
def me(request: Request, response: Response) -> dict:
    auth = get_browser_auth(request)
    response.headers.update(_NO_STORE)
    return {"authenticated": auth.is_authenticated(request), "auth_enabled": auth.enabled}
