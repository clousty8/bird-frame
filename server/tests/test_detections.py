"""`GET /sites/{slug}/detections` — contrat §6.30 (liste brute, pour la revue)."""

from tests.conftest import make_detection


def test_detections_lists_raw_with_predictions_and_no_exclusion(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(
        1,
        scientific_name="Parus major",
        common_name="Mésange charbonnière",
        confidence=0.72,
        predictions=[{"scientific_name": "Columba palumbus", "common_name": "Pigeon ramier", "confidence": 0.0242}],
    )
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text

    body = client.get("/api/v1/sites/pornic/detections").json()
    assert body["total"] == 1
    d = body["detections"][0]
    assert d["node_local_id"] == 1
    assert d["scientific_name"] == "Parus major"
    assert d["effective_scientific_name"] == "Parus major"
    assert d["confidence"] == 0.72
    assert d["review"] is None
    assert d["rule"] is None
    assert d["predictions"][0] == {
        "scientific_name": "Parus major",
        "common_name_fr": "Mésange charbonnière",
        "confidence": 0.72,
        "is_primary": True,
    }
    assert d["predictions"][1]["scientific_name"] == "Columba palumbus"
    assert d["predictions"][1]["is_primary"] is False


def test_detections_shows_false_positive_still_listed_with_review(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Turdus merula", common_name="Merle noir")
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    detection_id = client.get("/api/v1/sites/pornic/detections").json()["detections"][0]["detection_id"]
    client.post("/api/v1/sites/pornic/reviews", json={"detection_id": detection_id, "kind": "false_positive"})

    body = client.get("/api/v1/sites/pornic/detections").json()
    assert body["total"] == 1  # aucune exclusion, contrairement au calendrier/stats
    assert body["detections"][0]["review"] == "false_positive"

    filtered = client.get("/api/v1/sites/pornic/detections?review=false_positive").json()
    assert filtered["total"] == 1
    none_reviewed = client.get("/api/v1/sites/pornic/detections?review=none").json()
    assert none_reviewed["total"] == 0


def test_detections_filters_by_species_min_confidence_and_date(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    dets = [
        make_detection(1, scientific_name="Turdus merula", confidence=0.9),
        make_detection(2, scientific_name="Erithacus rubecula", confidence=0.3),
    ]
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 2, "detections": dets},
    )

    by_species = client.get("/api/v1/sites/pornic/detections?species=Turdus%20merula").json()
    assert by_species["total"] == 1
    assert by_species["detections"][0]["scientific_name"] == "Turdus merula"

    by_confidence = client.get("/api/v1/sites/pornic/detections?min_confidence=0.5").json()
    assert by_confidence["total"] == 1

    all_today = client.get("/api/v1/sites/pornic/detections?date=2000-01-01").json()
    assert all_today["total"] == 0  # aucune détection ce jour-là


def test_detections_pagination(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    dets = [make_detection(i + 1, scientific_name=f"Testus speciesus{i}") for i in range(5)]
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 5, "detections": dets},
    )

    page = client.get("/api/v1/sites/pornic/detections?limit=2&offset=1").json()
    assert page["total"] == 5
    assert len(page["detections"]) == 2
    assert page["limit"] == 2
    assert page["offset"] == 1


def test_detections_unknown_site_404(client):
    resp = client.get("/api/v1/sites/nowhere/detections")
    assert resp.status_code == 404
