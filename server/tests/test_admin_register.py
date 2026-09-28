from tests.conftest import ADMIN_TOKEN


def test_register_requires_admin_token(client):
    resp = client.post(
        "/api/v1/nodes/register",
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Test",
            "timezone": "Europe/Paris",
            "lat": None,
            "lon": None,
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_admin_token"


def test_register_creates_site_and_node(client):
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Mac Armand — Pornic",
            "timezone": "Europe/Paris",
            "lat": 47.1155,
            "lon": -2.1046,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["site_created"] is True
    assert body["site_slug"] == "pornic"
    assert isinstance(body["node_id"], int)
    assert len(body["bridge_shared_secret"]) > 20


def test_register_second_node_reuses_existing_site(client):
    first = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Node 1",
            "timezone": "Europe/Paris",
            "lat": 47.1,
            "lon": -2.1,
        },
    ).json()

    second = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            # site_name/timezone/lat/lon ignorés car le site existe déjà
            "site_name": "Autre nom",
            "node_name": "Node 2",
            "timezone": "Europe/London",
            "lat": 0.0,
            "lon": 0.0,
        },
    ).json()

    assert second["site_created"] is False
    assert second["site_id"] == first["site_id"]
    assert second["node_id"] != first["node_id"]


def test_register_rejects_bad_timezone(client):
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Test",
            "timezone": "Not/AZone",
            "lat": None,
            "lon": None,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


def test_sync_requires_valid_bearer(client, registered_node):
    node_id = registered_node["node_id"]

    resp = client.post(f"/api/v1/nodes/{node_id}/sync", json={"since_id": 0, "node_max_id": 0, "detections": []})
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"
    assert resp.headers.get("www-authenticate") == "Bearer"

    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers={"Authorization": "Bearer wrong-secret"},
        json={"since_id": 0, "node_max_id": 0, "detections": []},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/api/v1/nodes/999999/sync",
        headers={"Authorization": f"Bearer {registered_node['bridge_shared_secret']}"},
        json={"since_id": 0, "node_max_id": 0, "detections": []},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "node_not_found"
