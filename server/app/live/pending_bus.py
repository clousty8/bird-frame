"""Bus en mémoire, par site, pour le bloc « en écoute » et le SSE navigateur.

Architecture.md §3.3, contrat §4.5 et §6.4. Accédé à la fois depuis les routes
d'ingestion (synchrones, exécutées dans le threadpool de Starlette) et depuis les
abonnés SSE (coroutines sur la boucle asyncio) : toute mutation partagée est protégée
par un verrou `threading.Lock`, et la remise aux abonnés traverse la frontière
thread → event loop via `loop.call_soon_threadsafe`.

État perdu au redémarrage du serveur (contrat §9.8) — reconstruit au prochain
instantané envoyé par chaque bridge (≤ 30 s).
"""

from __future__ import annotations

import asyncio
import threading


class PendingBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # node_id -> {"items": [PendingItem...], "received_at_unix": int}
        self._node_snapshots: dict[int, dict] = {}
        # site_id -> dernière liste PendingItem diffusée (pour ne diffuser que les changements)
        self._last_broadcast: dict[int, list[dict]] = {}
        # site_id -> ensemble des files d'attente des abonnés SSE actifs
        self._subscribers: dict[int, set[asyncio.Queue]] = {}

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Appelé une fois au démarrage (coroutine), pour pouvoir réveiller les abonnés
        SSE depuis des routes synchrones exécutées dans un autre thread."""
        self._loop = loop

    # ---- Écriture (routes d'ingestion, synchrones) -------------------------------

    def update_node_snapshot(self, node_id: int, received_at_unix: int, items: list[dict]) -> None:
        with self._lock:
            self._node_snapshots[node_id] = {"items": items, "received_at_unix": received_at_unix}

    def clear_node_snapshot(self, node_id: int) -> None:
        with self._lock:
            self._node_snapshots.pop(node_id, None)

    def node_snapshot(self, node_id: int) -> dict | None:
        with self._lock:
            snap = self._node_snapshots.get(node_id)
            return dict(snap) if snap else None

    def known_node_ids(self) -> list[int]:
        with self._lock:
            return list(self._node_snapshots.keys())

    # ---- Abonnement SSE (coroutines) ----------------------------------------------

    def subscribe(self, site_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        with self._lock:
            self._subscribers.setdefault(site_id, set()).add(q)
        return q

    def unsubscribe(self, site_id: int, q: asyncio.Queue) -> None:
        with self._lock:
            subs = self._subscribers.get(site_id)
            if subs is not None:
                subs.discard(q)

    def last_broadcast(self, site_id: int) -> list[dict] | None:
        with self._lock:
            prev = self._last_broadcast.get(site_id)
            return list(prev) if prev is not None else None

    # ---- Diffusion ------------------------------------------------------------------

    def publish_if_changed(self, site_id: int, pending_items: list[dict], updated_at_utc: str) -> bool:
        """Diffuse `event: pending` à ce site si la liste diffère de la dernière diffusée.

        `data` ne porte pas `site_slug` (le bus ne connaît que des `site_id`) : c'est
        l'endpoint SSE, qui connaît le slug demandé dans l'URL, qui le complète (§6.4).
        """
        with self._lock:
            if self._last_broadcast.get(site_id) == pending_items:
                return False
            self._last_broadcast[site_id] = pending_items
            subs = list(self._subscribers.get(site_id, ()))
        self._dispatch(
            subs,
            {"event": "pending", "data": {"updated_at_utc": updated_at_utc, "pending": pending_items}},
        )
        return True

    def publish_detection(self, site_id: int, detection: dict) -> None:
        with self._lock:
            subs = list(self._subscribers.get(site_id, ()))
        self._dispatch(subs, {"event": "detection", "data": detection})

    def publish_heartbeat(self, site_id: int, server_time_utc: str, node_online: bool) -> None:
        with self._lock:
            subs = list(self._subscribers.get(site_id, ()))
        self._dispatch(
            subs,
            {"event": "heartbeat", "data": {"server_time_utc": server_time_utc, "node_online": node_online}},
        )

    def _dispatch(self, subs: list[asyncio.Queue], message: dict) -> None:
        if not subs or self._loop is None:
            return
        for q in subs:
            self._loop.call_soon_threadsafe(_put_nowait_drop_oldest, q, message)


def _put_nowait_drop_oldest(q: asyncio.Queue, message: dict) -> None:
    try:
        q.put_nowait(message)
    except asyncio.QueueFull:
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            pass
