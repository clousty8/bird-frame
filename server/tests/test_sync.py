from tests.conftest import make_detection


def _sync(client, node_id, headers, since_id, node_max_id, detections):
    return client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=headers,
        json={"since_id": since_id, "node_max_id": node_max_id, "detections": detections},
    )


def test_sync_accepts_and_is_idempotent(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, confidence=0.9)

    resp1 = _sync(client, node_id, auth_headers, 0, 1, [det])
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    assert body1["accepted"] == 1
    assert body1["duplicates"] == 0
    assert body1["synced_up_to_id"] == 1

    # Rejeu du même lot après coupure réseau : no-op silencieux (contrat §4.2).
    resp2 = _sync(client, node_id, auth_headers, 0, 1, [det])
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["accepted"] == 0
    assert body2["duplicates"] == 1
    assert body2["synced_up_to_id"] == 1


def test_sync_cursor_advances_and_is_canonical(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    dets = [make_detection(i, confidence=0.5 + i * 0.01) for i in range(1, 4)]
    resp = _sync(client, node_id, auth_headers, 0, 3, dets)
    assert resp.status_code == 200
    assert resp.json()["synced_up_to_id"] == 3

    # since_id en avance sur le curseur serveur -> 409 cursor_ahead, curseur canonique renvoyé
    resp = _sync(client, node_id, auth_headers, 10, 10, [])
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "cursor_ahead"
    assert body["details"]["synced_up_to_id"] == 3


def test_sync_node_db_reset(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _sync(client, node_id, auth_headers, 0, 5, [make_detection(5)])

    resp = _sync(client, node_id, auth_headers, 0, 2, [])
    assert resp.status_code == 409
    assert resp.json()["error"] == "node_db_reset"


def test_sync_rejects_invalid_item_without_failing_whole_batch(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    good = make_detection(1, confidence=0.9)
    bad = make_detection(2, confidence=1.5)  # hors [0,1] -> rejeté, pas un 422 global

    resp = _sync(client, node_id, auth_headers, 0, 2, [good, bad])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["node_local_id"] == 2
    # Le curseur avance même sur l'élément rejeté.
    assert body["synced_up_to_id"] == 2


def test_sync_rejects_path_traversal_scientific_name(client, registered_node, auth_headers):
    # scientific_name devient un segment de chemin de fichier à l'upload du clip
    # (clip_paths, contrat §4.3) : un nom contenant `/` ou `..` doit être rejeté ici,
    # avant de jamais pouvoir atteindre le système de fichiers.
    node_id = registered_node["node_id"]
    good = make_detection(1, confidence=0.9)
    evil_slash = make_detection(2, confidence=0.9, scientific_name="/etc/cron.d")
    evil_dotdot = make_detection(3, confidence=0.9, scientific_name="../../../../tmp/pwn")

    resp = _sync(client, node_id, auth_headers, 0, 3, [good, evil_slash, evil_dotdot])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] == 1
    assert {r["node_local_id"] for r in body["rejected"]} == {2, 3}
    # Le curseur avance même sur les éléments rejetés.
    assert body["synced_up_to_id"] == 3

    species = client.get("/api/v1/sites/pornic/species").json()["species"]
    names = {s["scientific_name"] for s in species}
    assert "/etc/cron.d" not in names
    assert "../../../../tmp/pwn" not in names


def test_sync_batch_too_large(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    dets = [make_detection(i) for i in range(1, 202)]
    resp = _sync(client, node_id, auth_headers, 0, 201, dets)
    assert resp.status_code == 422
    assert resp.json()["error"] == "batch_too_large"


def test_sync_canonicalizes_alias(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Coloeus monedula", common_name="Choucas des tours")
    resp = _sync(client, node_id, auth_headers, 0, 1, [det])
    assert resp.status_code == 200

    species = client.get("/api/v1/sites/pornic/species").json()["species"]
    names = {s["scientific_name"] for s in species}
    assert "Corvus monedula" in names
    assert "Coloeus monedula" not in names


def test_sync_want_clips_lists_detection_needing_audio(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, has_clip=True, clip_name="2026/09/test.wav")
    resp = _sync(client, node_id, auth_headers, 0, 1, [det])
    assert resp.status_code == 200
    assert resp.json()["want_clips"] == [1]

    # Un second cycle sans nouvelle détection doit toujours redemander le même clip
    # tant qu'il n'a pas été reçu.
    resp2 = _sync(client, node_id, auth_headers, 1, 1, [])
    assert resp2.json()["want_clips"] == [1]


def test_sync_same_new_name_twice_in_one_item_does_not_crash(client, registered_node, auth_headers):
    # Primaire `Coloeus monedula` (canonicalisée en `Corvus monedula`) + prédiction brute
    # `Corvus monedula` : deux entrées de cache pour le même nom dans la même transaction.
    node_id = registered_node["node_id"]
    det = make_detection(
        1,
        scientific_name="Coloeus monedula",
        common_name="Choucas des tours",
        predictions=[{"scientific_name": "Corvus monedula", "common_name": "Choucas des tours", "confidence": 0.1}],
    )
    resp = _sync(client, node_id, auth_headers, 0, 1, [det])
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] == 1
