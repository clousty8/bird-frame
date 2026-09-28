"""WP-15 (version amendée) : `GET /sites/{slug}/stats/*` — contrat §6.14 à §6.19.

Jeu de données synthétique multi-jours multi-espèces, chiffres vérifiés à la main dans
les commentaires ci-dessous. Ancré sur « aujourd'hui » (comme `tests/test_calendar.py`)
pour rester indépendant de la date d'exécution des tests, tout en gardant des totaux
déterministes.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import ADMIN_TOKEN


def _local_noon_utc(tz_name: str, local_date) -> str:
    tz = ZoneInfo(tz_name)
    noon_local = datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0, tzinfo=tz)
    return noon_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_local(tz_name: str):
    return datetime.now(ZoneInfo(tz_name)).date()


def _build_detection(node_local_id: int, scientific_name: str, confidence: float, when_utc: str) -> dict:
    return {
        "node_local_id": node_local_id,
        "detected_at_utc": when_utc,
        "scientific_name": scientific_name,
        "common_name": None,
        "confidence": confidence,
        "source_id": None,
        "source_display_name": None,
        "clip_name": None,
        "has_clip": False,
        "predictions": [],
    }


def test_stats_hand_verified_multi_day_multi_species(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    tz = "Europe/Paris"
    today = _today_local(tz)

    dets: list[dict] = []
    next_id = [1]

    def add(days_ago: int, name: str, confidences: list[float]) -> None:
        d = today - timedelta(days=days_ago)
        base = datetime.strptime(_local_noon_utc(tz, d), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        for i, conf in enumerate(confidences):
            when = (base + timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dets.append(_build_detection(next_id[0], name, conf, when))
            next_id[0] += 1

    # Aujourd'hui : 2 Rougegorge + 1 Merle.
    add(0, "Erithacus rubecula", [0.9, 0.8])
    add(0, "Turdus merula", [0.5])
    # Hier : 5 Merle — la meilleure journée.
    add(1, "Turdus merula", [0.5, 0.6, 0.7, 0.8, 0.9])
    # Avant-hier : 2 Mésange.
    add(2, "Parus major", [0.6, 0.7])
    # J-3 : rien (coupe le streak).
    # J-5 : 1 Corneille.
    add(5, "Corvus corone", [0.4])

    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": len(dets), "detections": dets},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] == len(dets) == 11

    # ---------- KPIs (§6.14) ----------
    kpis = client.get("/api/v1/sites/pornic/stats/kpis").json()
    assert kpis["site_slug"] == "pornic"
    assert kpis["timezone"] == tz
    assert kpis["date"] == today.isoformat()
    assert kpis["lifetime_detections"] == 11
    assert kpis["lifetime_species"] == 4  # Erithacus, Turdus, Parus, Corvus
    assert kpis["today_detections"] == 3
    assert kpis["today_species"] == 2
    assert kpis["best_day"] == {"date": (today - timedelta(days=1)).isoformat(), "count": 5}
    assert kpis["streak_days"] == 3  # J, J-1, J-2 ; rien à J-3
    assert kpis["first_detection_utc"] is not None
    assert kpis["last_detection_utc"] is not None

    # ---------- Daily (§6.15) ----------
    start = (today - timedelta(days=5)).isoformat()
    end = today.isoformat()
    daily = client.get(f"/api/v1/sites/pornic/stats/daily?start={start}&end={end}").json()
    assert daily["timezone"] == tz
    assert len(daily["days"]) == 6  # J-5 à J inclus
    by_date = {d["date"]: (d["total"], d["species_count"]) for d in daily["days"]}
    assert by_date[(today - timedelta(days=5)).isoformat()] == (1, 1)
    assert by_date[(today - timedelta(days=4)).isoformat()] == (0, 0)
    assert by_date[(today - timedelta(days=3)).isoformat()] == (0, 0)
    assert by_date[(today - timedelta(days=2)).isoformat()] == (2, 1)
    assert by_date[(today - timedelta(days=1)).isoformat()] == (5, 1)
    assert by_date[today.isoformat()] == (3, 2)

    # ---------- Hourly (§6.16) : tout à midi local ----------
    hourly = client.get(f"/api/v1/sites/pornic/stats/hourly?start={start}&end={end}").json()
    assert len(hourly["hours"]) == 24
    noon = next(h for h in hourly["hours"] if h["hour"] == 12)
    assert noon["total"] == 11
    assert sum(h["total"] for h in hourly["hours"] if h["hour"] != 12) == 0
    top = {s["scientific_name"]: s["count"] for s in noon["species"]}
    assert top == {
        "Turdus merula": 6,
        "Erithacus rubecula": 2,
        "Parus major": 2,
        "Corvus corone": 1,
    }

    # ---------- Species ranking (§6.17) ----------
    ranking = client.get(f"/api/v1/sites/pornic/stats/species?start={start}&end={end}").json()
    assert ranking["total_species"] == 4
    names_ranked = [s["scientific_name"] for s in ranking["species"]]
    # Turdus (6) > Erithacus (2) = Parus (2, égalité -> ordre alphabétique) > Corvus (1).
    assert names_ranked == ["Turdus merula", "Erithacus rubecula", "Parus major", "Corvus corone"]
    assert [s["rank"] for s in ranking["species"]] == [1, 2, 3, 4]

    erithacus = next(s for s in ranking["species"] if s["scientific_name"] == "Erithacus rubecula")
    assert erithacus["total"] == 2
    assert erithacus["days_seen"] == 1
    assert erithacus["max_confidence"] == 0.9
    assert erithacus["avg_confidence"] == 0.85

    turdus = next(s for s in ranking["species"] if s["scientific_name"] == "Turdus merula")
    assert turdus["total"] == 6
    assert turdus["days_seen"] == 2  # aujourd'hui + hier

    # ---------- Confidence (§6.19), restreint à une espèce et une journée ----------
    conf = client.get(
        f"/api/v1/sites/pornic/stats/confidence?start={today.isoformat()}&end={today.isoformat()}"
        "&species=Erithacus%20rubecula"
    ).json()
    assert conf["species"] == "Erithacus rubecula"
    assert conf["total"] == 2
    buckets = {round(b["min"], 1): b["count"] for b in conf["buckets"]}
    assert len(conf["buckets"]) == 10
    assert buckets[0.8] == 1  # confiance 0.8 -> classe [0.8, 0.9)
    assert buckets[0.9] == 1  # confiance 0.9 -> classe [0.9, 1.0]
    assert sum(b["count"] for b in conf["buckets"]) == 2


def test_stats_heatmap_week_index_hand_verified(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    tz = "Europe/Paris"
    today = _today_local(tz)
    det = _build_detection(1, "Turdus merula", 0.9, _local_noon_utc(tz, today))
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text

    expected_week_index = (today.timetuple().tm_yday - 1) // 7  # contrat §1.4, pas ISO

    body = client.get(f"/api/v1/sites/pornic/stats/heatmap?species=Turdus%20merula&year={today.year}").json()
    assert body["year"] == today.year
    assert body["week_count"] == 53
    species = body["species"][0]
    assert species["scientific_name"] == "Turdus merula"
    assert species["total"] == 1
    assert len(species["weeks"]) == 53
    assert species["weeks"][expected_week_index] == 1
    assert sum(species["weeks"]) == 1


def test_stats_heatmap_more_than_40_species_422(client, registered_node):
    qs = "&".join(f"species=Testus%20speciesus{i}" for i in range(41))
    resp = client.get(f"/api/v1/sites/pornic/stats/heatmap?{qs}")
    assert resp.status_code == 422


def test_stats_respects_site_timezone_for_local_day_boundary(client):
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "kiritimati",
            "site_name": "Kiritimati",
            "node_name": "Test node UTC+14",
            "timezone": "Pacific/Kiritimati",
            "lat": 1.87,
            "lon": -157.4,
            "auto_main_name": False,
        },
    )
    assert resp.status_code == 201, resp.text
    node = resp.json()
    headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}

    # 23:00 UTC le 1er janvier = 13:00 le 2 janvier à Kiritimati (UTC+14) : la journée
    # locale DOIT être le 2, jamais le 1er (contrat §1.4 — jamais calculée en UTC).
    det = _build_detection(1, "Turdus merula", 0.9, "2026-01-01T23:00:00Z")
    sync = client.post(
        f"/api/v1/nodes/{node['node_id']}/sync",
        headers=headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert sync.status_code == 200, sync.text

    day1 = client.get("/api/v1/sites/kiritimati/stats/daily?start=2026-01-01&end=2026-01-01").json()
    assert day1["days"][0]["total"] == 0

    day2 = client.get("/api/v1/sites/kiritimati/stats/daily?start=2026-01-02&end=2026-01-02").json()
    assert day2["days"][0]["total"] == 1


def test_stats_empty_site_returns_zeros_not_errors(client, registered_node):
    kpis = client.get("/api/v1/sites/pornic/stats/kpis").json()
    assert kpis["lifetime_detections"] == 0
    assert kpis["lifetime_species"] == 0
    assert kpis["best_day"] is None
    assert kpis["streak_days"] == 0
    assert kpis["first_detection_utc"] is None

    daily = client.get("/api/v1/sites/pornic/stats/daily").json()
    assert len(daily["days"]) == 30
    assert all(d["total"] == 0 for d in daily["days"])


def test_stats_invalid_range_400_and_bad_date_422(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/stats/daily?start=2026-09-27&end=2026-09-01")
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_range"

    resp = client.get("/api/v1/sites/pornic/stats/daily?start=not-a-date")
    assert resp.status_code == 422


def test_stats_unknown_site_404(client):
    resp = client.get("/api/v1/sites/nowhere/stats/kpis")
    assert resp.status_code == 404
    assert resp.json()["error"] == "site_not_found"


def test_stats_exclude_impossible_species(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    tz = "Europe/Paris"
    today = _today_local(tz)
    det = _build_detection(1, "Columba livia", 0.9, _local_noon_utc(tz, today))
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    client.put("/api/v1/sites/pornic/species-rules/Columba%20livia", json={"rule": "impossible"})

    kpis = client.get("/api/v1/sites/pornic/stats/kpis").json()
    assert kpis["lifetime_detections"] == 0  # vue effective (§1.7) : exclue partout
