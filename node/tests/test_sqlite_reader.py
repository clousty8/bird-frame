"""WP-02 : lecture seule de birdnet.db, tri des prédictions par confiance (jamais par rank)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bridge.sqlite_reader import (
    SqliteReaderError,
    connect_readonly,
    fetch_clip_name,
    fetch_detections_since,
    fetch_max_detection_id,
    fetch_predictions,
)


def test_connect_readonly_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(SqliteReaderError):
        connect_readonly(str(tmp_path / "does-not-exist.db"))


def test_connect_readonly_rejects_writes(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        with pytest.raises(sqlite3.OperationalError):  # "attempt to write a readonly database"
            conn.execute("DELETE FROM detections")
            conn.commit()
    finally:
        conn.close()


def test_fetch_detections_since_orders_by_id_and_resolves_names(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        rows = fetch_detections_since(conn, since_id=0, limit=200)
    finally:
        conn.close()

    assert [row.id for row in rows] == [10, 11, 12]
    first = rows[0]
    assert first.scientific_name == "Erithacus rubecula"
    assert first.confidence == pytest.approx(0.98)
    assert first.clip_name == "2026/09/erithacus_rubecula_98p.wav"
    assert first.source_id == 1
    assert first.source_display_name == "Sound Card 1"

    # LEFT JOIN audio_sources : une détection sans clip garde quand même ses champs à null.
    third = rows[2]
    assert third.clip_name is None


def test_fetch_detections_since_respects_cursor_and_limit(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        rows = fetch_detections_since(conn, since_id=10, limit=1)
    finally:
        conn.close()
    assert [row.id for row in rows] == [11]


def test_fetch_predictions_orders_by_confidence_not_rank(seeded_db_path: Path) -> None:
    """Toutes les prédictions du fixture ont rank=1 (comme la vraie base) : si le tri se faisait
    par rank, l'ordre serait indéterminé/faux. Il doit être par confidence décroissante."""
    conn = connect_readonly(str(seeded_db_path))
    try:
        predictions = fetch_predictions(conn, [10])
    finally:
        conn.close()

    names_in_order = [p.scientific_name for p in predictions[10]]
    assert names_in_order == ["Erithacus rubecula", "Columba palumbus", "Turdus merula"]
    confidences = [p.confidence for p in predictions[10]]
    assert confidences == sorted(confidences, reverse=True)


def test_fetch_predictions_empty_ids_returns_empty_dict(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        assert fetch_predictions(conn, []) == {}
    finally:
        conn.close()


def test_fetch_max_detection_id(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        assert fetch_max_detection_id(conn) == 12
    finally:
        conn.close()


def test_fetch_max_detection_id_wraps_sqlite_errors(seeded_db_path: Path) -> None:
    """Comme `fetch_detections_since` et `fetch_predictions` : un `sqlite3.DatabaseError` brut ne
    doit jamais s'échapper de ce module — les appelants (`pusher.sync_once`,
    `heartbeat.build_heartbeat_payload`) ne savent traiter que `SqliteReaderError`."""
    conn = connect_readonly(str(seeded_db_path))
    conn.close()
    with pytest.raises(SqliteReaderError):
        fetch_max_detection_id(conn)


def test_fetch_clip_name(seeded_db_path: Path) -> None:
    conn = connect_readonly(str(seeded_db_path))
    try:
        assert fetch_clip_name(conn, 10) == "2026/09/erithacus_rubecula_98p.wav"
        assert fetch_clip_name(conn, 12) is None  # détection sans clip
        assert fetch_clip_name(conn, 9999) is None  # détection inconnue
    finally:
        conn.close()


def test_mtime_unchanged_after_reads(seeded_db_path: Path) -> None:
    """Preuve que la lecture seule ne modifie jamais le fichier (même garantie que pour
    local-test/data/birdnet.db en conditions réelles)."""
    mtime_before = seeded_db_path.stat().st_mtime_ns
    conn = connect_readonly(str(seeded_db_path))
    try:
        fetch_detections_since(conn, 0, limit=200)
        fetch_max_detection_id(conn)
    finally:
        conn.close()
    assert seeded_db_path.stat().st_mtime_ns == mtime_before
