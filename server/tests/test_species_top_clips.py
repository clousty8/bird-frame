from tests.conftest import make_detection, make_wav_bytes


def test_top_clips_predictions_sorted_confidence_desc_primary_first(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(
        1,
        scientific_name="Erithacus rubecula",
        common_name="Rougegorge familier",
        confidence=0.72,
        has_clip=True,
        clip_name="2026/09/multi.wav",
        predictions=[
            {"scientific_name": "Columba palumbus", "common_name": "Pigeon ramier", "confidence": 0.0242},
            {"scientific_name": "Cyanistes caeruleus", "common_name": "Mésange bleue", "confidence": 0.0517},
        ],
    )
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text

    client.post(
        f"/api/v1/nodes/{node_id}/clips/1",
        headers=auth_headers,
        data={"clip_name": "2026/09/multi.wav"},
        files={"audio": ("1.wav", make_wav_bytes(), "audio/wav")},
    )

    top_clips = client.get("/api/v1/species/Erithacus%20rubecula/sites/pornic/top-clips").json()
    assert len(top_clips["clips"]) == 1
    predictions = top_clips["clips"][0]["predictions"]

    assert predictions[0]["is_primary"] is True
    assert predictions[0]["scientific_name"] == "Erithacus rubecula"
    assert predictions[0]["confidence"] == 0.72

    secondaries = predictions[1:]
    assert [p["scientific_name"] for p in secondaries] == ["Cyanistes caeruleus", "Columba palumbus"]
    assert all(p["is_primary"] is False for p in secondaries)
    confidences = [p["confidence"] for p in secondaries]
    assert confidences == sorted(confidences, reverse=True)


def test_top_clips_unknown_species_or_site_returns_empty_list_not_404(client, registered_node):
    resp = client.get("/api/v1/species/Nonexistens%20specius/sites/pornic/top-clips")
    assert resp.status_code == 200
    assert resp.json()["clips"] == []

    resp2 = client.get("/api/v1/species/Erithacus%20rubecula/sites/nowhere/top-clips")
    assert resp2.status_code == 404
    assert resp2.json()["error"] == "site_not_found"
