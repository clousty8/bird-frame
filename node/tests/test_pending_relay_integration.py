"""WP-06 : la boucle complète (SSE local → POST /pending) sur un flux SSE entièrement mocké."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest
import respx

from bridge import pending_relay
from bridge.config import load_config
from bridge.pending_relay import run_pending_relay

NODE_API = "http://localhost:8080"
SERVER_API = "http://localhost:8090/api/v1"

_SSE_BODY = (
    b"event: pending\n"
    b'data: [{"species": "Rougegorge familier", "scientificName": "Erithacus rubecula", '
    b'"status": "active", "firstDetected": 1, "lastUpdated": 2, "sourceID": "src1", "hitCount": 1}]\n'
    b"\n"
)

# Item SANS "status" : BirdNET-Go peut l'envoyer avant qu'un item ne soit "typé", ou un champ peut
# être renommé/supprimé par une future version. Suivi immédiatement d'un item bien formé sur le
# même flux, pour prouver que le relais survit et continue de fonctionner après l'item fautif.
_SSE_BODY_MALFORMED_THEN_VALID = (
    b"event: pending\n"
    b'data: [{"scientificName": "Turdus merula", "firstDetected": 1, "lastUpdated": 2}]\n'
    b"\n"
    b"event: pending\n"
    b'data: [{"species": "Rougegorge familier", "scientificName": "Erithacus rubecula", '
    b'"status": "active", "firstDetected": 1, "lastUpdated": 2, "sourceID": "src1", "hitCount": 1}]\n'
    b"\n"
)


@pytest.fixture
def config(tmp_path):
    env = tmp_path / "pornic.env"
    env.write_text(
        "BRIDGE_SERVER_URL=http://localhost:8090\n"
        "BRIDGE_NODE_ID=1\n"
        "BRIDGE_SECRET=s3cr3t\n"
        "BRIDGE_SITE_SLUG=pornic\n"
        f"BRIDGE_DB_PATH={tmp_path / 'birdnet.db'}\n"
        f"BRIDGE_CLIPS_DIR={tmp_path / 'clips'}\n"
        f"BRIDGE_STATE_FILE={tmp_path / 'state.json'}\n",
        encoding="utf-8",
    )
    return load_config(env)


@pytest.mark.asyncio
async def test_pending_event_is_relayed_immediately(config) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(f"{NODE_API}/api/v2/detections/stream").mock(
                return_value=httpx.Response(200, content=_SSE_BODY)
            )
            pending_route = mock.post(f"{SERVER_API}/nodes/1/pending").mock(return_value=httpx.Response(204))

            stop_event = asyncio.Event()

            async def _stop_soon() -> None:
                await asyncio.sleep(0.15)
                stop_event.set()

            await asyncio.gather(
                run_pending_relay(node_client, server_client, config, stop_event),
                _stop_soon(),
            )

            assert pending_route.called
            body = pending_route.calls[0].request.content
            payload = json.loads(body)
            assert payload["items"][0]["scientific_name"] == "Erithacus rubecula"
            assert payload["items"][0]["common_name"] == "Rougegorge familier"


@pytest.mark.asyncio
async def test_malformed_pending_item_does_not_kill_the_relay(config, caplog) -> None:
    """Reproduit le bug confirmé : sans le correctif, une KeyError sur un item 'pending' mal formé
    sortait de `_consume_sse` sans être rattrapée, tuant silencieusement `consume_task` pour le
    reste du process — plus aucune détection locale n'était plus jamais relayée."""
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(f"{NODE_API}/api/v2/detections/stream").mock(
                return_value=httpx.Response(200, content=_SSE_BODY_MALFORMED_THEN_VALID)
            )
            pending_route = mock.post(f"{SERVER_API}/nodes/1/pending").mock(return_value=httpx.Response(204))

            stop_event = asyncio.Event()

            async def _stop_soon() -> None:
                await asyncio.sleep(0.15)
                stop_event.set()

            with caplog.at_level(logging.WARNING, logger="bridge.pending_relay"):
                await asyncio.gather(
                    run_pending_relay(node_client, server_client, config, stop_event),
                    _stop_soon(),
                )

            # L'item malformé est journalisé (visible), mais l'item valide suivant, sur le même
            # flux, est bien relayé : le flux SSE n'est jamais tué par l'item fautif.
            assert any("mal formé" in r.message for r in caplog.records)
            assert pending_route.called
            payload = json.loads(pending_route.calls[-1].request.content)
            assert payload["items"][0]["scientific_name"] == "Erithacus rubecula"


@pytest.mark.asyncio
async def test_backoff_resets_on_successful_connection_even_without_any_event(monkeypatch, config) -> None:
    """Avant le correctif, `backoff.reset()` n'était appelé qu'à la réception d'un évènement
    'pending' : une connexion SSE qui réussit mais reste des heures sans détection (nuit calme) ne
    remettait jamais le compteur à zéro, si bien qu'une reconnexion ultérieure (fermeture propre du
    flux) réutilisait un délai gonflé par les tentatives précédentes."""
    reset_calls: list[str] = []
    real_backoff_cls = pending_relay.Backoff

    class _SpyBackoff(real_backoff_cls):
        def reset(self) -> None:
            reset_calls.append("reset")
            super().reset()

    monkeypatch.setattr(pending_relay, "Backoff", _SpyBackoff)

    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            # Connexion réussie, fermée immédiatement sans jamais émettre d'évènement 'pending'.
            mock.get(f"{NODE_API}/api/v2/detections/stream").mock(return_value=httpx.Response(200, content=b""))
            mock.post(f"{SERVER_API}/nodes/1/pending").mock(return_value=httpx.Response(204))

            stop_event = asyncio.Event()

            async def _stop_soon() -> None:
                await asyncio.sleep(0.1)
                stop_event.set()

            await asyncio.gather(
                run_pending_relay(node_client, server_client, config, stop_event),
                _stop_soon(),
            )

    assert "reset" in reset_calls
