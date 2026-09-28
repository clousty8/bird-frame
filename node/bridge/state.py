"""État local du bridge : `BRIDGE_STATE_FILE` (api-contract.md §7.1).

Le curseur qui y est écrit est une **optimisation seulement** — le curseur canonique est
`synced_up_to_id` renvoyé par le serveur à chaque `/sync` (§3.1, §4.2). Ce module ne fait jamais
foi seul : `pusher.py` doit toujours adopter la valeur serveur, même si elle diffère de ce fichier.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BridgeState:
    cursor: int = 0
    updated_at: str | None = None


def load_state(path: Path) -> BridgeState:
    """Charge le curseur local. Fichier absent ou corrompu → curseur 0, sans jamais planter
    (le serveur redonnera de toute façon la valeur canonique au premier `/sync`)."""
    if not path.is_file():
        logger.info("Aucun fichier d'état à %s, curseur local initialisé à 0", path)
        return BridgeState(cursor=0, updated_at=None)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BridgeState(cursor=int(raw["cursor"]), updated_at=raw.get("updated_at"))
    except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        logger.warning(
            "Fichier d'état %s illisible ou corrompu (%s) : curseur local repris à 0, "
            "le serveur redonnera la valeur canonique au prochain /sync",
            path,
            exc,
        )
        return BridgeState(cursor=0, updated_at=None)


def save_state(path: Path, cursor: int) -> None:
    """Écriture atomique (fichier temporaire + renommage) après chaque `synced_up_to_id` adopté."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cursor": cursor, "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.error("Écriture de l'état %s impossible : %s", path, exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
