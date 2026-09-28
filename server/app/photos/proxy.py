"""Proxy + cache disque des photos d'espèces — contrat §6.10.

Une seule source amont (`base.photo.url_1600`, sinon `url_original`), téléchargée au
plus une fois par espèce : les deux tailles (320 et « min(1600, largeur source) ») sont
produites et écrites ensemble au premier accès, quelle que soit la taille demandée.
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.errors import ApiError
from app.fsutil import write_atomic
from app.species_data.naming import genre_espece
from app.species_data.store import SpeciesDataStore
from app.time_utils import utc_now

logger = logging.getLogger("bird_frame.photos")

# Wikimedia bloque (403) les User-Agent trop génériques ou imitant un navigateur sans l'être
# (leur politique — meta.wikimedia.org/wiki/User-Agent_policy — décourage explicitement le
# "browser spoofing" et exige un identifiant d'outil + un contact). Constaté en pratique lors
# de l'intégration S1 (27/09/2026) : `httpx` avec un UA générique ou un UA calqué sur un vrai
# navigateur échoue de façon intermittente en 403, alors qu'un UA descriptif conforme à leur
# politique passe de façon fiable (10/10 sur upload.wikimedia.org, thumb et original).
USER_AGENT = "bird-frame/0.1 (projet personnel bird-frame; contact: armand.mounsi@gmail.com) httpx/0.28"
DOWNLOAD_TIMEOUT_S = 20.0
FAILURE_COOLDOWN_S = 600
SIZES = (320, 1600)


def get_photo_path(
    store: SpeciesDataStore,
    data_dir: Path,
    scientific_name: str,
    size: int,
    failures: dict[str, datetime],
) -> Path:
    base_entry = store.base.get(scientific_name)
    photo = (base_entry or {}).get("photo")
    source_url = (photo or {}).get("url_1600") or (photo or {}).get("url_original") if photo else None
    if not source_url:
        raise ApiError(404, "photo_not_found", f"Aucune photo pour {scientific_name!r}.")

    folder = data_dir / "photos" / genre_espece(scientific_name)
    target = folder / f"{size}.jpg"
    if target.is_file():
        return target

    last_failure = failures.get(scientific_name)
    if last_failure is not None and (utc_now() - last_failure).total_seconds() < FAILURE_COOLDOWN_S:
        raise ApiError(
            502,
            "photo_upstream_error",
            "Téléchargement de la photo déjà en échec récemment, nouvel essai différé.",
        )

    try:
        content = _download(source_url)
        image = Image.open(BytesIO(content))
        image.load()
        image = image.convert("RGB")
    except Exception as exc:  # réseau, décodage — jamais silencieux
        failures[scientific_name] = utc_now()
        logger.error("échec photo pour %s (%s) : %s", scientific_name, source_url, exc)
        raise ApiError(502, "photo_upstream_error", "Échec du téléchargement de la photo source.") from exc

    failures.pop(scientific_name, None)

    width_320 = 320
    width_1600 = min(1600, image.width)
    write_atomic(folder / "320.jpg", _resize_and_encode(image, width_320))
    write_atomic(folder / "1600.jpg", _resize_and_encode(image, width_1600))

    return target


def _download(url: str) -> bytes:
    with httpx.Client(timeout=DOWNLOAD_TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _resize_and_encode(image: Image.Image, target_width: int) -> bytes:
    resized = image
    if target_width != image.width and target_width > 0:
        ratio = target_width / image.width
        new_height = max(1, round(image.height * ratio))
        resized = image.resize((target_width, new_height), Image.LANCZOS)
    buf = BytesIO()
    # Pas d'`exif=` ni d'`icc_profile=` passés à save() : EXIF retiré, pas de profil
    # couleur exotique embarqué (équivaut à assumer sRGB), conforme au contrat §6.10.
    resized.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
