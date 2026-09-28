from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def _noon_utc_today(tz_name: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_name)
    local_today = datetime.now(tz).date()
    noon_utc = datetime(local_today.year, local_today.month, local_today.day, 12, 0, 0, tzinfo=tz).astimezone(
        UTC
    )
    return local_today.isoformat(), noon_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_calendar_returns_more_than_30_species_without_truncation(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    local_date, at_utc = _noon_utc_today("Europe/Paris")

    species_count = 35
    dets = [
        {
            "node_local_id": i + 1,
            "detected_at_utc": at_utc,
            "scientific_name": f"Testus speciesus{i}",
            "common_name": None,
            "confidence": 0.5 + (i % 10) * 0.01,
            "source_id": None,
            "source_display_name": None,
            "clip_name": None,
            "has_clip": False,
            "predictions": [],
        }
        for i in range(species_count)
    ]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": species_count, "detections": dets},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] == species_count

    calendar = client.get(f"/api/v1/sites/pornic/calendar?date={local_date}").json()
    assert calendar["site_slug"] == "pornic"
    assert calendar["timezone"] == "Europe/Paris"
    assert calendar["date"] == local_date
    assert len(calendar["species"]) == species_count, "aucune troncature à 30, contrairement au comportement natif"
    assert calendar["total_detections"] == species_count

    for entry in calendar["species"]:
        assert sum(entry["hours"]) == entry["total"]
        assert entry["hours"][12] == entry["total"]  # toutes les détections sont à midi local
        assert len(entry["hours"]) == 24


def test_calendar_defaults_to_today_and_empty_day_returns_empty_list(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/calendar")
    assert resp.status_code == 200
    body = resp.json()
    assert body["species"] == []
    assert body["total_detections"] == 0


def test_calendar_unknown_site_404(client):
    resp = client.get("/api/v1/sites/nowhere/calendar")
    assert resp.status_code == 404
    assert resp.json()["error"] == "site_not_found"
