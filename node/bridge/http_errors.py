"""Classification des réponses HTTP du serveur bird-frame, commune à toutes les routes
d'ingestion (api-contract.md §4.1) :

| Réponse                                   | Action du bridge                                            |
|--------------------------------------------|--------------------------------------------------------------|
| 2xx                                        | succès                                                        |
| erreur réseau, timeout, 5xx                | retry avec backoff exponentiel                                |
| 401, 403, 404 `node_not_found`             | config invalide : log ERROR, pas de backoff, réessai à 300 s  |
| 409                                        | spécifique à chaque route (géré par l'appelant)                |
| 413, 422                                   | bug de payload : log ERROR, élément abandonné, pas de retry    |

Ce module ne fait que qualifier une réponse ; il ne décide ni ne journalise rien lui-même.
"""

from __future__ import annotations

from enum import Enum

import httpx


class RetryDecision(Enum):
    SUCCESS = "success"
    TRANSIENT = "transient"  # backoff exponentiel
    CONFIG_ERROR = "config_error"  # réessai fixe à 300 s, pas de backoff exponentiel
    CONFLICT = "conflict"  # 409, à traiter route par route par l'appelant
    PERMANENT = "permanent"  # payload fautif : log + abandon, pas de retry en boucle


def error_code(response: httpx.Response) -> str | None:
    """Code `error` du corps JSON d'erreur (§1.8), ou `None` si le corps n'est pas exploitable."""
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        value = body.get("error")
        return value if isinstance(value, str) else None
    return None


def classify(response: httpx.Response | None, exc: Exception | None = None) -> RetryDecision:
    if exc is not None or response is None:
        return RetryDecision.TRANSIENT
    status = response.status_code
    if status < 300:
        return RetryDecision.SUCCESS
    if status >= 500:
        return RetryDecision.TRANSIENT
    if status == 409:
        return RetryDecision.CONFLICT
    if status in (401, 403):
        return RetryDecision.CONFIG_ERROR
    if status == 404:
        return RetryDecision.CONFIG_ERROR if error_code(response) == "node_not_found" else RetryDecision.PERMANENT
    if status in (413, 422):
        return RetryDecision.PERMANENT
    return RetryDecision.PERMANENT
