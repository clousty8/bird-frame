"""Chemins de stockage des clips reçus — contrat §4.3 et §7.2 (`BIRDFRAME_DATA_DIR`)."""

from __future__ import annotations

from pathlib import Path

from app.species_data.naming import genre_espece, is_safe_scientific_name


def clip_paths(
    data_dir: Path, site_slug: str, scientific_name: str, kept_clip_id: int, ext: str
) -> tuple[Path, Path]:
    """`<data_dir>/clips/<site_slug>/<Genre_espece>/<kept_clip_id>.<ext>` + le `.png` voisin.

    `scientific_name` doit déjà avoir été validé à l'ingestion (`_validate_item`,
    contrat §4.2) contre `is_safe_scientific_name` : c'est le seul filtrage EN AMONT.
    Ce qui suit est une seconde ligne de défense (pas la seule) contre une traversée de
    répertoire / écriture hors de `data_dir` si jamais un nom non sûr atteignait quand
    même ce point (redirection, donnée déjà en base avant ce correctif…) — on refuse
    plutôt que d'écrire n'importe où sur le disque.
    """
    if not is_safe_scientific_name(scientific_name):
        raise ValueError(f"scientific_name non sûr pour un chemin de fichier : {scientific_name!r}")

    data_dir_resolved = data_dir.resolve()
    folder = (data_dir_resolved / "clips" / site_slug / genre_espece(scientific_name)).resolve()
    if not folder.is_relative_to(data_dir_resolved):
        raise ValueError(
            f"chemin de clip résolu hors de data_dir : site_slug={site_slug!r} "
            f"scientific_name={scientific_name!r} → {folder}"
        )

    folder.mkdir(parents=True, exist_ok=True)
    ext = ext if ext.startswith(".") else f".{ext}"
    audio_path = folder / f"{kept_clip_id}{ext}"
    png_path = folder / f"{kept_clip_id}.png"
    return audio_path, png_path


def looks_like_wav(content: bytes) -> bool:
    return len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WAVE"
