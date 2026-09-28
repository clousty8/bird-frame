"""Conventions de nommage `species-data/` et d'URL (contrat §1.6, §8.1)."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote


def genre_espece(scientific_name: str) -> str:
    """`Erithacus rubecula` → `Erithacus_rubecula` (nom de fichier / dossier)."""
    return scientific_name.strip().replace(" ", "_")


def species_from_genre_espece(genre_espece_str: str) -> str:
    """`Erithacus_rubecula` → `Erithacus rubecula`."""
    return genre_espece_str.replace("_", " ")


def quote_species_name(scientific_name: str) -> str:
    """Encodage d'URL d'un nom d'espèce — `urllib.parse.quote(name, safe="")` (contrat §1.6)."""
    return quote(scientific_name, safe="")


def fold(name: str) -> str:
    """Clé de comparaison insensible à la casse (mais PAS aux accents) pour la résolution
    de noms d'espèces — `.strip().casefold()`. Ne pas utiliser pour un tri alphabétique
    destiné à l'affichage (« Étourneau » doit trier avec les « E », pas après les « Z ») :
    voir `fold_diacritics` pour ce cas-là.
    """
    return name.strip().casefold()


def fold_diacritics(name: str) -> str:
    """Clé de tri/recherche insensible à la casse ET aux accents (NFKD + suppression des
    marques combinantes + casefold). Contrat §6.7/§6.12 : `sort=common_name` et la
    recherche `q=` doivent classer « Étourneau » avec les « E », pas après les « Z ».
    """
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


# Univers connu (species-data/) : lettres, chiffres, espaces, apostrophes et tirets
# (ex. BirdNET « Human non-vocal »). Aucun `/`, `\`, `.` — ce nom sert de segment de
# chemin de fichier (`clip_paths`, contrat §4.3) : un nom qui ne matche pas ce motif ne
# doit jamais atteindre le système de fichiers. Premier caractère forcé à une lettre
# (aucun nom d'espèce réel ne commence par un chiffre) : ça bloque aussi `..` et `.`.
_SAFE_SCIENTIFIC_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 '-]{0,199}$")


def is_safe_scientific_name(name: str) -> bool:
    """`True` si `name` ne peut pas servir à sortir du dossier de clips prévu (pas de
    `/`, `\\`, `..`, etc.) — à valider à l'ingestion, avant que le nom ne devienne un
    segment de chemin (contrat §4.2, §4.3)."""
    return bool(_SAFE_SCIENTIFIC_NAME_RE.match(name))
