"""Cache du dictionnaire FR du nœud (`GET /api/v2/species/dictionary/fr`), utilisé pour résoudre
`common_name` dans les payloads de sync (api-contract.md §4.2, §1.6 niveau 3).

Lecture seule, GET public sur le nœud. Chargé une fois (le dictionnaire est stable pendant la vie
du process) ; un échec au chargement laisse simplement `common_name = null` dans les payloads —
jamais une erreur bloquante pour la synchro des détections.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class SpeciesDictionary:
    def __init__(self, node_client: httpx.AsyncClient, node_api: str) -> None:
        self._client = node_client
        self._node_api = node_api.rstrip("/")
        self._names: dict[str, str] = {}
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    async def ensure_loaded(self) -> None:
        if self._loaded:
            return
        url = f"{self._node_api}/api/v2/species/dictionary/fr"
        try:
            response = await self._client.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Dictionnaire FR du nœud indisponible (%s) : common_name restera null pour ce cycle, "
                "nouvel essai au prochain",
                exc,
            )
            return
        if isinstance(data, dict):
            self._names = {str(k): str(v) for k, v in data.items()}
            self._loaded = True
            logger.info("Dictionnaire FR du nœud chargé (%d entrées)", len(self._names))
        else:
            logger.warning("Réponse inattendue de %s (pas un objet), dictionnaire ignoré", url)

    def get(self, scientific_name: str) -> str | None:
        return self._names.get(scientific_name)
