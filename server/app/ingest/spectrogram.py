"""Génération du spectrogramme PNG d'un clip reçu — architecture.md §3.2 (amendé),
contrat §6.13 (« Contrat d'image pour le frontend »). Commande figée par le contrat, ne
JAMAIS diverger sans mettre à jour les deux en même temps.

Si `sox` est absent ou échoue, on logge une erreur claire et on continue sans image
(`spectrogram_path = NULL`) — jamais d'échec de l'upload à cause du spectrogramme seul.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("bird_frame.spectrogram")

_TIMEOUT_S = 30


def generate_spectrogram(sox_path: str, audio_path: Path, png_path: Path) -> bool:
    cmd = [
        sox_path,
        str(audio_path),
        "-n",
        "remix",
        "1",
        "rate",
        "24k",
        "spectrogram",
        "-r",
        "-x",
        "1000",
        "-y",
        "257",
        "-z",
        "90",
        "-o",
        str(png_path),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT_S, check=False)
    except FileNotFoundError:
        logger.error(
            "sox introuvable (%s) : spectrogramme non généré pour %s — clip servi sans image.",
            sox_path,
            audio_path,
        )
        return False
    except subprocess.TimeoutExpired:
        logger.error("sox a dépassé %ds pour %s : spectrogramme abandonné.", _TIMEOUT_S, audio_path)
        return False

    if completed.returncode != 0 or not png_path.is_file():
        logger.error(
            "sox a échoué (code %s) pour %s : %s",
            completed.returncode,
            audio_path,
            completed.stderr.decode("utf-8", "replace").strip(),
        )
        return False
    return True


def probe_duration_s(sox_path: str, audio_path: Path) -> float | None:
    """Durée du clip en secondes (`soxi -D`, ici via l'alias `sox --info`), `None` si
    indisponible (sox absent, fichier illisible) — ne bloque jamais l'upload.
    """
    try:
        completed = subprocess.run(
            [sox_path, "--info", "-D", str(audio_path)],
            capture_output=True,
            timeout=_TIMEOUT_S,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        logger.warning("sox introuvable (%s) : durée non sondée pour %s.", sox_path, audio_path)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("sox --info a dépassé %ds pour %s : durée non sondée.", _TIMEOUT_S, audio_path)
        return None
    if completed.returncode != 0:
        logger.warning(
            "sox --info a échoué (code %s) pour %s : %s",
            completed.returncode,
            audio_path,
            completed.stderr.strip(),
        )
        return None
    try:
        return round(float(completed.stdout.strip()), 3)
    except ValueError:
        logger.warning(
            "sortie de sox --info non numérique pour %s : %r", audio_path, completed.stdout.strip()
        )
        return None
