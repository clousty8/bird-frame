
from app.ingest.top5 import recompute_top5
from app.models.detection import Detection
from app.models.review import Review
from tests.conftest import make_detection, make_wav_bytes


def _upload(client, node_id, headers, node_local_id, clip_name):
    return client.post(
        f"/api/v1/nodes/{node_id}/clips/{node_local_id}",
        headers=headers,
        data={"clip_name": clip_name},
        files={"audio": (f"{node_local_id}.wav", make_wav_bytes(), "audio/wav")},
    )


def test_top5_keeps_best_five_and_deletes_evicted_file_from_disk(
    client, registered_node, auth_headers, app_settings
):
    node_id = registered_node["node_id"]
    species = "Erithacus rubecula"

    # 5 premières détections : toutes entrent dans le top-5 (un seul candidat par rang).
    first_batch = [
        make_detection(i, confidence=c, has_clip=True, clip_name=f"2026/09/clip{i}.wav")
        for i, c in zip(range(1, 6), [0.50, 0.60, 0.70, 0.80, 0.90])
    ]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 5, "detections": first_batch},
    )
    assert resp.status_code == 200, resp.text
    assert sorted(resp.json()["want_clips"]) == [1, 2, 3, 4, 5]

    kept_clip_id_by_local_id = {}
    for i in range(1, 6):
        up = _upload(client, node_id, auth_headers, i, f"2026/09/clip{i}.wav")
        assert up.status_code == 201, up.text
        body = up.json()
        assert body["already_stored"] is False
        assert body["spectrogram_generated"] is True, "sox doit être disponible pour ce test"
        kept_clip_id_by_local_id[i] = body["kept_clip_id"]

    top_clips = client.get(f"/api/v1/species/{species.replace(' ', '%20')}/sites/pornic/top-clips").json()
    assert len(top_clips["clips"]) == 5
    assert all(c["audio_available"] for c in top_clips["clips"])

    # Les deux fichiers évincés (confiance 0.50 et 0.60, local_id 1 et 2) doivent
    # physiquement exister à ce stade.
    for local_id in (1, 2):
        path = app_settings.clips_dir_resolved / "pornic" / "Erithacus_rubecula" / f"{kept_clip_id_by_local_id[local_id]}.wav"
        assert path.is_file()

    # 2 détections supplémentaires, plus confiantes que tout le monde : elles doivent
    # évincer les deux plus faibles (local_id 1 et 2).
    second_batch = [
        make_detection(6, confidence=0.95, has_clip=True, clip_name="2026/09/clip6.wav"),
        make_detection(7, confidence=0.99, has_clip=True, clip_name="2026/09/clip7.wav"),
    ]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 5, "node_max_id": 7, "detections": second_batch},
    )
    assert resp.status_code == 200, resp.text

    top_clips_after = client.get(f"/api/v1/species/{species.replace(' ', '%20')}/sites/pornic/top-clips").json()
    assert len(top_clips_after["clips"]) == 5
    # Toujours 5, la meilleure (0.99) en tête (rang 1).
    assert top_clips_after["clips"][0]["confidence"] == 0.99
    assert top_clips_after["clips"][0]["rank"] == 1

    # Les deux clips évincés ne sont plus servables (404) et leur fichier a disparu du disque.
    for local_id in (1, 2):
        kept_clip_id = kept_clip_id_by_local_id[local_id]
        recording = client.get(f"/api/v1/recordings/{kept_clip_id}/audio")
        assert recording.status_code == 404
        assert recording.json()["error"] == "recording_not_found"

        path = app_settings.clips_dir_resolved / "pornic" / "Erithacus_rubecula" / f"{kept_clip_id}.wav"
        assert not path.exists(), f"le fichier évincé {path} aurait dû être supprimé du disque"


def test_upload_rejects_clip_name_mismatch(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, has_clip=True, clip_name="2026/09/real.wav")
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    resp = _upload(client, node_id, auth_headers, 1, "2026/09/wrong-name.wav")
    assert resp.status_code == 422
    assert resp.json()["error"] == "clip_name_mismatch"


def test_upload_not_wanted_when_outside_top5(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    # 6 détections de la même espèce, has_clip=True : seules les 5 meilleures entrent
    # dans le top-5. local_id=6 (confiance la plus basse) n'obtient jamais de ligne
    # kept_clips, donc son upload doit être refusé (409 clip_not_wanted).
    dets = [
        make_detection(i, confidence=c, has_clip=True, clip_name=f"2026/09/w{i}.wav")
        for i, c in zip(range(1, 7), [0.99, 0.95, 0.90, 0.85, 0.80, 0.10])
    ]
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 6, "detections": dets},
    )
    resp = _upload(client, node_id, auth_headers, 6, "2026/09/w6.wav")
    assert resp.status_code == 409
    assert resp.json()["error"] == "clip_not_wanted"


def test_upload_idempotent_already_stored(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, has_clip=True, clip_name="2026/09/idem.wav")
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    first = _upload(client, node_id, auth_headers, 1, "2026/09/idem.wav")
    assert first.status_code == 201

    second = _upload(client, node_id, auth_headers, 1, "2026/09/idem.wav")
    assert second.status_code == 200
    assert second.json()["already_stored"] is True


def test_clip_missing_frees_rank_for_next_candidate(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    dets = [
        make_detection(i, confidence=c, has_clip=True, clip_name=f"2026/09/m{i}.wav")
        for i, c in zip(range(1, 7), [0.50, 0.60, 0.70, 0.80, 0.90, 0.40])
    ]
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 6, "detections": dets},
    )
    # local_id=1 (confiance 0.50) est dans le top-5 initial (les 5 meilleurs de [1..5]),
    # local_id=6 (0.40) n'y est pas.
    resp = client.post(
        f"/api/v1/nodes/{node_id}/clips/1/missing",
        headers=auth_headers,
        json={"clip_name": "2026/09/m1.wav", "reason": "not_found"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "marked_missing"

    # Rejouer la même déclaration est sans effet (idempotent, contrat §4.4) : la ligne
    # reste "active" (evicted_at NULL) même marquée missing, donc toujours "marked_missing".
    resp2 = client.post(
        f"/api/v1/nodes/{node_id}/clips/1/missing",
        headers=auth_headers,
        json={"clip_name": "2026/09/m1.wav", "reason": "not_found"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "marked_missing"

    # Le rang libéré doit avoir fait entrer le 6e candidat (confiance 0.40, local_id 6)
    # dans le top-5 actif.
    top_clips = client.get("/api/v1/species/Erithacus%20rubecula/sites/pornic/top-clips").json()
    assert len(top_clips["clips"]) == 5
    assert any(c["detection_id"] for c in top_clips["clips"])


def test_upload_evicted_mid_flight_by_concurrent_review_leaves_no_orphan_file(
    client, registered_node, auth_headers, app_settings, monkeypatch
):
    # Constat #5 : si une autre requête (ici POST .../reviews en faux positif, dans SA
    # propre session/transaction) évince ce kept_clip pendant que le nôtre écrit son
    # fichier sur disque, l'upload ne doit ni committer les chemins sur la ligne évincée
    # ni laisser le fichier fraîchement écrit orphelin sur disque.
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Erithacus rubecula", confidence=0.9, has_clip=True, clip_name="a.wav")
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["want_clips"] == [1]

    app = client.app
    session_factory = app.state.session_local
    db = session_factory()
    try:
        detection_id = (
            db.query(Detection.id).filter(Detection.node_id == node_id, Detection.node_local_id == 1).scalar()
        )
    finally:
        db.close()
    assert detection_id is not None

    import app.fsutil as fsutil_module

    real_write_atomic = fsutil_module.write_atomic

    def evicting_write_atomic(path, content):
        # Écrit le fichier normalement, PUIS — pendant que la requête d'upload continue
        # de tourner, exactement comme la fenêtre de course décrite par le constat —
        # une AUTRE session commite une éviction de ce même kept_clip (faux positif).
        real_write_atomic(path, content)
        other_db = session_factory()
        try:
            detection = other_db.get(Detection, detection_id)
            other_db.add(Review(detection_id=detection.id, kind="false_positive"))
            other_db.commit()
            recompute_top5(other_db, detection.site_id, detection.scientific_name)
        finally:
            other_db.close()

    monkeypatch.setattr("app.api.ingest.write_atomic", evicting_write_atomic)

    up = client.post(
        f"/api/v1/nodes/{node_id}/clips/1",
        headers=auth_headers,
        data={"clip_name": "a.wav"},
        files={"audio": ("1.wav", make_wav_bytes(), "audio/wav")},
    )
    assert up.status_code == 409, up.text
    assert up.json()["error"] == "clip_not_wanted"

    # Rien d'orphelin sur disque : le fichier écrit pendant la fenêtre de course a été
    # nettoyé plutôt que laissé sans jamais être référencé par aucune ligne active.
    species_dir = app_settings.clips_dir_resolved / "pornic" / "Erithacus_rubecula"
    assert not any(species_dir.glob("*")), list(species_dir.glob("*"))

    db = session_factory()
    try:
        from app.models.kept_clip import KeptClip

        kept_clip = db.query(KeptClip).filter(KeptClip.detection_id == detection_id).first()
        assert kept_clip.evicted_at is not None
        assert kept_clip.audio_path is None
        assert kept_clip.spectrogram_path is None
    finally:
        db.close()
