"""Fixtures communes aux tests du bridge. Aucune ne touche jamais `local-test/`."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

_SCHEMA = """
CREATE TABLE labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL,
    model_id INTEGER NOT NULL
);
CREATE TABLE audio_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_uri TEXT NOT NULL,
    node_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    display_name TEXT
);
CREATE TABLE detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL,
    source_id INTEGER,
    detected_at INTEGER NOT NULL,
    confidence REAL NOT NULL,
    clip_name TEXT
);
CREATE TABLE detection_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL,
    confidence REAL NOT NULL,
    rank INTEGER NOT NULL DEFAULT 1
);
"""


@pytest.fixture
def seeded_db_path(tmp_path: Path) -> Path:
    """Reproduit, en miniature, le schéma réel de `birdnet.db` (detections/labels/
    detection_predictions/audio_sources) — jamais `local-test/`, toujours un fichier temporaire.
    Toutes les prédictions ont `rank=1` (comme la vraie base), pour vérifier que le tri se fait
    bien par `confidence` et jamais par `rank`."""
    db_path = tmp_path / "birdnet-test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)

    conn.execute(
        "INSERT INTO audio_sources (id, source_uri, node_name, source_type, display_name) "
        "VALUES (1, 'HyperX QuadCast', 'BirdNET-Go', 'unknown', 'Sound Card 1')"
    )

    labels = [
        (1, "Erithacus rubecula"),
        (2, "Turdus merula"),
        (3, "Parus major"),
        (4, "Columba palumbus"),
    ]
    conn.executemany("INSERT INTO labels (id, scientific_name, model_id) VALUES (?, ?, 1)", labels)

    detections = [
        # id, label_id, source_id, detected_at, confidence, clip_name
        (10, 1, 1, 1_790_000_000, 0.98, "2026/09/erithacus_rubecula_98p.wav"),
        (11, 2, 1, 1_790_000_100, 0.91, "2026/09/turdus_merula_91p.wav"),
        (12, 3, 1, 1_790_000_200, 0.72, None),
    ]
    conn.executemany(
        "INSERT INTO detections (id, label_id, source_id, detected_at, confidence, clip_name, model_id) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        detections,
    )

    # Prédictions de la détection 10 : toutes rank=1 (comme la vraie base), doit trier par confidence.
    predictions = [
        (10, 2, 0.05),  # Turdus merula, plus faible
        (10, 4, 0.12),  # Columba palumbus, la plus forte des secondaires
        (10, 1, 0.98),  # Erithacus rubecula = la primaire elle-même (doit être filtrée par pusher.py)
    ]
    conn.executemany(
        "INSERT INTO detection_predictions (detection_id, label_id, confidence, rank) VALUES (?, ?, ?, 1)",
        predictions,
    )
    conn.commit()
    conn.close()
    return db_path
