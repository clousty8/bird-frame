import asyncio
import time

from app.api.sites import _read_site_online, _read_site_pending, sse_event_stream
from tests.conftest import ADMIN_TOKEN, make_detection


def test_now_before_any_activity(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/now")
    assert resp.status_code == 200
    body = resp.json()
    assert body["site_slug"] == "pornic"
    assert body["pending"] == []
    assert body["recent"] == []
    # Le nœud existe mais n'a encore jamais envoyé de heartbeat/ingestion authentifiée
    # avec un node_status déjà en base à ce stade précis du test.
    assert body["node_status"] is None or body["node_status"]["online"] is False


def test_pending_then_now_shows_it(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/pending",
        headers=auth_headers,
        json={
            "snapshot_at_unix": int(time.time()),
            "items": [
                {
                    "scientific_name": "Erithacus rubecula",
                    "common_name": "Rougegorge familier",
                    "status": "active",
                    "hit_count": 3,
                    "confidence_hint": None,
                    "first_detected_unix": int(time.time()) - 5,
                    "last_updated_unix": int(time.time()),
                    "source_id": "audio_card_test",
                }
            ],
        },
    )
    assert resp.status_code == 204

    now = client.get("/api/v1/sites/pornic/now").json()
    assert len(now["pending"]) == 1
    item = now["pending"][0]
    assert item["scientific_name"] == "Erithacus rubecula"
    assert item["common_name_fr"] == "Rougegorge familier"
    assert item["status"] == "active"
    assert now["node_status"]["online"] is True


def test_now_recent_shows_fresh_detection(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Turdus merula", common_name="Merle noir", minutes_ago=1)
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200

    now = client.get("/api/v1/sites/pornic/now").json()
    assert len(now["recent"]) == 1
    assert now["recent"][0]["scientific_name"] == "Turdus merula"
    assert now["recent"][0]["common_name_fr"] == "Merle noir"


def test_pending_sse_emits_initial_snapshot(client, registered_node, auth_headers):
    # Le flux SSE de production ne se termine jamais : le driver de test HTTP habituel
    # (TestClient synchrone) ne sait pas consommer un flux infini par morceaux et reste
    # bloqué à la déconnexion. On appelle donc directement le générateur qui alimente la
    # route (`sse_event_stream`, factorisé dans app/api/sites.py pour cette raison),
    # avec un faux `is_disconnected` qui coupe le flux après le premier événement —
    # exactement ce qui arriverait avec un vrai client qui ferme la connexion.
    node_id = registered_node["node_id"]
    client.post(
        f"/api/v1/nodes/{node_id}/pending",
        headers=auth_headers,
        json={
            "snapshot_at_unix": int(time.time()),
            "items": [
                {
                    "scientific_name": "Turdus merula",
                    "common_name": "Merle noir",
                    "status": "active",
                    "hit_count": 1,
                    "confidence_hint": None,
                    "first_detected_unix": int(time.time()),
                    "last_updated_unix": int(time.time()),
                    "source_id": None,
                }
            ],
        },
    )

    from app.models.site import Site

    app = client.app
    session_factory = app.state.session_local
    db = session_factory()
    try:
        site_id = db.query(Site.id).filter(Site.slug == "pornic").scalar()
    finally:
        db.close()

    collected = asyncio.run(
        asyncio.wait_for(
            _collect_first_events(session_factory, app.state.species_data, app.state.pending_bus, site_id),
            timeout=5,
        )
    )

    assert "retry: 3000" in collected
    assert "event: pending" in collected
    assert "Turdus merula" in collected
    assert '"site_slug":"pornic"' in collected


async def _collect_first_events(session_factory, store, bus, site_id: int) -> str:
    call_count = {"n": 0}

    async def is_disconnected() -> bool:
        # Faux : jamais déconnecté avant d'avoir lu le premier événement, déconnecté
        # ensuite (simule un client qui ferme après avoir reçu son instantané initial).
        call_count["n"] += 1
        return call_count["n"] > 1

    generator = sse_event_stream(
        session_factory, store, bus, site_id=site_id, site_slug="pornic", is_disconnected=is_disconnected
    )
    collected = ""
    try:
        collected += await generator.__anext__()  # "retry: 3000\n\n"
        collected += await generator.__anext__()  # event: pending (instantané initial)
    finally:
        await generator.aclose()
    return collected


def test_sse_pollers_do_not_hold_open_db_connections(client, registered_node):
    # Constat #10 : `_read_site_pending`/`_read_site_online` tenaient auparavant la
    # `Session` injectée par route (une par connexion SSE, potentiellement des heures)
    # au lieu d'ouvrir/refermer une session courte à chaque poll — épuisant le pool
    # SQLite (5 + 10 de marge) si une quinzaine de clients SSE restaient connectés.
    # Ici : après un poll, aucune connexion ne doit rester extraite du pool.
    from app.models.site import Site

    app = client.app
    engine = app.state.engine
    session_factory = app.state.session_local

    db = session_factory()
    try:
        site_id = db.query(Site.id).filter(Site.slug == "pornic").scalar()
    finally:
        db.close()

    assert engine.pool.checkedout() == 0

    _read_site_pending(session_factory, site_id, app.state.pending_bus, app.state.species_data)
    assert engine.pool.checkedout() == 0, "_read_site_pending a laissé une connexion ouverte"

    _read_site_online(session_factory, site_id)
    assert engine.pool.checkedout() == 0, "_read_site_online a laissé une connexion ouverte"


def test_heartbeat_event_node_online_matches_principal_node_not_any_node(client, registered_node, auth_headers):
    # Constat #3 : contrat §6.4, `node_online` de l'event `heartbeat` = `online` du nœud
    # PRINCIPAL (même nœud que `GET /sites/{slug}/now`), pas « au moins un nœud du site
    # en ligne ». Deuxième nœud enregistré sur le même site, jamais contacté depuis (pas
    # de NodeStatus) : `_read_site_online` doit rester cohérent avec `/now`.
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Second node (jamais contacté)",
            "timezone": "Europe/Paris",
            "lat": 47.1155,
            "lon": -2.1046,
            "auto_main_name": False,
        },
    )
    assert resp.status_code == 201, resp.text

    node_id = registered_node["node_id"]
    hb = client.post(
        f"/api/v1/nodes/{node_id}/heartbeat",
        headers=auth_headers,
        json={
            "sent_at_utc": "2026-09-27T14:40:00Z",
            "bridge_version": "0.1.0",
            "birdnet_go_version": "20260823",
            "birdnet_go_reachable": True,
            "birdnet_go_pid_alive": True,
            "mic_device_name": "Test mic",
            "mic_healthy": True,
            "disk_free_pct": 50.0,
            "node_db_max_id": 1,
            "dynamic_thresholds_snapshot": [],
        },
    )
    assert hb.status_code == 200, hb.text

    now = client.get("/api/v1/sites/pornic/now").json()
    assert now["node_status"]["online"] is True
    assert now["node_status"]["node_id"] == node_id

    from app.models.site import Site

    app = client.app
    session_factory = app.state.session_local
    db = session_factory()
    try:
        site_id = db.query(Site.id).filter(Site.slug == "pornic").scalar()
    finally:
        db.close()

    online = _read_site_online(session_factory, site_id)
    assert online == now["node_status"]["online"]
