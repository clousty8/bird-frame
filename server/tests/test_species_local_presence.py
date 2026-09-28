"""Présence locale par site dans `GET /species/{name}` (contrat §6.9 `local_presence`)."""

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.species_data.local_presence import haversine_km, level_for_score, nearest_reference_city
from app.species_data.store import load_species_data
from tests.conftest import ADMIN_TOKEN, FIXTURES_SPECIES_DATA, make_detection

# Fixture base/Erithacus_rubecula.json, ville « Pornic » : une valeur par seuil (bornes incluses).
ROBIN_PORNIC_LEVELS = [
    "tres_courant",  # 0.5
    "courant",  # 0.4999
    "courant",  # 0.2
    "peu_frequent",  # 0.1999
    "peu_frequent",  # 0.05
    "rare",  # 0.0499
    "rare",  # 0.01
    "absent",  # 0.0099
    "absent",  # 0.0
    "tres_courant",  # 0.6
    "tres_courant",  # 0.9
    "tres_courant",  # 1.0
]


def _register_site(client, slug: str, name: str, lat: float | None, lon: float | None) -> dict:
    body = {
        "site_slug": slug,
        "site_name": name,
        "node_name": f"Nœud {name}",
        "timezone": "Europe/Paris",
        "lat": lat,
        "lon": lon,
        "auto_main_name": False,
    }
    resp = client.post("/api/v1/nodes/register", headers={"X-Admin-Token": ADMIN_TOKEN}, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _current_month() -> int:
    return datetime.now(ZoneInfo("Europe/Paris")).month


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1.0, "tres_courant"),
        (0.5, "tres_courant"),
        (0.4999, "courant"),
        (0.2, "courant"),
        (0.1999, "peu_frequent"),
        (0.05, "peu_frequent"),
        (0.0499, "rare"),
        (0.01, "rare"),
        (0.0099, "absent"),
        (0.0, "absent"),
    ],
)
def test_level_thresholds(score, expected):
    assert level_for_score(score) == expected


def test_nearest_reference_city_and_distance():
    cities = {"Pornic": (47.1155, -2.1046), "Le Mans": (47.9819, 0.1957)}
    # Nantes est à ~43 km de Pornic et ~170 km du Mans.
    name, distance = nearest_reference_city(47.2184, -1.5536, cities)
    assert name == "Pornic"
    assert 40 < distance < 47
    assert nearest_reference_city(47.0, -2.0, {}) is None
    assert haversine_km(47.1155, -2.1046, 47.1155, -2.1046) == pytest.approx(0.0)


def test_local_presence_for_site_with_detection(client, registered_node, auth_headers):
    resp = client.post(
        f"/api/v1/nodes/{registered_node['node_id']}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [make_detection(1)]},
    )
    assert resp.status_code == 200, resp.text

    body = client.get("/api/v1/species/Erithacus%20rubecula").json()
    month = _current_month()
    expected = {
        "site_slug": "pornic",
        "site_name": "Pornic",
        "reference_city": {"name": "Pornic", "distance_km": 0.0},
        "monthly_levels": ROBIN_PORNIC_LEVELS,
        "current_month": month,
        "current_month_level": ROBIN_PORNIC_LEVELS[month - 1],
    }
    assert body["local_presence_by_site"] == {"pornic": expected}
    # Même bloc recopié dans l'entrée presence_by_site du site.
    assert body["presence_by_site"][0]["site_slug"] == "pornic"
    assert body["presence_by_site"][0]["local_presence"] == expected


def test_local_presence_for_every_site_even_without_detection(client):
    _register_site(client, "nantes", "Nantes", 47.2184, -1.5536)
    _register_site(client, "sans-position", "Jardin", None, None)

    body = client.get("/api/v1/species/Erithacus%20rubecula").json()
    assert body["presence_by_site"] == []  # aucune détection ni règle
    by_site = body["local_presence_by_site"]
    assert list(by_site) == ["nantes", "sans-position"]  # tous les sites, triés par slug

    nantes = by_site["nantes"]
    assert nantes["reference_city"]["name"] == "Pornic"
    assert 40 < nantes["reference_city"]["distance_km"] < 47
    assert nantes["monthly_levels"] == ROBIN_PORNIC_LEVELS

    # Site sans coordonnées : impossible de choisir une ville de référence.
    assert by_site["sans-position"] is None


def test_local_presence_uses_nearest_city_when_far_away(client):
    # Paris : aucune ville de référence des fixtures à moins de 80 km — la plus proche est
    # Le Mans (~185 km), le frontend le précise alors (« d'après les observations autour du Mans »).
    _register_site(client, "paris", "Paris", 48.8566, 2.3522)
    paris = client.get("/api/v1/species/Erithacus%20rubecula").json()["local_presence_by_site"]["paris"]
    assert paris["reference_city"]["name"] == "Le Mans"
    assert paris["reference_city"]["distance_km"] > 80
    assert paris["monthly_levels"] == ["tres_courant"] * 12


def test_local_presence_null_when_species_has_no_monthly_scores(client, registered_node):
    # Turdus merula : base/ sans city_monthly_scores et univers sans cityMonthlyScores.
    body = client.get("/api/v1/species/Turdus%20merula").json()
    assert body["local_presence_by_site"] == {"pornic": None}


def test_local_presence_falls_back_to_universe_scores(client, registered_node):
    # Parus major n'a pas de base/ : les scores viennent de cityMonthlyScores de l'univers.
    body = client.get("/api/v1/species/Parus%20major").json()
    levels = body["local_presence_by_site"]["pornic"]["monthly_levels"]
    assert levels[3:6] == ["rare", "peu_frequent", "rare"]
    assert levels[0] == "absent"


def test_local_presence_null_without_reference_cities_file(tmp_path: Path):
    target = tmp_path / "species-data"
    shutil.copytree(FIXTURES_SPECIES_DATA, target)
    (target / "reference_cities.json").unlink()
    store = load_species_data(target)
    assert store.reference_cities == {}
    assert store.invalid_files == []  # absence signalée par un WARNING, pas un fichier invalide


def test_invalid_reference_city_is_reported(tmp_path: Path):
    target = tmp_path / "species-data"
    shutil.copytree(FIXTURES_SPECIES_DATA, target)
    (target / "reference_cities.json").write_text(
        '{"Pornic": {"lat": 47.1155, "lon": -2.1046}, "Nulle part": {"lat": "x", "lon": 3}}', encoding="utf-8"
    )
    store = load_species_data(target)
    assert list(store.reference_cities) == ["Pornic"]
    assert [inv.file for inv in store.invalid_files] == ["reference_cities.json"]


def test_lookalikes_flag_species_with_a_page(client):
    body = client.get("/api/v1/species/Erithacus%20rubecula").json()
    flags = {lk["scientific_name"]: lk["has_page"] for lk in body["lookalikes"]}
    assert flags == {"Turdus merula": True, "Nonexistens specius": False}
