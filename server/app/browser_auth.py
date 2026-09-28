"""Session navigateur à mot de passe unique — contrat §2.2.

Lecture libre pour tout le monde ; **une session est requise pour modifier** (toute route
navigateur non-GET) **et pour écouter les sons** (les enregistrements peuvent contenir des
voix privées). Un seul mot de passe (celui d'Armand), pas de comptes.

- Cookie `bf_session` = jeton signé HMAC-SHA256 (stdlib) avec expiration intégrée
  (30 jours) : rien n'est stocké côté serveur. La clé de signature dérive de
  `BIRDFRAME_SESSION_SECRET` **et** du hash du mot de passe : changer l'un ou l'autre
  invalide toutes les sessions existantes.
- Protection des routes : deux dépendances FastAPI réutilisables, `require_same_origin`
  (CSRF : en-tête `Origin` étranger → 403) et `require_browser_session` (les deux
  contrôles, puis 401 `auth_required` sans session valide). `tests/test_route_protection.py`
  énumère toutes les routes de l'application et échoue si une route navigateur mutante,
  ou une route qui sert de l'audio, n'en dépend pas.
- Anti-force brute : 5 échecs en 5 min pour une IP → 429 pendant 5 min
  (`LoginRateLimiter`, en mémoire du process : un seul process uvicorn, contrat S1).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from fastapi import Depends, Request

from app.config import Settings
from app.errors import ApiError
from app.passwords import ParsedHash, PasswordHashError, parse_password_hash, verify_password

logger = logging.getLogger("bird_frame.auth")

SESSION_COOKIE_NAME = "bf_session"
SESSION_MAX_AGE_S = 30 * 24 * 3600
MIN_SESSION_SECRET_LENGTH = 32

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_S = 5 * 60
LOGIN_BLOCK_S = 5 * 60

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_TOKEN_VERSION = "v1"
_KEY_CONTEXT = b"bird-frame/session/v1\x00"


class ConfigError(RuntimeError):
    """Configuration d'authentification invalide : le serveur refuse de démarrer."""


# ---- Jeton de session ---------------------------------------------------------------


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def derive_signing_key(session_secret: str, password_hash: str) -> bytes:
    return hmac.new(
        session_secret.encode("utf-8"),
        _KEY_CONTEXT + password_hash.strip().encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _signature(key: bytes, payload: str) -> str:
    return _b64(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())


def sign_session_token(key: bytes, now: float, max_age_s: int = SESSION_MAX_AGE_S) -> str:
    """`v1.<expiration_unix>.<nonce>.<signature>` — tous caractères sûrs pour un cookie."""
    payload = f"{_TOKEN_VERSION}.{int(now) + max_age_s}.{secrets.token_urlsafe(12)}"
    return f"{payload}.{_signature(key, payload)}"


def verify_session_token(key: bytes, token: str, now: float) -> bool:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _TOKEN_VERSION or not parts[1].isdigit():
        return False
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(_signature(key, payload), parts[3]):
        return False
    return now < int(parts[1])


# ---- Anti-force brute ---------------------------------------------------------------


@dataclass
class _IpAttempts:
    failures: list[float] = field(default_factory=list)
    in_flight: int = 0
    blocked_until: float = 0.0


class LoginRateLimiter:
    """5 échecs en 5 min pour une IP → 429 pendant 5 min.

    Les tentatives en cours de vérification comptent déjà : une rafale de requêtes
    parallèles ne peut pas faire vérifier plus de `max_failures` mots de passe avant que
    le blocage ne tombe. Une connexion réussie remet le compteur de l'IP à zéro.
    """

    def __init__(
        self,
        max_failures: int = LOGIN_MAX_FAILURES,
        window_s: float = LOGIN_WINDOW_S,
        block_s: float = LOGIN_BLOCK_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self.block_s = block_s
        self.clock = clock
        self._lock = threading.Lock()
        self._by_ip: dict[str, _IpAttempts] = {}

    def try_acquire(self, ip: str) -> float | None:
        """`None` si la tentative peut être vérifiée (à clore par `release`), sinon le
        nombre de secondes avant la prochaine tentative autorisée."""
        with self._lock:
            now = self.clock()
            self._prune(now)
            state = self._by_ip.setdefault(ip, _IpAttempts())
            if state.blocked_until > now:
                return state.blocked_until - now
            if len(state.failures) + state.in_flight >= self.max_failures:
                # Uniquement des tentatives encore en vol : l'IP sera bloquée dès que
                # l'une d'elles aura échoué ; d'ici là, pas de vérification de plus.
                return self.block_s
            state.in_flight += 1
            return None

    def release(self, ip: str, success: bool) -> None:
        with self._lock:
            now = self.clock()
            state = self._by_ip.setdefault(ip, _IpAttempts())
            state.in_flight = max(0, state.in_flight - 1)
            if success:
                state.failures.clear()
                return
            state.failures = [t for t in state.failures if t > now - self.window_s]
            state.failures.append(now)
            if len(state.failures) >= self.max_failures:
                state.blocked_until = now + self.block_s
                state.failures.clear()
                logger.warning(
                    "Connexion : %d échecs en %d min depuis %s, IP bloquée %d min.",
                    self.max_failures,
                    int(self.window_s // 60),
                    ip,
                    int(self.block_s // 60),
                )

    def _prune(self, now: float) -> None:
        """Oublie les IP sans échec récent ni blocage ni tentative en cours (mémoire bornée)."""
        stale = [
            ip
            for ip, state in self._by_ip.items()
            if state.in_flight == 0
            and state.blocked_until <= now
            and all(t <= now - self.window_s for t in state.failures)
        ]
        for ip in stale:
            del self._by_ip[ip]


# ---- État d'authentification de l'application -------------------------------------


@dataclass
class BrowserAuth:
    """Construit une fois par application (`create_app`), rangé dans `app.state.browser_auth`.

    `enabled=False` seulement en `dev` sans hash : tout est alors autorisé.
    """

    enabled: bool
    password: ParsedHash | None = None
    signing_key: bytes | None = None
    trusted_origins: frozenset[str] = frozenset()
    limiter: LoginRateLimiter = field(default_factory=LoginRateLimiter)
    clock: Callable[[], float] = time.time

    def check_password(self, password: str) -> bool:
        if self.password is None:
            return False
        return verify_password(password, self.password)

    def issue_token(self) -> str:
        assert self.signing_key is not None
        return sign_session_token(self.signing_key, self.clock())

    def token_is_valid(self, token: str | None) -> bool:
        if not token or self.signing_key is None:
            return False
        return verify_session_token(self.signing_key, token, self.clock())

    def is_authenticated(self, request: Request) -> bool:
        return self.enabled and self.token_is_valid(request.cookies.get(SESSION_COOKIE_NAME))


def build_browser_auth(app_settings: Settings) -> BrowserAuth:
    """Valide la configuration d'authentification (lève `ConfigError`) et construit l'état.

    - `production` : hash **et** secret obligatoires, sinon refus de démarrer.
    - `dev` sans hash : authentification désactivée, WARNING.
    - `dev` avec hash mais sans secret : secret aléatoire propre au process (sessions
      perdues au redémarrage), WARNING.
    - Dans tous les cas : un hash mal formé ou un secret de moins de 32 caractères est
      refusé (une faute de configuration ne doit jamais ouvrir l'accès en silence).
    """
    password_hash = app_settings.ui_password_hash.strip()
    session_secret = app_settings.session_secret.strip()
    trusted_origins = frozenset(
        o for o in (_normalize_origin(x) for x in app_settings.cors_origins_list) if o
    )

    if app_settings.env == "production":
        missing = [
            name
            for name, value in (
                ("BIRDFRAME_UI_PASSWORD_HASH", password_hash),
                ("BIRDFRAME_SESSION_SECRET", session_secret),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "BIRDFRAME_ENV=production exige BIRDFRAME_UI_PASSWORD_HASH et "
                f"BIRDFRAME_SESSION_SECRET ; manquant : {', '.join(missing)}. "
                "Hash : `uv run scripts/hash_password.py` (racine du dépôt). "
                "Secret : `python3 -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
            )

    if not password_hash:
        logger.warning(
            "Authentification navigateur DÉSACTIVÉE (BIRDFRAME_ENV=dev sans "
            "BIRDFRAME_UI_PASSWORD_HASH) : n'importe qui peut modifier les règles/revues et "
            "écouter les enregistrements. Ne jamais exposer ce serveur publiquement ainsi."
        )
        return BrowserAuth(enabled=False, trusted_origins=trusted_origins)

    try:
        parsed = parse_password_hash(password_hash)
    except PasswordHashError as exc:
        raise ConfigError(f"BIRDFRAME_UI_PASSWORD_HASH invalide : {exc}.") from exc

    if session_secret and len(session_secret) < MIN_SESSION_SECRET_LENGTH:
        raise ConfigError(
            f"BIRDFRAME_SESSION_SECRET trop court ({len(session_secret)} caractères, "
            f"minimum {MIN_SESSION_SECRET_LENGTH})."
        )
    if not session_secret:
        logger.warning(
            "BIRDFRAME_SESSION_SECRET absent (mode dev) : secret aléatoire propre à ce "
            "process, les sessions seront perdues au prochain redémarrage."
        )
        session_secret = secrets.token_urlsafe(48)

    return BrowserAuth(
        enabled=True,
        password=parsed,
        signing_key=derive_signing_key(session_secret, password_hash),
        trusted_origins=trusted_origins,
    )


# ---- Dépendances FastAPI ----------------------------------------------------------


def get_browser_auth(request: Request) -> BrowserAuth:
    return request.app.state.browser_auth


def client_ip(request: Request) -> str:
    """IP du client telle que vue par l'application : derrière le proxy Railway, uvicorn
    (`--proxy-headers`) l'a déjà remplacée par celle de `X-Forwarded-For`."""
    return request.client.host if request.client else "inconnue"


def _normalize_origin(origin: str) -> str | None:
    """`scheme://hôte[:port]` en minuscules, port par défaut retiré ; `None` si illisible."""
    try:
        parts = urlsplit(origin.strip().rstrip("/"))
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{_strip_default_port(parts.netloc.lower(), parts.scheme)}"


def _strip_default_port(netloc: str, scheme: str) -> str:
    default_port = ":443" if scheme == "https" else ":80"
    return netloc.removesuffix(default_port)


def _origin_is_allowed(origin: str, request: Request, trusted: frozenset[str]) -> bool:
    normalized = _normalize_origin(origin)
    if normalized is None:  # y compris « null » (iframe sandboxée, redirection opaque)
        return False
    if normalized in trusted:
        return True
    host = request.headers.get("host")
    if not host:
        return False
    scheme, _, origin_netloc = normalized.partition("://")
    return origin_netloc == _strip_default_port(host.strip().lower(), scheme)


def require_same_origin(request: Request) -> None:
    """Anti-CSRF des mutations : un en-tête `Origin` présent DOIT désigner l'hôte de la
    requête (ou une origine de `BIRDFRAME_CORS_ORIGINS`, cas du proxy Vite en dev), sinon
    403 `origin_mismatch`. Sans effet sur GET/HEAD/OPTIONS. Complète `SameSite=Lax`."""
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is None:
        return
    if not _origin_is_allowed(origin, request, get_browser_auth(request).trusted_origins):
        raise ApiError(
            403,
            "origin_mismatch",
            "Requête refusée : elle provient d'un autre site que celui de bird-frame.",
            details={"origin": origin},
        )


def require_browser_session(request: Request, _: None = Depends(require_same_origin)) -> None:
    """Session requise (après le contrôle d'origine) : 401 `auth_required` sinon.

    À poser sur **toute** route navigateur non-GET et sur toute route qui sert de l'audio
    (`dependencies=[Depends(require_browser_session)]`). Sans effet quand
    l'authentification est désactivée (`dev` sans hash).
    """
    auth = get_browser_auth(request)
    if not auth.enabled:
        return
    if not auth.is_authenticated(request):
        raise ApiError(
            401,
            "auth_required",
            "Connexion requise : cette action (ou l'écoute des enregistrements) est réservée "
            "au propriétaire du cadre.",
        )
