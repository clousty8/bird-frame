"""Écriture atomique d'un fichier (fichier temporaire + renommage) — évite un fichier
tronqué visible côté lecteur si le process est interrompu en cours d'écriture.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".part")
    tmp_path.write_bytes(content)
    os.replace(tmp_path, path)
