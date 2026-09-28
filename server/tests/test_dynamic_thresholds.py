"""WP-14 : `GET`/`DELETE /sites/{slug}/dynamic-thresholds` — contrat §6.23, §6.24."""

_SNAPSHOT_ENTRY = {
    "species_name": "accenteur mouchet",
    "scientific_name": "Prunella modularis",
    "level": 3,
    "current_value": 0.2,
    "base_threshold": 0.6,
    "high_conf_count": 19,
    "trigger_count": 19,
    "is_active": True,
    "expires_at_utc": "2026-09-28T14:26:19Z",
    "last_triggered_utc": "2026-09-27T14:39:38Z",
    "first_created_utc": "2026-09-27T14:39:38Z",
}


def _send_heartbeat(client, node_id, auth_headers, snapshot):
    resp = client.post(
        f"/api/v1/nodes/{node_id}/heartbeat",
        headers=auth_headers,
        json={
            "sent_at_utc": "2026-09-27T14:40:00Z",
            "bridge_version": "0.1.0",
            "birdnet_go_version": "20260823",
            "birdnet_go_reachable": True,
            "birdnet_go_pid_alive": True,
            "mic_device_name": None,
            "mic_healthy": None,
            "disk_free_pct": None,
            "node_db_max_id": 0,
            "dynamic_thresholds_snapshot": snapshot,
        },
    )
    assert resp.status_code == 200, resp.text


def test_get_dynamic_thresholds_mirrors_last_heartbeat(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _send_heartbeat(client, node_id, auth_headers, [_SNAPSHOT_ENTRY])

    resp = client.get("/api/v1/sites/pornic/dynamic-thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_at"] is not None
    assert len(body["thresholds"]) == 1
    entry = body["thresholds"][0]
    assert entry["scientific_name"] == "Prunella modularis"
    assert entry["node_species_name"] == "accenteur mouchet"
    assert entry["level"] == 3
    assert entry["expires_at"] == "2026-09-28T14:26:19Z"
    assert entry["reset_pending"] is False


def test_get_dynamic_thresholds_empty_site_returns_empty_list(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/dynamic-thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_at"] is None
    assert body["thresholds"] == []


def test_delete_dynamic_threshold_creates_reset_command_and_marks_reset_pending(
    client, registered_node, auth_headers
):
    node_id = registered_node["node_id"]
    _send_heartbeat(client, node_id, auth_headers, [_SNAPSHOT_ENTRY])

    resp = client.delete("/api/v1/sites/pornic/dynamic-thresholds/Prunella%20modularis")
    assert resp.status_code == 202, resp.text
    commands = resp.json()["commands"]
    assert len(commands) == 1
    assert commands[0]["kind"] == "reset_dynamic_threshold"
    assert commands[0]["payload"]["scientific_name"] == "Prunella modularis"
    assert commands[0]["status"] == "pending"

    # Tant que le heartbeat suivant n'est pas arrivé, l'instantané affiche encore
    # l'ancienne valeur mais marquée « reset en cours » (contrat §6.23-24).
    thresholds = client.get("/api/v1/sites/pornic/dynamic-thresholds").json()["thresholds"]
    assert thresholds[0]["reset_pending"] is True

    node_commands = client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers).json()["commands"]
    assert any(c["kind"] == "reset_dynamic_threshold" for c in node_commands)


def test_delete_dynamic_threshold_unknown_species_404(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _send_heartbeat(client, node_id, auth_headers, [_SNAPSHOT_ENTRY])

    resp = client.delete("/api/v1/sites/pornic/dynamic-thresholds/Larus%20argentatus")
    assert resp.status_code == 404
    assert resp.json()["error"] == "threshold_not_found"


def test_get_dynamic_thresholds_rounds_float32_noise(client, registered_node, auth_headers):
    # Valeurs réelles relayées depuis BirdNET-Go (float32) : contrat §1.2, seuils arrondis à
    # 4 décimales dans les réponses navigateur.
    node_id = registered_node["node_id"]
    entry = {**_SNAPSHOT_ENTRY, "current_value": 0.30000001192092896, "base_threshold": 0.6000000238418579}
    _send_heartbeat(client, node_id, auth_headers, [entry])

    body = client.get("/api/v1/sites/pornic/dynamic-thresholds").json()
    assert body["thresholds"][0]["current_value"] == 0.3
    assert body["thresholds"][0]["base_threshold"] == 0.6
