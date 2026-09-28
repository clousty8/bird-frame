"""Présence locale d'une espèce sur un site, mois par mois (contrat §6.9, `local_presence`).

Source : `city_monthly_scores` de `species-data/` = probabilité d'observer l'espèce autour de
chacune des 18 villes de référence, pour chaque mois, d'après les observations naturalistes.
On prend la ville de référence la plus proche des coordonnées du site (distance du grand
cercle) et on traduit chaque probabilité en un niveau qualitatif, que le frontend affiche en
mots (jamais de pourcentage brut côté interface).

Seuils (score = probabilité 0-1 du mois ; bornes basses incluses) :

| Niveau          | Condition            |
|-----------------|----------------------|
| `tres_courant`  | score ≥ 0,50         |
| `courant`       | 0,20 ≤ score < 0,50  |
| `peu_frequent`  | 0,05 ≤ score < 0,20  |
| `rare`          | 0,01 ≤ score < 0,05  |
| `absent`        | score < 0,01         |

0,05 est aussi le seuil mensuel (`month_threshold`) que `build_universe.py` applique au score
national pour la liste `france_universe.months`.
"""

from __future__ import annotations

import math

from app.models.site import Site
from app.species_data.store import SpeciesDataStore
from app.time_utils import today_local

LEVEL_TRES_COURANT = "tres_courant"
LEVEL_COURANT = "courant"
LEVEL_PEU_FREQUENT = "peu_frequent"
LEVEL_RARE = "rare"
LEVEL_ABSENT = "absent"

# (niveau, borne basse incluse), du plus fréquent au moins fréquent.
LEVEL_THRESHOLDS: tuple[tuple[str, float], ...] = (
    (LEVEL_TRES_COURANT, 0.5),
    (LEVEL_COURANT, 0.2),
    (LEVEL_PEU_FREQUENT, 0.05),
    (LEVEL_RARE, 0.01),
)

_EARTH_RADIUS_KM = 6371.0088


def level_for_score(score: float) -> str:
    for level, lower_bound in LEVEL_THRESHOLDS:
        if score >= lower_bound:
            return level
    return LEVEL_ABSENT


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def nearest_reference_city(
    lat: float, lon: float, cities: dict[str, tuple[float, float]]
) -> tuple[str, float] | None:
    """Ville la plus proche et sa distance en km ; `None` si `cities` est vide. Égalité de
    distance départagée par le nom (résultat déterministe)."""
    best: tuple[float, str] | None = None
    for name, (city_lat, city_lon) in cities.items():
        candidate = (haversine_km(lat, lon, city_lat, city_lon), name)
        if best is None or candidate < best:
            best = candidate
    return None if best is None else (best[1], best[0])


def build_local_presence(store: SpeciesDataStore, scientific_name: str, site: Site) -> dict | None:
    """Bloc `local_presence` (§6.9) de `scientific_name` pour `site`, ou `None` si le site n'a
    pas de coordonnées ou si l'espèce n'a pas de scores mensuels par ville."""
    if site.lat is None or site.lon is None:
        return None
    scores_by_city = store.city_monthly_scores(scientific_name)
    candidates = {name: coords for name, coords in store.reference_cities.items() if name in scores_by_city}
    nearest = nearest_reference_city(site.lat, site.lon, candidates)
    if nearest is None:
        return None
    city, distance_km = nearest
    levels = [level_for_score(score) for score in scores_by_city[city]]
    current_month = int(today_local(site.timezone).split("-")[1])
    return {
        "site_slug": site.slug,
        "site_name": site.name,
        "reference_city": {"name": city, "distance_km": round(distance_km, 1)},
        "monthly_levels": levels,
        "current_month": current_month,
        "current_month_level": levels[current_month - 1],
    }
