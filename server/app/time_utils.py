"""Dates, heures et fuseaux — contrat §1.3 et §1.4.

Règle centrale : tout instant stocké ou renvoyé au format texte est en UTC, secondes
entières, suffixe `Z` (`YYYY-MM-DDTHH:MM:SSZ`). Les agrégations « jour »/« heure » sont
toujours calculées dans le fuseau du site (`zoneinfo`), jamais en UTC ni dans celui du
serveur.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("bird_frame.time_utils")


def parse_utc_instant(raw: str) -> datetime:
    """Parse un instant ISO 8601 avec fuseau obligatoire, renvoie un datetime UTC aware.

    Accepte `Z` ou un décalage explicite (`+02:00`) en entrée (contrat §1.3). Un instant
    sans fuseau est un usage incorrect de l'appelant : lever ValueError (le point d'entrée
    Pydantic la transforme en 422 `validation_error`).
    """
    s = raw.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"instant invalide : {raw!r}") from exc
    if dt.tzinfo is None:
        raise ValueError(f"instant sans fuseau explicite (Z ou +HH:MM) : {raw!r}")
    return dt.astimezone(UTC)


def format_utc_instant(dt: datetime) -> str:
    """Formate un datetime (aware ou naïf-considéré-UTC) en chaîne canonique `...Z`."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def utc_now_str() -> str:
    return format_utc_instant(utc_now())


def parse_stored_utc(raw: str | None) -> datetime | None:
    """Relit un instant stocké tel qu'écrit par `format_utc_instant` (toujours `...Z`)."""
    if raw is None:
        return None
    return parse_utc_instant(raw)


def site_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        # Ne doit normalement jamais arriver (validé à l'enregistrement du site) ; on ne
        # masque pas l'erreur (on la journalise) mais on retombe sur Europe/Paris pour ne
        # pas planter une route de lecture à cause d'une donnée déjà en base.
        logger.error(
            "fuseau horaire invalide en base : %r — repli sur Europe/Paris (contrat §1.4).",
            tz_name,
        )
        return ZoneInfo("Europe/Paris")


def local_date_and_hour(dt_utc: datetime, tz_name: str) -> tuple[str, int]:
    """Date locale (`YYYY-MM-DD`) et heure murale (0-23) d'un instant UTC, dans le fuseau du site."""
    local = dt_utc.astimezone(site_zone(tz_name))
    return local.date().isoformat(), local.hour


def today_local(tz_name: str) -> str:
    return datetime.now(site_zone(tz_name)).date().isoformat()


def local_day_bounds_utc(local_date: str, tz_name: str) -> tuple[datetime, datetime]:
    """Bornes UTC `[début, fin)` de la journée locale `local_date` (semi-ouvert, §1.4)."""
    tz = site_zone(tz_name)
    y, m, d = (int(x) for x in local_date.split("-"))
    start_local = datetime(y, m, d, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def parse_local_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"date invalide : {raw!r} (attendu YYYY-MM-DD)") from exc


def round4(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def round1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def round_latlon(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
