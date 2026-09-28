"""Routes `/species` — contrat §6.8 à §6.12."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.deps import get_db, get_photo_failures, get_settings_dep, get_species_data
from app.errors import ApiError
from app.ingest.valid_detection import is_valid_detection_expr
from app.live.compute import resolve_common_name_fr
from app.models.detection import Detection, Prediction
from app.models.kept_clip import KeptClip
from app.models.site import Site
from app.models.species_site_rule import SpeciesSiteRule
from app.photos.proxy import get_photo_path
from app.species_data.naming import fold_diacritics, quote_species_name
from app.species_data.store import SpeciesDataStore
from app.time_utils import round4, today_local

router = APIRouter(tags=["species"])


def resolve_species_name_or_404(db: Session, store: SpeciesDataStore, raw: str) -> str:
    resolved = store.resolve_reference(raw)
    if resolved:
        return resolved
    normalized = raw.strip().replace("_", " ")
    row = (
        db.query(Detection.scientific_name)
        .filter(func.lower(Detection.scientific_name) == normalized.casefold())
        .first()
    )
    if row:
        return row[0]
    raise ApiError(404, "species_not_found", f"Espèce inconnue : {raw!r}.")


def _photo_url(scientific_name: str, store: SpeciesDataStore) -> str | None:
    if not store.has_photo(scientific_name):
        return None
    return f"/api/v1/species/{quote_species_name(scientific_name)}/photo?size=320"


@router.get("/species")
def list_species(
    site: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    detected_only: bool = Query(default=False),
    sort: str = Query(default="common_name"),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    if sort not in ("common_name", "france_max_score", "detections"):
        raise ApiError(422, "validation_error", f"sort invalide : {sort!r}")

    site_row = get_site_or_404(db, site) if site else None

    universe_names = set(store.universe)
    detection_names = {
        row[0] for row in db.query(Detection.scientific_name).filter(is_valid_detection_expr()).distinct()
    }
    all_names = universe_names | detection_names

    counts_by_species: dict[str, dict[str, int]] = {}
    for name, slug, count in (
        db.query(Detection.scientific_name, Site.slug, func.count(Detection.id))
        .join(Site, Site.id == Detection.site_id)
        .filter(is_valid_detection_expr())
        .group_by(Detection.scientific_name, Site.slug)
        .all()
    ):
        counts_by_species.setdefault(name, {})[slug] = count

    entries = []
    for name in all_names:
        per_site = counts_by_species.get(name, {})
        total_detections = sum(per_site.values())
        site_total = per_site.get(site_row.slug, 0) if site_row else None
        common_name = resolve_common_name_fr(name, store, db)
        base_entry = store.base.get(name)
        taxonomy = base_entry.get("taxonomy") if base_entry else None

        if detected_only:
            effective_count = site_total if site_row else total_detections
            if not effective_count:
                continue

        if q:
            haystack = f"{common_name or ''} {name}"
            if fold_diacritics(q) not in fold_diacritics(haystack):
                continue

        entries.append(
            {
                "scientific_name": name,
                "common_name_fr": common_name,
                "order": (taxonomy or {}).get("order"),
                "family": (taxonomy or {}).get("family"),
                "in_france_universe": name in universe_names,
                "france_max_score": (store.france_universe_view(name) or {}).get("max_score"),
                "detected_sites": sorted(per_site.keys()),
                "total_detections": total_detections,
                "site_total": site_total,
                "photo_url": _photo_url(name, store),
                "has_sheet": store.has_sheet(name),
            }
        )

    entries.sort(key=lambda e: e["scientific_name"])
    if sort == "france_max_score":
        entries.sort(key=lambda e: (e["france_max_score"] is None, -(e["france_max_score"] or 0)))
    elif sort == "detections":
        entries.sort(key=lambda e: (e["site_total"] if site_row else e["total_detections"]), reverse=True)
    else:
        entries.sort(key=lambda e: fold_diacritics(e["common_name_fr"] or e["scientific_name"]))

    total = len(entries)
    page = entries[offset : offset + limit]
    return {"species": page, "total": total, "limit": limit, "offset": offset}


@router.get("/species/{scientific_name}")
def get_species_detail(
    scientific_name: str,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    canonical = resolve_species_name_or_404(db, store, scientific_name)
    base_entry = store.base.get(canonical)
    sheet_entry = store.sheets.get(canonical)

    aliases = [raw for raw, canon in store.aliases.items() if canon == canonical]

    taxonomy = base_entry.get("taxonomy") if base_entry else None

    photo = None
    base_photo = (base_entry or {}).get("photo")
    if base_photo and (base_photo.get("url_1600") or base_photo.get("url_original")):
        quoted = quote_species_name(canonical)
        photo = {
            "url": f"/api/v1/species/{quoted}/photo?size=320",
            "url_1600": f"/api/v1/species/{quoted}/photo?size=1600",
            "width": base_photo.get("width"),
            "height": base_photo.get("height"),
            "license": base_photo.get("license"),
            "license_url": base_photo.get("license_url"),
            "author": base_photo.get("author"),
            "credit": base_photo.get("credit"),
            "description_url": base_photo.get("description_url"),
        }

    wiki_raw = (base_entry or {}).get("wikipedia") or {}
    wikipedia = {"fr": _wiki_ref(wiki_raw.get("fr")), "en": _wiki_ref(wiki_raw.get("en"))}

    has_sheet = sheet_entry is not None
    if sheet_entry:
        migration = {
            "statut": sheet_entry["migration"]["statut"],
            "hiverne": sheet_entry["migration"]["hiverne"],
            "niche": sheet_entry["migration"]["niche"],
            "passage": sheet_entry["migration"]["passage"],
        }
        lookalikes = [
            {
                "scientific_name": lk["scientific_name"],
                "common_name_fr": resolve_common_name_fr(lk["scientific_name"], store, db),
                "why_fr": lk["why_fr"],
            }
            for lk in sheet_entry.get("lookalikes", [])
        ]
        sheet_fields = {
            "summary_fr": sheet_entry["summary_fr"],
            "habitat": sheet_entry["habitat"],
            "diet": sheet_entry["diet"],
            "activity_pattern": sheet_entry["activity_pattern"],
            "migration": migration,
            "seasonality_fr": sheet_entry["seasonality_fr"],
            "song_fr": sheet_entry["song_fr"],
            "lookalikes": lookalikes,
            "rarity_note": sheet_entry["rarity_note"],
            "fun_facts": sheet_entry.get("fun_facts", []),
            "sources": sheet_entry.get("sources", []),
            "generated_at": sheet_entry.get("generated_at"),
            "generator_model": sheet_entry.get("generator_model"),
            "reviewed_by_human": bool(sheet_entry.get("reviewed_by_human", False)),
        }
    else:
        sheet_fields = {
            "summary_fr": None,
            "habitat": None,
            "diet": None,
            "activity_pattern": None,
            "migration": None,
            "seasonality_fr": None,
            "song_fr": None,
            "lookalikes": [],
            "rarity_note": None,
            "fun_facts": [],
            "sources": [],
            "generated_at": None,
            "generator_model": None,
            "reviewed_by_human": False,
        }

    return {
        "scientific_name": canonical,
        "aliases": aliases,
        "common_name_fr": resolve_common_name_fr(canonical, store, db),
        "in_france_universe": store.in_france_universe(canonical),
        "taxonomy": taxonomy,
        "photo": photo,
        "wikipedia": wikipedia,
        "has_sheet": has_sheet,
        **sheet_fields,
        "france_universe": store.france_universe_view(canonical),
        "presence_by_site": _presence_by_site(db, canonical),
    }


def _wiki_ref(raw: dict | None) -> dict | None:
    if not raw or not raw.get("title"):
        return None
    return {
        "title": raw.get("title"),
        "url": raw.get("url"),
        "description": raw.get("description"),
        "extract": raw.get("extract"),
    }


def _presence_by_site(db: Session, canonical: str) -> list[dict]:
    by_site: dict[int, dict] = {}
    for d in db.query(Detection).filter(Detection.scientific_name == canonical, is_valid_detection_expr()).all():
        entry = by_site.get(d.site_id)
        if entry is None:
            entry = {
                "total": 0,
                "max_confidence": 0.0,
                "first_seen_utc": d.detected_at_utc,
                "last_seen_utc": d.detected_at_utc,
                "days": set(),
                "months": [0] * 12,
            }
            by_site[d.site_id] = entry
        entry["total"] += 1
        entry["max_confidence"] = max(entry["max_confidence"], d.confidence)
        entry["first_seen_utc"] = min(entry["first_seen_utc"], d.detected_at_utc)
        entry["last_seen_utc"] = max(entry["last_seen_utc"], d.detected_at_utc)
        entry["days"].add(d.detected_local_date)
        entry["months"][int(d.detected_local_date.split("-")[1]) - 1] += 1

    rule_by_site = {
        r.site_id: r for r in db.query(SpeciesSiteRule).filter(SpeciesSiteRule.scientific_name == canonical)
    }

    site_ids = set(by_site) | set(rule_by_site)
    if not site_ids:
        return []
    sites_by_id = {s.id: s for s in db.query(Site).filter(Site.id.in_(site_ids)).all()}

    result = []
    for site_id in site_ids:
        site_row = sites_by_id[site_id]
        rule = rule_by_site.get(site_id)
        entry = by_site.get(site_id)
        result.append(
            {
                "site_slug": site_row.slug,
                "site_name": site_row.name,
                "total": entry["total"] if entry else 0,
                "first_seen_utc": entry["first_seen_utc"] if entry else None,
                "last_seen_utc": entry["last_seen_utc"] if entry else None,
                "days_seen": len(entry["days"]) if entry else 0,
                "max_confidence": round4(entry["max_confidence"]) if entry else None,
                "months": entry["months"] if entry else [0] * 12,
                "rule": rule.rule if rule else None,
                "redirect_to_scientific_name": (
                    rule.redirect_to_scientific_name if rule and rule.rule == "redirect" else None
                ),
            }
        )
    result.sort(key=lambda p: p["site_slug"])
    result.sort(key=lambda p: p["total"], reverse=True)
    return result


@router.get("/species/{scientific_name}/photo")
def get_species_photo(
    scientific_name: str,
    size: int = Query(default=320),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
    app_settings=Depends(get_settings_dep),
    failures: dict = Depends(get_photo_failures),
) -> Response:
    if size not in (320, 1600):
        raise ApiError(422, "validation_error", "size doit être 320 ou 1600.")
    canonical = store.resolve_reference(scientific_name) or scientific_name.strip().replace("_", " ")
    # get_photo_path() ajoute lui-même le segment "photos/" (contrat §6.10 :
    # <BIRDFRAME_DATA_DIR>/photos/<Genre_espece>/<size>.jpg) : il faut donc lui passer
    # data_dir_resolved (la racine), pas photos_dir_resolved (déjà .../data/photos) — sinon les
    # fichiers finissent sous data/photos/photos/... (bug constaté et corrigé le 27/09/2026 lors
    # de l'intégration S1).
    path = get_photo_path(store, app_settings.data_dir_resolved, canonical, size, failures)
    return Response(
        content=path.read_bytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@router.get("/species/{scientific_name}/sites/{slug}/top-clips")
def get_top_clips(
    scientific_name: str,
    slug: str,
    include_missing: bool = Query(default=False),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    canonical = store.resolve_reference(scientific_name) or scientific_name.strip().replace("_", " ")

    active_rows = (
        db.query(KeptClip)
        .filter(
            KeptClip.site_id == site.id,
            KeptClip.scientific_name == canonical,
            KeptClip.evicted_at.is_(None),
            KeptClip.missing.is_(False),
        )
        .order_by(KeptClip.rank_in_site_species.asc())
        .all()
    )
    clips = [_build_clip_entry(db, store, kc, missing=False) for kc in active_rows]

    if include_missing:
        missing_rows = (
            db.query(KeptClip)
            .filter(KeptClip.site_id == site.id, KeptClip.scientific_name == canonical, KeptClip.missing.is_(True))
            .order_by(KeptClip.id.desc())
            .limit(5)
            .all()
        )
        clips.extend(_build_clip_entry(db, store, kc, missing=True) for kc in missing_rows)

    return {"site_slug": site.slug, "scientific_name": canonical, "clips": clips}


def _build_clip_entry(db: Session, store: SpeciesDataStore, kc: KeptClip, missing: bool) -> dict:
    detection = db.get(Detection, kc.detection_id)
    audio_ok = bool(kc.audio_path) and Path(kc.audio_path).is_file()
    spectro_ok = bool(kc.spectrogram_path) and Path(kc.spectrogram_path).is_file()
    review_kind = _current_review_kind(db, detection.id)
    return {
        "kept_clip_id": kc.id,
        "detection_id": kc.detection_id,
        "detected_at_utc": detection.detected_at_utc,
        "confidence": round4(detection.confidence),
        "rank": None if missing else kc.rank_in_site_species,
        "audio_available": audio_ok,
        "audio_url": f"/api/v1/recordings/{kc.id}/audio" if audio_ok else None,
        "spectrogram_url": f"/api/v1/recordings/{kc.id}/spectrogram" if spectro_ok else None,
        "duration_s": kc.duration_s,
        "review": review_kind if review_kind == "correct" else None,
        "missing": missing,
        "predictions": _build_predictions(db, store, detection),
    }


def _current_review_kind(db: Session, detection_id: int) -> str | None:
    from app.models.review import Review

    row = (
        db.query(Review.kind)
        .filter(Review.detection_id == detection_id)
        .order_by(Review.id.desc())
        .first()
    )
    return row[0] if row else None


def _build_predictions(db: Session, store: SpeciesDataStore, detection: Detection) -> list[dict]:
    result = [
        {
            "scientific_name": detection.scientific_name,
            "common_name_fr": resolve_common_name_fr(detection.scientific_name, store, db),
            "confidence": round4(detection.confidence),
            "is_primary": True,
        }
    ]
    secondaries = (
        db.query(Prediction)
        .filter(Prediction.detection_id == detection.id)
        .order_by(Prediction.confidence.desc())
        .all()
    )
    for p in secondaries:
        result.append(
            {
                "scientific_name": p.scientific_name,
                "common_name_fr": resolve_common_name_fr(p.scientific_name, store, db),
                "confidence": round4(p.confidence),
                "is_primary": False,
            }
        )
    return result


@router.get("/species/{scientific_name}/presence")
def get_species_presence(
    scientific_name: str,
    site: str | None = Query(default=None),
    include_by_day: bool = Query(default=False),
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    canonical = resolve_species_name_or_404(db, store, scientific_name)
    site_row = get_site_or_404(db, site) if site else None
    tz_name = site_row.timezone if site_row else "Europe/Paris"

    query = db.query(Detection).filter(Detection.scientific_name == canonical, is_valid_detection_expr())
    if site_row:
        query = query.filter(Detection.site_id == site_row.id)
    rows = query.all()

    months = [0] * 12
    hours = [0] * 24
    first_seen: str | None = None
    last_seen: str | None = None
    day_counts: dict[str, int] = {}
    for d in rows:
        months[int(d.detected_local_date.split("-")[1]) - 1] += 1
        hours[d.detected_local_hour] += 1
        first_seen = d.detected_at_utc if first_seen is None else min(first_seen, d.detected_at_utc)
        last_seen = d.detected_at_utc if last_seen is None else max(last_seen, d.detected_at_utc)
        day_counts[d.detected_local_date] = day_counts.get(d.detected_local_date, 0) + 1

    by_day = None
    if include_by_day:
        today = date.fromisoformat(today_local(tz_name))
        by_day = [
            {"date": (today - timedelta(days=offset)).isoformat(), "count": day_counts.get((today - timedelta(days=offset)).isoformat(), 0)}
            for offset in range(364, -1, -1)
        ]

    return {
        "scientific_name": canonical,
        "site_slug": site_row.slug if site_row else None,
        "total": len(rows),
        "first_seen_utc": first_seen,
        "last_seen_utc": last_seen,
        "months": months,
        "hours": hours,
        "by_day": by_day,
    }
