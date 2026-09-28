"""CLI de vérification, sans réseau : imprime de vraies détections de `birdnet.db` (lecture
seule) pour prouver que WP-02 fonctionne, indépendamment du serveur.

    uv run python -m bridge.inspect --db <path> --since-id 0 --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys

from bridge.sqlite_reader import (
    SqliteReaderError,
    connect_readonly,
    fetch_detections_since,
    fetch_max_detection_id,
    fetch_predictions,
)
from bridge.time_utils import unix_to_instant_str


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m bridge.inspect", description=__doc__)
    parser.add_argument("--db", required=True, help="Chemin vers birdnet.db")
    parser.add_argument("--since-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        conn = connect_readonly(args.db)
    except SqliteReaderError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2

    try:
        max_id = fetch_max_detection_id(conn)
        rows = fetch_detections_since(conn, args.since_id, limit=args.limit)
        predictions = fetch_predictions(conn, [row.id for row in rows])

        print(f"# node_max_id (MAX(detections.id)) = {max_id}", file=sys.stderr)
        print(
            f"# {len(rows)} détection(s) depuis id > {args.since_id} (limite {args.limit})",
            file=sys.stderr,
        )
        for row in rows:
            print(
                json.dumps(
                    {
                        "node_local_id": row.id,
                        "detected_at_utc": unix_to_instant_str(row.detected_at),
                        "scientific_name": row.scientific_name,
                        "confidence": row.confidence,
                        "source_display_name": row.source_display_name,
                        "clip_name": row.clip_name,
                        "predictions": [
                            {"scientific_name": p.scientific_name, "confidence": p.confidence}
                            for p in predictions.get(row.id, [])
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
