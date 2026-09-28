"""Routes `/sites/{slug}/stats/*` — contrat §6.14 à §6.19 (WP-15, version amendée).

Calculées à partir de la table `detections` du serveur (jamais un proxy vers le nœud —
amendement `architecture.md` §9bis du 27/09/2026) : restent disponibles hors ligne.
Vue **effective** partout (§1.7) : détections valides, espèce = `COALESCE(redirected_to,
scientific_name)`, en excluant les espèces `impossible` sur le site.

Agrégation faite en Python sur les lignes déjà filtrées par site/plage en SQL, comme le
reste du code navigateur (`app/api/sites.py`, `app/api/species.py`) — cohérent avec le
style existant, à l'échelle familiale visée (pas de sur-ingénierie sur des `GROUP BY` SQL
qui n'apporteraient rien de mesurable ici).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404, impossible_names_for_site
from app.deps import get_db, get_species_data
from app.errors import ApiError
from app.ingest.valid_detection import is_valid_detection_expr
from app.live.compute import photo_url_for, resolve_common_name_fr
from app.models.detection import Detection
from app.species_data.store import SpeciesDataStore
from app.time_utils import parse_local_date, round4, today_local

router = APIRouter(tags=["stats"])

_DEFAULT_RANGE_DAYS = 30  # 30 jours inclusifs = aujourd'hui - 29


def _parse_date_param(raw: str) -> date:
    try:
        return parse_local_date(raw)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc


def _resolve_range(tz_name: str, start: str | None, end: str | None) -> tuple[date, date]:
    """Défauts et validation communs aux stats à plage (contrat, « Statistiques —
    règles communes »)."""
    if start is None and end is None:
        end_d = date.fromisoformat(today_local(tz_name))
        start_d = end_d - timedelta(days=_DEFAULT_RANGE_DAYS - 1)
    elif start is not None and end is None:
        start_d = _parse_date_param(start)
        end_d = start_d + timedelta(days=_DEFAULT_RANGE_DAYS - 1)
    elif start is None and end is not None:
        end_d = _parse_date_param(end)
        start_d = end_d - timedelta(days=_DEFAULT_RANGE_DAYS - 1)
    else:
        start_d = _parse_date_param(start)  # type: ignore[arg-type]
        end_d = _parse_date_param(end)  # type: ignore[arg-type]

    if start_d > end_d:
        raise ApiError(400, "invalid_range", "start doit être antérieur ou égal à end.")
    return start_d, end_d


def _effective_rows(
    db: Session, site_id: int, start_d: date | None, end_d: date | None
) -> list[Detection]:
    """Détections valides du site (§1.7), bornées en date locale si demandé, avec les
    espèces effectives `impossible` déjà retirées."""
    query = db.query(Detection).filter(Detection.site_id == site_id, is_valid_detection_expr())
    if start_d is not None:
        query = query.filter(Detection.detected_local_date >= start_d.isoformat())
    if end_d is not None:
        query = query.filter(Detection.detected_local_date <= end_d.isoformat())

    impossible = impossible_names_for_site(db, site_id)
    return [
        d
        for d in query.all()
        if (d.redirected_to_scientific_name or d.scientific_name) not in impossible
    ]


def _effective_name(d: Detection) -> str:
    return d.redirected_to_scientific_name or d.scientific_name


def _compute_streak(by_day_count: dict[str, int], today_str: str) -> int:
    today_d = date.fromisoformat(today_str)
    if by_day_count.get(today_str, 0) > 0:
        cursor = today_d
    else:
        yesterday_str = (today_d - timedelta(days=1)).isoformat()
        if by_day_count.get(yesterday_str, 0) == 0:
            return 0
        cursor = today_d - timedelta(days=1)

    streak = 0
    while by_day_count.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@router.get("/sites/{slug}/stats/kpis")
def get_stats_kpis(slug: str, db: Session = Depends(get_db)) -> dict:
    site = get_site_or_404(db, slug)
    today_str = today_local(site.timezone)
    rows = _effective_rows(db, site.id, None, None)  # toute la période, contrat §6.14

    species_seen: set[str] = set()
    by_day_count: dict[str, int] = {}
    first_utc: str | None = None
    last_utc: str | None = None
    for d in rows:
        species_seen.add(_effective_name(d))
        by_day_count[d.detected_local_date] = by_day_count.get(d.detected_local_date, 0) + 1
        if first_utc is None or d.detected_at_utc < first_utc:
            first_utc = d.detected_at_utc
        if last_utc is None or d.detected_at_utc > last_utc:
            last_utc = d.detected_at_utc

    today_species = {_effective_name(d) for d in rows if d.detected_local_date == today_str}

    best_day = None
    if by_day_count:
        max_count = max(by_day_count.values())
        # Égalité → la plus récente (contrat §6.14).
        best_date = max(dt for dt, count in by_day_count.items() if count == max_count)
        best_day = {"date": best_date, "count": max_count}

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "date": today_str,
        "lifetime_species": len(species_seen),
        "lifetime_detections": len(rows),
        "today_detections": by_day_count.get(today_str, 0),
        "today_species": len(today_species),
        "best_day": best_day,
        "streak_days": _compute_streak(by_day_count, today_str),
        "first_detection_utc": first_utc,
        "last_detection_utc": last_utc,
    }


@router.get("/sites/{slug}/stats/daily")
def get_stats_daily(
    slug: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    site = get_site_or_404(db, slug)
    start_d, end_d = _resolve_range(site.timezone, start, end)
    rows = _effective_rows(db, site.id, start_d, end_d)

    by_day: dict[str, dict] = {}
    for d in rows:
        entry = by_day.setdefault(d.detected_local_date, {"total": 0, "species": set()})
        entry["total"] += 1
        entry["species"].add(_effective_name(d))

    days = []
    cursor = start_d
    while cursor <= end_d:
        key = cursor.isoformat()
        entry = by_day.get(key)
        days.append(
            {
                "date": key,
                "total": entry["total"] if entry else 0,
                "species_count": len(entry["species"]) if entry else 0,
            }
        )
        cursor += timedelta(days=1)

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "days": days,
    }


@router.get("/sites/{slug}/stats/hourly")
def get_stats_hourly(
    slug: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    start_d, end_d = _resolve_range(site.timezone, start, end)
    rows = _effective_rows(db, site.id, start_d, end_d)

    hour_totals = [0] * 24
    by_hour_species: list[dict[str, int]] = [{} for _ in range(24)]
    for d in rows:
        h = d.detected_local_hour
        hour_totals[h] += 1
        species_counts = by_hour_species[h]
        name = _effective_name(d)
        species_counts[name] = species_counts.get(name, 0) + 1

    hours = []
    for h in range(24):
        ranked = sorted(by_hour_species[h].items(), key=lambda kv: kv[0])
        ranked.sort(key=lambda kv: kv[1], reverse=True)
        species_list = [
            {"scientific_name": name, "common_name_fr": resolve_common_name_fr(name, store, db), "count": count}
            for name, count in ranked[:10]
        ]
        hours.append({"hour": h, "total": hour_totals[h], "species": species_list})

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "hours": hours,
    }


@router.get("/sites/{slug}/stats/species")
def get_stats_species(
    slug: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    start_d, end_d = _resolve_range(site.timezone, start, end)
    rows = _effective_rows(db, site.id, start_d, end_d)

    by_species: dict[str, dict] = {}
    for d in rows:
        name = _effective_name(d)
        entry = by_species.get(name)
        if entry is None:
            entry = {
                "total": 0,
                "days": set(),
                "max_confidence": 0.0,
                "sum_confidence": 0.0,
                "first_utc": d.detected_at_utc,
                "last_utc": d.detected_at_utc,
            }
            by_species[name] = entry
        entry["total"] += 1
        entry["days"].add(d.detected_local_date)
        entry["max_confidence"] = max(entry["max_confidence"], d.confidence)
        entry["sum_confidence"] += d.confidence
        entry["first_utc"] = min(entry["first_utc"], d.detected_at_utc)
        entry["last_utc"] = max(entry["last_utc"], d.detected_at_utc)

    ranked = sorted(by_species.items(), key=lambda kv: kv[0])
    ranked.sort(key=lambda kv: kv[1]["total"], reverse=True)

    species_out = [
        {
            "rank": rank,
            "scientific_name": name,
            "common_name_fr": resolve_common_name_fr(name, store, db),
            "total": entry["total"],
            "days_seen": len(entry["days"]),
            "max_confidence": round4(entry["max_confidence"]),
            "avg_confidence": round4(entry["sum_confidence"] / entry["total"]),
            "first_utc": entry["first_utc"],
            "last_utc": entry["last_utc"],
            "photo_url": photo_url_for(name, store),
        }
        for rank, (name, entry) in enumerate(ranked[:limit], start=1)
    ]

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "total_species": len(by_species),
        "species": species_out,
    }


@router.get("/sites/{slug}/stats/heatmap")
def get_stats_heatmap(
    slug: str,
    year: int | None = Query(default=None, ge=2000, le=2100),
    species: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    year_val = year or date.fromisoformat(today_local(site.timezone)).year
    if species is not None and len(species) > 40:
        raise ApiError(422, "validation_error", "40 espèces au maximum pour species=.")

    year_start = f"{year_val}-01-01"
    year_end = f"{year_val}-12-31"
    rows = (
        db.query(Detection)
        .filter(
            Detection.site_id == site.id,
            is_valid_detection_expr(),
            Detection.detected_local_date >= year_start,
            Detection.detected_local_date <= year_end,
        )
        .all()
    )
    impossible = impossible_names_for_site(db, site.id)

    weeks_by_species: dict[str, list[int]] = {}
    totals: dict[str, int] = {}
    for d in rows:
        name = _effective_name(d)
        if name in impossible:
            continue
        day_of_year = date.fromisoformat(d.detected_local_date).timetuple().tm_yday
        week_index = (day_of_year - 1) // 7  # 0..52 (contrat §1.4 : PAS la semaine ISO)
        weeks = weeks_by_species.setdefault(name, [0] * 53)
        weeks[week_index] += 1
        totals[name] = totals.get(name, 0) + 1

    if species:
        selected = [store.resolve_reference(raw) or raw.strip().replace("_", " ") for raw in species]
    else:
        ranked = sorted(totals.items(), key=lambda kv: kv[0])
        ranked.sort(key=lambda kv: kv[1], reverse=True)
        selected = [name for name, _ in ranked[:40]]

    species_out = [
        {
            "scientific_name": name,
            "common_name_fr": resolve_common_name_fr(name, store, db),
            "total": totals.get(name, 0),
            "weeks": weeks_by_species.get(name, [0] * 53),
        }
        for name in selected
    ]

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "year": year_val,
        "week_count": 53,
        "species": species_out,
    }


@router.get("/sites/{slug}/stats/confidence")
def get_stats_confidence(
    slug: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    species: str | None = Query(default=None),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    start_d, end_d = _resolve_range(site.timezone, start, end)

    canonical_species = None
    if species is not None:
        canonical_species = store.resolve_reference(species) or species.strip().replace("_", " ")

    rows = _effective_rows(db, site.id, start_d, end_d)
    buckets = [0] * 10
    total = 0
    for d in rows:
        if canonical_species is not None and _effective_name(d) != canonical_species:
            continue
        idx = min(int(d.confidence * 10), 9)
        buckets[idx] += 1
        total += 1

    return {
        "site_slug": site.slug,
        "timezone": site.timezone,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "species": canonical_species,
        "total": total,
        "buckets": [{"min": i / 10, "max": (i + 1) / 10, "count": buckets[i]} for i in range(10)],
    }
