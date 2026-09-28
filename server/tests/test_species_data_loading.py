from io import BytesIO

from PIL import Image

import app.photos.proxy as photo_proxy
from tests.conftest import ADMIN_TOKEN


def test_species_list_merges_universe_and_flags_sheet(client):
    resp = client.get("/api/v1/species")
    assert resp.status_code == 200
    body = resp.json()
    by_name = {s["scientific_name"]: s for s in body["species"]}

    assert "Erithacus rubecula" in by_name
    assert by_name["Erithacus rubecula"]["has_sheet"] is True
    assert by_name["Erithacus rubecula"]["common_name_fr"] == "Rougegorge familier"
    assert by_name["Erithacus rubecula"]["in_france_universe"] is True

    # Turdus merula a une base/ mais pas de fiche : « base seule ».
    assert "Turdus merula" in by_name
    assert by_name["Turdus merula"]["has_sheet"] is False

    # Parus major n'est que dans l'univers (pas de base/ dans les fixtures).
    assert "Parus major" in by_name


def test_species_detail_merges_base_and_sheet(client):
    resp = client.get("/api/v1/species/Erithacus%20rubecula")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scientific_name"] == "Erithacus rubecula"
    assert body["taxonomy"]["family"] == "Muscicapidae"
    assert body["wikipedia"]["fr"]["title"] == "Rouge-gorge familier"
    assert body["has_sheet"] is True
    assert body["summary_fr"] is not None
    assert body["migration"]["statut"] == "migrateur partiel"
    assert body["reviewed_by_human"] is False
    assert body["france_universe"]["max_score"] == 0.9939


def test_species_detail_base_only_has_null_sheet_fields(client):
    resp = client.get("/api/v1/species/Turdus%20merula")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_sheet"] is False
    assert body["summary_fr"] is None
    assert body["migration"] is None
    assert body["lookalikes"] == []
    assert body["taxonomy"]["family"] == "Turdidae"  # la base reste disponible


def test_species_detail_unknown_returns_404(client):
    resp = client.get("/api/v1/species/Nonexistens%20specius")
    assert resp.status_code == 404
    assert resp.json()["error"] == "species_not_found"


def test_species_underscore_and_case_insensitive_lookup(client):
    resp = client.get("/api/v1/species/erithacus_RUBECULA")
    assert resp.status_code == 200
    assert resp.json()["scientific_name"] == "Erithacus rubecula"


def test_photo_not_found_for_species_without_photo(client):
    resp = client.get("/api/v1/species/Nonexistens%20specius/photo")
    assert resp.status_code == 404
    assert resp.json()["error"] == "photo_not_found"


def test_photo_downloads_once_caches_and_serves_both_sizes(client, monkeypatch):
    calls = {"n": 0}

    def fake_download(url: str) -> bytes:
        calls["n"] += 1
        buf = BytesIO()
        Image.new("RGB", (3200, 2000), color=(10, 20, 30)).save(buf, format="JPEG")
        return buf.getvalue()

    monkeypatch.setattr(photo_proxy, "_download", fake_download)

    resp_320 = client.get("/api/v1/species/Erithacus%20rubecula/photo?size=320")
    assert resp_320.status_code == 200
    assert resp_320.headers["content-type"] == "image/jpeg"
    img_320 = Image.open(BytesIO(resp_320.content))
    assert img_320.width == 320

    resp_1600 = client.get("/api/v1/species/Erithacus%20rubecula/photo?size=1600")
    assert resp_1600.status_code == 200
    img_1600 = Image.open(BytesIO(resp_1600.content))
    assert img_1600.width == 1600

    # Un seul téléchargement amont pour les deux tailles (produites ensemble au premier accès).
    assert calls["n"] == 1

    # Un second GET (taille déjà en cache) ne retélécharge pas.
    client.get("/api/v1/species/Erithacus%20rubecula/photo?size=320")
    assert calls["n"] == 1


def test_photo_invalid_size_422(client):
    resp = client.get("/api/v1/species/Erithacus%20rubecula/photo?size=999")
    assert resp.status_code == 422


def test_admin_species_data_reload(client):
    resp = client.post("/api/v1/admin/species-data/reload", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["universe_count"] == 3
    assert body["base_count"] == 2
    assert body["sheet_count"] == 1
    assert body["alias_count"] == 1
    assert body["invalid_files"] == []


def test_admin_reload_requires_token(client):
    resp = client.post("/api/v1/admin/species-data/reload")
    assert resp.status_code == 401
