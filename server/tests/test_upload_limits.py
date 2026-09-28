"""Constat #11 : une requête dont le `Content-Length` déclaré dépasse largement la
limite d'upload doit être rejetée AVANT que le corps ne soit lu/spoolé, pas seulement
après un `await audio.read()` complet (`app/api/ingest.py`)."""


def test_oversized_content_length_rejected_before_body_is_read(client, app_settings):
    huge = app_settings.max_upload_bytes + 100 * 1024 * 1024
    resp = client.get("/api/v1/health", headers={"Content-Length": str(huge)})
    assert resp.status_code == 413
    body = resp.json()
    assert body["error"] == "payload_too_large"
    assert "message" in body and "details" in body


def test_content_length_just_over_margin_rejected(client, app_settings):
    over = app_settings.max_upload_bytes + 64 * 1024 + 1
    resp = client.get("/api/v1/health", headers={"Content-Length": str(over)})
    assert resp.status_code == 413


def test_normal_requests_unaffected_by_body_size_guard(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/now")
    assert resp.status_code == 200
