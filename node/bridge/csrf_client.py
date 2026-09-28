"""Client CSRF unique contre l'API locale de BirdNET-Go (api-contract.md §5.1).

Cycle vérifié :
1. `GET {BRIDGE_NODE_API}/api/v2/app/config` pose un cookie `csrf` et renvoie un champ JSON
   `csrfToken`.
2. Toute requête mutante (POST/PUT/PATCH/DELETE) envoie l'en-tête `X-CSRF-Token` **et** le cookie
   `csrf` (même client HTTP, cookies conservés).
3. Sur 403, rafraîchir le jeton et rejouer une fois.
4. Si `BRIDGE_NODE_API_TOKEN` est non vide (S2+), ajouter `Authorization: Bearer <token>` à
   **toutes** les requêtes.

Point de désaccord explicite entre `architecture.md`/`api-contract.md` (qui citent le champ JSON
`csrfToken`) et une vérification `curl` réelle demandée en amont de ce lot : sur le nœud local,
la valeur du cookie `csrf` posé par `GET /` (et par `GET /api/v2/app/config`) diffère de la valeur
du champ JSON `csrfToken` du corps — et c'est la valeur du **cookie** que la mutation testée en
`curl` (`POST /api/v2/range/species/test`) a acceptée dans `X-CSRF-Token`. Ce client utilise donc
la valeur du cookie comme jeton, pas le champ JSON (double-submit cookie, cohérent avec le
middleware CSRF d'Echo). Voir node/README.md.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_COOKIE_NAME = "csrf"


class CsrfError(Exception):
    """Impossible d'obtenir un jeton CSRF valide auprès du nœud."""


class CsrfClient:
    """Bibliothèque unique de mutation CSRF contre l'API locale BirdNET-Go — jamais recontournée
    ad hoc par endpoint (architecture.md §7.2/§9)."""

    def __init__(self, node_client: httpx.AsyncClient, node_api: str, bearer_token: str = "") -> None:
        self._client = node_client
        self._node_api = node_api.rstrip("/")
        self._bearer_token = bearer_token or None
        self._token: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        if self._bearer_token:
            return {"Authorization": f"Bearer {self._bearer_token}"}
        return {}

    async def _refresh_token(self) -> str:
        url = f"{self._node_api}/api/v2/app/config"
        response = await self._client.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        cookie_value = self._client.cookies.get(_COOKIE_NAME)
        if not cookie_value:
            raise CsrfError(f"Aucun cookie '{_COOKIE_NAME}' reçu de {url}")
        self._token = cookie_value
        return cookie_value

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        params: dict[str, object] | None = None,
        timeout: float = 15.0,
    ) -> httpx.Response:
        """Exécute une requête contre l'API locale BirdNET-Go (`path` relatif, ex. `/api/v2/settings/species`)."""
        method = method.upper()
        mutating = method in _MUTATING_METHODS
        if mutating and self._token is None:
            await self._refresh_token()

        url = f"{self._node_api}{path}"
        headers = self._auth_headers()
        if mutating:
            headers["X-CSRF-Token"] = self._token or ""

        response = await self._client.request(
            method, url, json=json_body, params=params, headers=headers, timeout=timeout
        )

        if mutating and response.status_code == 403:
            logger.info("403 sur %s %s : rafraîchissement du jeton CSRF et un seul réessai", method, path)
            await self._refresh_token()
            headers["X-CSRF-Token"] = self._token or ""
            response = await self._client.request(
                method, url, json=json_body, params=params, headers=headers, timeout=timeout
            )
        return response
