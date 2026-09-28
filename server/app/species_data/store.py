"""Chargement de `species-data/` en mémoire (WP-10) — univers France, `base/`, `sheets/`,
`aliases.json`, `reference_cities.json` (coordonnées des 18 villes de référence de l'univers,
pour la présence locale §6.9). La source de vérité reste toujours les fichiers versionnés ; ce module
produit un instantané immuable rechargé au démarrage et par `POST /admin/species-data/reload`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as jsonschema_validate

from app.species_data.naming import fold, species_from_genre_espece
from app.species_data.sheet_schema import SHEET_JSON_SCHEMA
from app.time_utils import round4, utc_now_str

logger = logging.getLogger("bird_frame.species_data")

_RARITY_WARNING_WORDS = ("rare", "exceptionnel", "accidentel")
_WORD_RE = re.compile(r"\S+")


@dataclass
class InvalidFile:
    file: str
    error: str

    def as_dict(self) -> dict:
        return {"file": self.file, "error": self.error}


@dataclass
class SpeciesDataStore:
    universe: dict[str, dict]
    base: dict[str, dict]
    sheets: dict[str, dict]
    aliases: dict[str, str]
    invalid_files: list[InvalidFile]
    loaded_at: str
    # Ville de référence → (lat, lon) ; vide si `reference_cities.json` est absent (la présence
    # locale §6.9 vaut alors `null` partout, avec un WARNING au chargement).
    reference_cities: dict[str, tuple[float, float]] = field(default_factory=dict)
    _lookup: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        lookup: dict[str, str] = {}
        for name in self.universe:
            lookup.setdefault(fold(name), name)
        for name in self.base:
            lookup.setdefault(fold(name), name)
        for name in self.sheets:
            lookup.setdefault(fold(name), name)
        for raw, canon in self.aliases.items():
            lookup.setdefault(fold(raw), canon)
            lookup.setdefault(fold(canon), canon)
        self._lookup = lookup

    @property
    def universe_count(self) -> int:
        return len(self.universe)

    @property
    def base_count(self) -> int:
        return len(self.base)

    @property
    def sheet_count(self) -> int:
        return len(self.sheets)

    @property
    def alias_count(self) -> int:
        return len(self.aliases)

    def resolve_reference(self, raw_name: str) -> str | None:
        """Résout un nom d'espèce (URL, alias, `_`/espace, casse) vers le nom canonique
        connu de `species-data/` (univers, base ou fiche). Ne regarde PAS la base
        `detections` : les routes qui doivent aussi trouver une espèce hors univers le
        font séparément (contrat §1.6/§6.9).
        """
        s = raw_name.strip().replace("_", " ")
        return self._lookup.get(fold(s))

    def common_name_fr(self, scientific_name: str) -> str | None:
        """Résolution §1.6, niveaux 1-2 uniquement (le niveau 3, cache bridge, est en base)."""
        base_entry = self.base.get(scientific_name)
        if base_entry and base_entry.get("common_name_fr"):
            return base_entry["common_name_fr"]
        universe_entry = self.universe.get(scientific_name)
        if universe_entry and universe_entry.get("common_name_fr"):
            return universe_entry["common_name_fr"]
        return None

    def has_photo(self, scientific_name: str) -> bool:
        photo = (self.base.get(scientific_name) or {}).get("photo")
        return bool(photo and (photo.get("url_1600") or photo.get("url_original")))

    def has_sheet(self, scientific_name: str) -> bool:
        return scientific_name in self.sheets

    def in_france_universe(self, scientific_name: str) -> bool:
        return scientific_name in self.universe

    def france_universe_view(self, scientific_name: str) -> dict | None:
        """`france_universe` pour `GET /species/{name}` — base d'abord, sinon univers brut
        arrondi, sinon `None` (contrat §8.4).
        """
        base_entry = self.base.get(scientific_name)
        if base_entry and base_entry.get("france_universe"):
            fu = base_entry["france_universe"]
            return {
                "max_score": round4(fu.get("max_score")),
                "cities": {k: round(v, 3) for k, v in (fu.get("cities") or {}).items()},
                "months": fu.get("months") or [],
            }
        universe_entry = self.universe.get(scientific_name)
        if universe_entry:
            return {
                "max_score": round4(universe_entry.get("max_score")),
                "cities": {k: round(v, 3) for k, v in (universe_entry.get("cities") or {}).items()},
                "months": universe_entry.get("months") or [],
            }
        return None

    def city_monthly_scores(self, scientific_name: str) -> dict[str, list[float]]:
        """Probabilité d'observer l'espèce, par ville de référence et par mois (12 valeurs
        0-1, index 0 = janvier) — `base.france_universe.city_monthly_scores`, sinon
        `cityMonthlyScores` de l'univers, sinon `{}`. Une ville dont la série n'a pas
        exactement 12 nombres dans [0, 1] est écartée (jamais de valeur inventée).
        """
        base_fu = (self.base.get(scientific_name) or {}).get("france_universe") or {}
        raw = base_fu.get("city_monthly_scores")
        if not raw:
            raw = (self.universe.get(scientific_name) or {}).get("city_monthly_scores")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[float]] = {}
        for city, series in raw.items():
            if isinstance(series, list) and len(series) == 12 and all(_is_probability(v) for v in series):
                result[str(city)] = [float(v) for v in series]
        return result


def _is_probability(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1


def _is_coordinate(value: object, bound: float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and -bound <= value <= bound


def load_species_data(species_data_dir: Path) -> SpeciesDataStore:
    invalid_files: list[InvalidFile] = []

    universe = _load_universe(species_data_dir, invalid_files)
    reference_cities = _load_reference_cities(species_data_dir, invalid_files)
    aliases = _load_aliases(species_data_dir, invalid_files)
    base = _load_base(species_data_dir, invalid_files)
    sheets = _load_sheets(species_data_dir, base, invalid_files)
    for raw, canonical in aliases.items():
        if canonical not in universe and canonical not in base:
            logger.warning(
                "aliases.json : %r pointe vers %r, absent de l'univers et de base/ (contrat §7.3)",
                raw,
                canonical,
            )

    store = SpeciesDataStore(
        universe=universe,
        base=base,
        sheets=sheets,
        aliases=aliases,
        invalid_files=invalid_files,
        loaded_at=utc_now_str(),
        reference_cities=reference_cities,
    )
    logger.info(
        "species-data chargé : univers=%d base=%d fiches=%d alias=%d villes=%d invalides=%d",
        store.universe_count,
        store.base_count,
        store.sheet_count,
        store.alias_count,
        len(reference_cities),
        len(invalid_files),
    )
    for inv in invalid_files:
        logger.warning("species-data ignoré : %s (%s)", inv.file, inv.error)
    return store


def _load_universe(species_data_dir: Path, invalid_files: list[InvalidFile]) -> dict[str, dict]:
    path = species_data_dir / "species_universe_fr.json"
    if not path.is_file():
        logger.warning("species_universe_fr.json absent de %s", species_data_dir)
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        invalid_files.append(InvalidFile("species_universe_fr.json", str(exc)))
        return {}
    universe: dict[str, dict] = {}
    for entry in raw:
        name = entry.get("scientificName")
        if not name:
            continue
        universe[name] = {
            "common_name_fr": entry.get("commonName"),
            "max_score": entry.get("maxScore"),
            "cities": entry.get("cities") or {},
            "months": entry.get("months") or [],
            "city_monthly_scores": entry.get("cityMonthlyScores") or {},
        }
    return universe


def _load_reference_cities(
    species_data_dir: Path, invalid_files: list[InvalidFile]
) -> dict[str, tuple[float, float]]:
    """`reference_cities.json` = `{ville: {lat, lon}}` (écrit par `build_universe.py`). Absent →
    `{}` avec un WARNING : la présence locale (§6.9) vaut alors `null` pour tous les sites."""
    path = species_data_dir / "reference_cities.json"
    if not path.is_file():
        logger.warning(
            "reference_cities.json absent de %s : la présence locale (local_presence) sera null partout",
            species_data_dir,
        )
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        invalid_files.append(InvalidFile("reference_cities.json", str(exc)))
        return {}
    if not isinstance(raw, dict):
        invalid_files.append(InvalidFile("reference_cities.json", "doit être un objet {ville: {lat, lon}}"))
        return {}
    cities: dict[str, tuple[float, float]] = {}
    for name, coords in raw.items():
        lat = coords.get("lat") if isinstance(coords, dict) else None
        lon = coords.get("lon") if isinstance(coords, dict) else None
        if not _is_coordinate(lat, 90) or not _is_coordinate(lon, 180):
            invalid_files.append(InvalidFile("reference_cities.json", f"coordonnées invalides pour {name!r}"))
            continue
        cities[str(name)] = (float(lat), float(lon))
    return cities


def _load_aliases(species_data_dir: Path, invalid_files: list[InvalidFile]) -> dict[str, str]:
    path = species_data_dir / "aliases.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        invalid_files.append(InvalidFile("aliases.json", str(exc)))
        return {}
    if not isinstance(raw, dict):
        invalid_files.append(InvalidFile("aliases.json", "doit être un objet plat {reçu: canonique}"))
        return {}
    aliases = {str(k): str(v) for k, v in raw.items()}
    # Contrat §7.3 : pas de chaîne (une valeur n'est jamais elle-même une clé) — sinon la
    # canonicalisation `aliases.get(nom, nom)` ne serait pas idempotente.
    valid: dict[str, str] = {}
    for received, canonical in aliases.items():
        if received == canonical or canonical in aliases:
            invalid_files.append(
                InvalidFile("aliases.json", f"alias {received!r} → {canonical!r} ignoré : chaîne ou boucle")
            )
            continue
        valid[received] = canonical
    return valid


def _load_base(species_data_dir: Path, invalid_files: list[InvalidFile]) -> dict[str, dict]:
    base_dir = species_data_dir / "base"
    base: dict[str, dict] = {}
    if not base_dir.is_dir():
        return base
    for file_path in sorted(base_dir.glob("*.json")):
        rel = f"base/{file_path.name}"
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            invalid_files.append(InvalidFile(rel, f"JSON invalide : {exc}"))
            continue
        expected_name = species_from_genre_espece(file_path.stem)
        declared_name = data.get("scientific_name")
        if declared_name != expected_name:
            invalid_files.append(
                InvalidFile(
                    rel,
                    f"scientific_name ({declared_name!r}) ne correspond pas au nom de fichier "
                    f"({expected_name!r})",
                )
            )
            continue
        base[declared_name] = data
    return base


def _load_sheets(
    species_data_dir: Path, base: dict[str, dict], invalid_files: list[InvalidFile]
) -> dict[str, dict]:
    sheets_dir = species_data_dir / "sheets"
    sheets: dict[str, dict] = {}
    if not sheets_dir.is_dir():
        return sheets
    for file_path in sorted(sheets_dir.glob("*.json")):
        rel = f"sheets/{file_path.name}"
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            invalid_files.append(InvalidFile(rel, f"JSON invalide : {exc}"))
            continue

        error = _validate_sheet(data, file_path.stem, base)
        if error:
            invalid_files.append(InvalidFile(rel, error))
            continue

        sheets[data["scientific_name"]] = data
    return sheets


def _validate_sheet(data: dict, file_stem: str, base: dict[str, dict]) -> str | None:
    """Retourne un message d'erreur si la fiche doit être rejetée, sinon `None` (avertit
    par `logger.warning` pour les anomalies tolérées, contrat §8.3 « Validation au chargement »).
    """
    try:
        jsonschema_validate(instance=data, schema=SHEET_JSON_SCHEMA)
    except JsonSchemaValidationError as exc:
        return f"schéma invalide : {exc.message}"

    expected_name = species_from_genre_espece(file_stem)
    if data["scientific_name"] != expected_name:
        return (
            f"scientific_name ({data['scientific_name']!r}) ne correspond pas au nom de "
            f"fichier ({expected_name!r})"
        )

    word_count = len(_WORD_RE.findall(data["summary_fr"]))
    if word_count < 80 or word_count > 260:
        return f"summary_fr : {word_count} mots (attendu 80 à 260)"
    if word_count < 120 or word_count > 200:
        logger.warning(
            "%s : summary_fr fait %d mots (cible 120-200, toléré 80-260)",
            data["scientific_name"],
            word_count,
        )

    base_entry = base.get(data["scientific_name"])
    if base_entry is None:
        logger.warning("%s : fiche sans base/ correspondante", data["scientific_name"])

    max_score = ((base_entry or {}).get("france_universe") or {}).get("max_score")
    rarity_note = (data.get("rarity_note") or "").casefold()
    if max_score is not None and max_score >= 0.5 and any(word in rarity_note for word in _RARITY_WARNING_WORDS):
        logger.warning(
            "%s : rarity_note évoque la rareté alors que france_universe.max_score=%.4f",
            data["scientific_name"],
            max_score,
        )

    return None
