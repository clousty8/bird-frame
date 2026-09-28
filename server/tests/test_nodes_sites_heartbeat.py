def test_sites_list(client, registered_node):
    resp = client.get("/api/v1/sites")
    assert resp.status_code == 200
    sites = resp.json()["sites"]
    assert len(sites) == 1
    assert sites[0]["slug"] == "pornic"
    assert sites[0]["node_count"] == 1
    assert sites[0]["online"] is False


def test_nodes_list(client, registered_node):
    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["site_slug"] == "pornic"
    assert nodes[0]["synced_up_to_id"] == 0


def test_heartbeat_updates_node_status_and_marks_site_online(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/heartbeat",
        headers=auth_headers,
        json={
            "sent_at_utc": "2026-09-27T14:40:00Z",
            "bridge_version": "0.1.0",
            "birdnet_go_version": "20260823",
            "birdnet_go_reachable": True,
            "birdnet_go_pid_alive": True,
            "mic_device_name": "HyperX QuadCast 2",
            "mic_healthy": True,
            "disk_free_pct": 62.44,
            "node_db_max_id": 4627,
            "dynamic_thresholds_snapshot": [
                {
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
            ],
        },
    )
    assert resp.status_code == 200
    assert "server_time_utc" in resp.json()

    nodes = client.get("/api/v1/nodes").json()["nodes"]
    node = nodes[0]
    assert node["online"] is True
    assert node["birdnet_go_version"] == "20260823"
    assert node["disk_free_pct"] == 62.4  # arrondi 1 décimale, contrat §1.2
    assert node["node_db_max_id"] == 4627

    sites = client.get("/api/v1/sites").json()["sites"]
    assert sites[0]["online"] is True


def test_species_presence_aggregates_months_and_hours(client, registered_node, auth_headers):
    from tests.conftest import make_detection

    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Turdus merula", common_name="Merle noir")
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200

    presence = client.get("/api/v1/species/Turdus%20merula/presence?site=pornic").json()
    assert presence["site_slug"] == "pornic"
    assert presence["total"] == 1
    assert sum(presence["months"]) == 1
    assert sum(presence["hours"]) == 1
    assert presence["by_day"] is None

    presence_with_days = client.get("/api/v1/species/Turdus%20merula/presence?site=pornic&include_by_day=true").json()
    assert len(presence_with_days["by_day"]) == 365
    assert sum(d["count"] for d in presence_with_days["by_day"]) == 1


def test_sync_lag_never_negative_when_heartbeat_lags_behind_sync(client, registered_node, auth_headers):
    # Constaté en réel : heartbeat (≈ 1/min) avec node_db_max_id=5165 alors que le sync
    # (plus fréquent) a déjà avancé le curseur à 5167 → sync_lag valait -2. Contrat §6.1 : ≥ 0.
    from tests.conftest import make_detection

    node_id = registered_node["node_id"]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 7, "detections": [make_detection(7)]},
    )
    assert resp.status_code == 200, resp.text
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
            "node_db_max_id": 5,
            "dynamic_thresholds_snapshot": [],
        },
    )
    assert resp.status_code == 200, resp.text

    node = client.get("/api/v1/nodes").json()["nodes"][0]
    assert node["synced_up_to_id"] == 7
    assert node["sync_lag"] == 0
