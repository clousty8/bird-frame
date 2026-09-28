"""Lecture de `birdnet.db` en lecture seule (WP-02, architecture.md §3.1).

Ouvre toujours la base en `mode=ro` (URI SQLite) : aucune requête d'écriture n'est possible via
ce module, même par erreur — `PRAGMA query_only = ON` l'impose une seconde fois au niveau de la
connexion elle-même, en plus du mode d'ouverture du fichier.

Schéma réel de BirdNET-Go (v2-only, vérifié contre local-test/data/birdnet.db) :
  detections(id, model_id, label_id, source_id, detected_at [unix seconds], confidence,
             clip_name, ...)
  labels(id, scientific_name, model_id, ...)
  detection_predictions(id, detection_id, label_id, confidence, rank)  -- rank vaut 1 partout
             sur le chemin d'écriture v2-only actif : ne jamais trier dessus.
  audio_sources(id, source_uri, node_name, source_type, display_name, ...)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


class SqliteReaderError(Exception):
    """La base `birdnet.db` n'a pas pu être ouverte ou interrogée."""


@dataclass(frozen=True)
class PredictionRow:
    scientific_name: str
    confidence: float


@dataclass(frozen=True)
class DetectionRow:
    id: int
    detected_at: int  # unix seconds, brut (conversion en instant UTC laissée à l'appelant)
    confidence: float
    clip_name: str | None
    source_id: int | None
    scientific_name: str
    source_display_name: str | None


def connect_readonly(path: str) -> sqlite3.Connection:
    """Ouvre `birdnet.db` en lecture seule stricte (`file:...?mode=ro`, `uri=True`).

    Ne bloque jamais un binaire BirdNET-Go qui écrit en parallèle (mode WAL) : c'est le même
    schéma d'accès que `local-test/clip-retention.py`, déjà en production sans incident.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        raise SqliteReaderError(f"Impossible d'ouvrir {path} en lecture seule : {exc}") from exc
    conn.execute("PRAGMA query_only = ON;")
    conn.row_factory = sqlite3.Row
    return conn


_DETECTIONS_SINCE_SQL = """
SELECT d.id, d.detected_at, d.confidence, d.clip_name, d.source_id,
       l.scientific_name, s.display_name AS source_display_name
FROM detections d
JOIN labels l ON l.id = d.label_id
LEFT JOIN audio_sources s ON s.id = d.source_id
WHERE d.id > :since_id
ORDER BY d.id ASC
LIMIT :limit;
"""


def fetch_detections_since(conn: sqlite3.Connection, since_id: int, limit: int = 200) -> list[DetectionRow]:
    """Requête exacte d'architecture.md §3.1 / plan.md WP-02."""
    try:
        rows = conn.execute(_DETECTIONS_SINCE_SQL, {"since_id": since_id, "limit": limit}).fetchall()
    except sqlite3.DatabaseError as exc:
        raise SqliteReaderError(f"Échec de lecture des détections depuis id={since_id} : {exc}") from exc
    return [
        DetectionRow(
            id=row["id"],
            detected_at=row["detected_at"],
            confidence=row["confidence"],
            clip_name=row["clip_name"],
            source_id=row["source_id"],
            scientific_name=row["scientific_name"],
            source_display_name=row["source_display_name"],
        )
        for row in rows
    ]


def fetch_predictions(conn: sqlite3.Connection, detection_ids: list[int]) -> dict[int, list[PredictionRow]]:
    """Prédictions triées par confiance décroissante — **jamais** `ORDER BY rank`
    (colonne toujours =1 sur le chemin d'écriture v2-only, cf. architecture.md §3.1)."""
    if not detection_ids:
        return {}
    placeholders = ",".join("?" for _ in detection_ids)
    sql = f"""
        SELECT p.detection_id, l.scientific_name, p.confidence
        FROM detection_predictions p
        JOIN labels l ON l.id = p.label_id
        WHERE p.detection_id IN ({placeholders})
        ORDER BY p.detection_id ASC, p.confidence DESC;
    """
    try:
        rows = conn.execute(sql, detection_ids).fetchall()
    except sqlite3.DatabaseError as exc:
        raise SqliteReaderError(f"Échec de lecture des prédictions : {exc}") from exc
    result: dict[int, list[PredictionRow]] = {}
    for row in rows:
        result.setdefault(row["detection_id"], []).append(
            PredictionRow(scientific_name=row["scientific_name"], confidence=row["confidence"])
        )
    return result


def fetch_max_detection_id(conn: sqlite3.Connection) -> int:
    """`node_max_id` du protocole de sync (§4.2) — aussi utilisé par le heartbeat."""
    try:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM detections;").fetchone()
    except sqlite3.DatabaseError as exc:
        raise SqliteReaderError(f"Échec de lecture du max id des détections : {exc}") from exc
    return int(row["max_id"])


def fetch_clip_name(conn: sqlite3.Connection, detection_id: int) -> str | None:
    """`clip_name` d'une détection donnée (utilisé lors de l'upload d'un clip demandé, §4.3)."""
    row = conn.execute("SELECT clip_name FROM detections WHERE id = :id;", {"id": detection_id}).fetchone()
    if row is None:
        return None
    return row["clip_name"]
