"""Applique `species-data/aliases.json` aux données déjà ingérées (contrat §1.6/§7.3).

Usage (serveur ARRÊTÉ : le script écrit dans la même base SQLite) :

    cd server
    uv run python scripts/recanonicalize.py            # base et species-data de server/.env
    uv run python scripts/recanonicalize.py --dry-run  # compte sans rien écrire
    uv run python scripts/recanonicalize.py --db data/bird-frame.db --species-data ../species-data

Puis redémarrer le serveur (ou `POST /api/v1/admin/species-data/reload`) pour que les
nouvelles ingestions utilisent aussi les alias. Détail des effets :
`app/ingest/recanonicalize.py`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Lancé comme script (`python scripts/recanonicalize.py`) : rendre le package `app` importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.ingest.recanonicalize import (
    AliasConflictError,
    recanonicalize_existing,
    validate_aliases,
)
from app.main import run_migrations
from app.species_data.store import load_species_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", help="base SQLite du serveur (défaut : BIRDFRAME_DB_PATH)")
    parser.add_argument("--species-data", help="dossier species-data (défaut : BIRDFRAME_SPECIES_DATA_DIR)")
    parser.add_argument("--dry-run", action="store_true", help="compte les lignes concernées sans rien écrire")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    overrides = {}
    if args.db:
        overrides["db_path"] = str(Path(args.db).resolve())
    if args.species_data:
        overrides["species_data_dir"] = str(Path(args.species_data).resolve())
    settings: Settings = get_settings().model_copy(update=overrides)

    if not settings.db_path_resolved.is_file():
        print(f"Base introuvable : {settings.db_path_resolved}", file=sys.stderr)
        return 2
    store = load_species_data(settings.species_data_dir_resolved)
    aliases = store.aliases
    if not aliases:
        print("Aucun alias dans aliases.json : rien à faire.")
        return 0
    try:
        validate_aliases(aliases)
    except ValueError as exc:
        print(f"aliases.json invalide : {exc}", file=sys.stderr)
        return 2

    run_migrations(settings)
    engine = make_engine(settings)
    session = make_session_factory(engine)()
    try:
        if args.dry_run:
            print("--dry-run : aucune écriture. Lignes qui seraient renommées :")
            _print_counts(session, aliases)
            return 0
        report = recanonicalize_existing(session, aliases)
    except AliasConflictError as exc:
        session.rollback()
        print(f"Conflit, rien n'a été modifié : {exc}", file=sys.stderr)
        return 3
    finally:
        session.close()
        engine.dispose()

    print(f"Base : {settings.db_path_resolved}")
    print(f"Alias appliqués : {len(aliases)}")
    print(
        "Lignes renommées : "
        f"detections={report.detections} (nom brut conservé dans raw_scientific_name), "
        f"redirections={report.redirect_targets}, predictions={report.predictions}, "
        f"kept_clips={report.kept_clips}, regles={report.species_site_rules}, "
        f"faux_negatifs={report.false_negative_reports}, "
        f"species_names fusionnées={report.species_names_merged} renommées={report.species_names_renamed}"
    )
    for site_id, name in report.recomputed:
        print(f"Redirection + top-5 recalculés : site {site_id}, {name}")
    return 0


def _print_counts(session, aliases: dict[str, str]) -> None:
    from sqlalchemy import func

    from app.models.detection import Detection, Prediction
    from app.models.kept_clip import KeptClip

    for raw, canonical in sorted(aliases.items()):
        counts = {
            "detections": session.query(func.count(Detection.id)).filter(Detection.scientific_name == raw).scalar(),
            "predictions": session.query(func.count(Prediction.id)).filter(Prediction.scientific_name == raw).scalar(),
            "kept_clips": session.query(func.count(KeptClip.id)).filter(KeptClip.scientific_name == raw).scalar(),
        }
        if any(counts.values()):
            print(f"{raw} → {canonical} : {counts}")


if __name__ == "__main__":
    raise SystemExit(main())
