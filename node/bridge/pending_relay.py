"""Relais « en écoute » quasi temps réel (WP-06, api-contract.md §4.5).

Abonnement SSE **local** à `GET {BRIDGE_NODE_API}/api/v2/detections/stream`, filtre l'évènement
`event: pending` (instantané complet, pas un évènement unitaire — §10.1 point 1) et relaie,
immédiatement, l'instantané entier vers `POST /nodes/{id}/pending` (fire-and-forget, retry
best-effort, jamais bloquant pour le flux SSE). Renvoie aussi le dernier instantané connu toutes
les 30 s, même sans changement, et un instantané vide si l'abonnement SSE tombe.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from bridge.backoff import Backoff
from bridge.config import BridgeConfig
from bridge.sse import iter_sse_events

logger = logging.getLogger(__name__)

_RESEND_INTERVAL_S = 30.0
_EMPTY_ITEMS: list[dict] = []


def _confidence_hint(raw_item: dict) -> float | None:
    contributions = raw_item.get("modelContributions") or []
    values = [c.get("maxConfidence") for c in contributions if isinstance(c.get("maxConfidence"), int | float)]
    return max(values) if values else None


def build_pending_items(raw_items: list[dict]) -> list[dict]:
    """Traduit le tableau brut `SSEPendingDetection` de BirdNET-Go vers la forme du contrat
    (§4.5). `thumbnail` n'est délibérément pas relayé."""
    return [
        {
            "scientific_name": item["scientificName"],
            "common_name": item.get("species"),
            "status": item["status"],
            "hit_count": item.get("hitCount", 0),
            "confidence_hint": _confidence_hint(item),
            "first_detected_unix": item["firstDetected"],
            "last_updated_unix": item["lastUpdated"],
            "source_id": item.get("sourceID"),
        }
        for item in raw_items
    ]


class _SharedPendingState:
    def __init__(self) -> None:
        self.items: list[dict] = list(_EMPTY_ITEMS)

    def snapshot_payload(self) -> dict:
        return {"snapshot_at_unix": int(time.time()), "items": self.items}


async def _post_pending(server_client: httpx.AsyncClient, config: BridgeConfig, payload: dict) -> None:
    """Fire-and-forget : un seul essai, log en WARNING sur échec, ne bloque jamais le flux SSE."""
    try:
        response = await server_client.post(f"/nodes/{config.node_id}/pending", json=payload, timeout=10)
        if response.status_code >= 400:
            logger.warning("POST /pending a échoué (%s) : %s", response.status_code, response.text[:300])
    except httpx.HTTPError as exc:
        logger.warning("POST /pending : erreur réseau (%s), best-effort — abandon pour ce cycle", exc)


async def _consume_sse(
    node_client: httpx.AsyncClient,
    config: BridgeConfig,
    server_client: httpx.AsyncClient,
    state: _SharedPendingState,
    stop_event: asyncio.Event,
) -> None:
    url = f"{config.node_api}/api/v2/detections/stream"
    backoff = Backoff()
    while not stop_event.is_set():
        received_event = False
        try:
            async with node_client.stream("GET", url, timeout=httpx.Timeout(None, connect=10)) as response:
                response.raise_for_status()
                # Reconnexion réussie : remettre le backoff à zéro dès maintenant, pas seulement à
                # la réception d'un évènement 'pending' — une connexion saine mais silencieuse
                # (nuit calme) ne doit jamais laisser le compteur de tentatives précédent inflater
                # le délai de la prochaine reconnexion.
                backoff.reset()
                logger.info("Flux SSE local connecté (%s)", url)
                async for event_name, data in iter_sse_events(response.aiter_lines()):
                    if stop_event.is_set():
                        return
                    if event_name != "pending":
                        continue
                    received_event = True
                    backoff.reset()
                    try:
                        raw_items = json.loads(data)
                    except json.JSONDecodeError as exc:
                        logger.warning("Évènement 'pending' illisible (%s), ignoré", exc)
                        continue
                    try:
                        new_items = build_pending_items(raw_items)
                    except (KeyError, TypeError) as exc:
                        # Un item incomplet ou mal formé ne doit jamais tuer ce flux : sans ce
                        # filet, l'exception sortait de la boucle `async for`, `_consume_sse`
                        # mourait silencieusement, et `_resend_periodically` continuait de reposter
                        # indéfiniment le dernier instantané connu (figé) toutes les 30 s.
                        logger.warning(
                            "Évènement 'pending' mal formé (%s), ignoré : %s", exc, str(raw_items)[:300]
                        )
                        continue
                    state.items = new_items
                    await _post_pending(server_client, config, state.snapshot_payload())
            if not received_event:
                # Le nœud ne doit normalement jamais fermer ce flux de lui-même. Traiter ce cas
                # comme n'importe quelle coupure (délai avant reconnexion) plutôt que de reboucler
                # immédiatement : sans ce délai, une fermeture propre et répétée du flux (proxy,
                # redémarrage du nœud) produirait une boucle chaude qui sature la CPU et le réseau.
                logger.warning("Flux SSE local terminé sans évènement 'pending' (%s), reconnexion avec délai", url)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Flux SSE local interrompu (%s) : instantané vide envoyé, reconnexion", exc)
            state.items = list(_EMPTY_ITEMS)
            await _post_pending(server_client, config, state.snapshot_payload())

        if stop_event.is_set():
            return
        delay = backoff.next_delay()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass


async def _resend_periodically(
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    state: _SharedPendingState,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_RESEND_INTERVAL_S)
            return
        except TimeoutError:
            await _post_pending(server_client, config, state.snapshot_payload())


async def run_pending_relay(
    node_client: httpx.AsyncClient,
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    stop_event: asyncio.Event,
) -> None:
    """`_consume_sse` peut rester bloqué indéfiniment dans une lecture réseau (flux SSE local
    inactif, pas d'évènement `pending` pendant longtemps) : `stop_event.set()` seul ne
    l'interromprait jamais. On annule donc explicitement les deux sous-tâches à l'arrêt plutôt
    que de compter sur leur boucle `while not stop_event.is_set()` pour sortir d'elle-même."""
    state = _SharedPendingState()
    consume_task = asyncio.ensure_future(_consume_sse(node_client, config, server_client, state, stop_event))
    resend_task = asyncio.ensure_future(_resend_periodically(server_client, config, state, stop_event))
    try:
        await stop_event.wait()
    finally:
        consume_task.cancel()
        resend_task.cancel()
        for task, name in ((consume_task, "consume_sse"), (resend_task, "resend_periodically")):
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Tâche '%s' du relais 'en écoute' s'est terminée en erreur inattendue", name)
