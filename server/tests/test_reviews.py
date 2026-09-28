"""WP-13 : `POST`/`GET /sites/{slug}/reviews` et `/false-negatives` — contrat §6.25 à §6.28."""

from tests.conftest import make_detection


def _sync_one(client, node_id, auth_headers, **kwargs):
    det = make_detection(1, **kwargs)
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text
    return resp


def _get_detection_id(client) -> int:
    detections = client.get("/api/v1/sites/pornic/detections").json()["detections"]
    return detections[0]["detection_id"]


def test_post_review_false_positive_creates_command_and_marks_detection(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _sync_one(client, node_id, auth_headers, scientific_name="Turdus merula", common_name="Merle noir")
    detection_id = _get_detection_id(client)

    resp = client.post(
        "/api/v1/sites/pornic/reviews",
        json={"detection_id": detection_id, "kind": "false_positive", "note": "C'était un pic épeiche"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["review"]["kind"] == "false_positive"
    assert body["review"]["detection"]["scientific_name"] == "Turdus merula"
    assert body["review"]["command_status"] == "pending"
    assert body["command_id"] is not None

    commands = client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers).json()["commands"]
    assert len(commands) == 1
    assert commands[0]["kind"] == "mark_detection_reviewed"
    assert commands[0]["payload"] == {
        "node_local_id": 1,
        "verified": "false_positive",
        "comment": "C'était un pic épeiche",
    }

    # La vue effective (contrat §1.7) exclut désormais la détection.
    calendar = client.get("/api/v1/sites/pornic/calendar").json()
    assert calendar["species"] == []

    # La vue brute, elle, la montre toujours, avec le statut de revue.
    detections = client.get("/api/v1/sites/pornic/detections").json()["detections"]
    assert detections[0]["review"] == "false_positive"
    assert detections[0]["review_note"] == "C'était un pic épeiche"


def test_reviews_ack_marks_synced_to_node(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _sync_one(client, node_id, auth_headers)
    detection_id = _get_detection_id(client)

    resp = client.post("/api/v1/sites/pornic/reviews", json={"detection_id": detection_id, "kind": "correct"})
    command_id = resp.json()["command_id"]

    ack = client.post(
        f"/api/v1/nodes/{node_id}/commands/{command_id}/ack",
        headers=auth_headers,
        json={"status": "applied", "result": None, "error": None},
    )
    assert ack.status_code == 200

    reviews = client.get("/api/v1/sites/pornic/reviews").json()["reviews"]
    assert reviews[0]["synced_to_node_at"] is not None
    assert reviews[0]["command_status"] == "applied"


def test_post_review_unknown_detection_404(client, registered_node):
    resp = client.post("/api/v1/sites/pornic/reviews", json={"detection_id": 999, "kind": "correct"})
    assert resp.status_code == 404
    assert resp.json()["error"] == "detection_not_found"


def test_get_reviews_filters_by_kind_and_paginates(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    for i in range(3):
        det = make_detection(i + 1, scientific_name=f"Testus reviewus{i}", common_name=None)
        client.post(
            f"/api/v1/nodes/{node_id}/sync",
            headers=auth_headers,
            json={"since_id": i, "node_max_id": i + 1, "detections": [det]},
        )
    detections = client.get("/api/v1/sites/pornic/detections?limit=10").json()["detections"]
    ids = [d["detection_id"] for d in detections]

    client.post("/api/v1/sites/pornic/reviews", json={"detection_id": ids[0], "kind": "correct"})
    client.post("/api/v1/sites/pornic/reviews", json={"detection_id": ids[1], "kind": "false_positive"})
    client.post("/api/v1/sites/pornic/reviews", json={"detection_id": ids[2], "kind": "false_positive"})

    all_reviews = client.get("/api/v1/sites/pornic/reviews").json()
    assert all_reviews["total"] == 3

    fp_only = client.get("/api/v1/sites/pornic/reviews?kind=false_positive").json()
    assert fp_only["total"] == 2
    assert all(r["kind"] == "false_positive" for r in fp_only["reviews"])

    paged = client.get("/api/v1/sites/pornic/reviews?limit=1&offset=1").json()
    assert len(paged["reviews"]) == 1
    assert paged["limit"] == 1
    assert paged["offset"] == 1


def test_false_negative_report_round_trip(client, registered_node):
    resp = client.post(
        "/api/v1/sites/pornic/false-negatives",
        json={
            "scientific_name": "Strix aluco",
            "approx_time_utc": "2026-09-26T21:30:00Z",
            "notes": "Hulotte entendue vers 23 h 30",
        },
    )
    assert resp.status_code == 201, resp.text
    fn = resp.json()["false_negative"]
    assert fn["scientific_name"] == "Strix aluco"
    assert fn["approx_time_utc"] == "2026-09-26T21:30:00Z"
    assert fn["reported_at"] is not None

    listed = client.get("/api/v1/sites/pornic/false-negatives").json()
    assert listed["total"] == 1
    assert listed["false_negatives"][0]["scientific_name"] == "Strix aluco"


def test_false_negative_known_species_true_when_already_detected(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _sync_one(client, node_id, auth_headers, scientific_name="Erithacus rubecula", common_name="Rougegorge familier")

    resp = client.post(
        "/api/v1/sites/pornic/false-negatives", json={"scientific_name": "Erithacus rubecula"}
    )
    assert resp.json()["false_negative"]["known_species"] is True

    resp = client.post(
        "/api/v1/sites/pornic/false-negatives", json={"scientific_name": "Nulla inventus"}
    )
    assert resp.json()["false_negative"]["known_species"] is False
