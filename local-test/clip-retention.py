#!/usr/bin/env python3
"""Ne garde l'audio (clip .wav + spectrogrammes .png) que des 10 meilleures détections de chaque espèce.

Les détections restent toutes en base (les statistiques restent justes) : on vide seulement leur
champ clip_name, exactement comme le fait le nettoyage intégré de BirdNET-Go, puis on efface les
fichiers. Les détections verrouillées dans l'interface gardent toujours leur audio.

Supprime aussi les clips « orphelins » (sans détection en base, ex. doublons écartés par BirdNET-Go).

Usage :
    ./clip-retention.py --dry-run      affiche ce qui serait supprimé, ne touche à rien
    ./clip-retention.py                un passage
    ./clip-retention.py --loop 600     un passage toutes les 10 min (lancé par start.sh)
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB = DATA / "birdnet.db"
CLIPS = DATA / "clips"  # realtime.audio.export.path, relatif au dossier data/

TOP_N = 10
# On ne touche pas aux détections et fichiers récents : le clip peut être encore en cours d'écriture,
# ou la détection pas encore enregistrée en base.
MIN_AGE_S = 30 * 60

TO_STRIP = """
WITH ranked AS (
    SELECT id, clip_name, detected_at,
           ROW_NUMBER() OVER (PARTITION BY label_id ORDER BY confidence DESC, id ASC) AS rk
    FROM detections
)
SELECT r.id, r.clip_name FROM ranked r
WHERE r.rk > ? AND r.clip_name IS NOT NULL AND r.clip_name != ''
  AND r.detected_at < ?
  AND NOT EXISTS (SELECT 1 FROM detection_locks l WHERE l.detection_id = r.id)
"""


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def clip_path(clip_name):
    name = clip_name.removeprefix("clips/")
    p = (CLIPS / name).resolve()
    return p if p.is_relative_to(CLIPS.resolve()) else None


def files_for(wav):
    """Le .wav et tous ses spectrogrammes (<nom>_<largeur>px*.png)."""
    return [wav] + sorted(wav.parent.glob(f"{wav.stem}_*px*.png"))


def remove(paths, dry_run):
    freed = 0
    for p in paths:
        try:
            size = p.stat().st_size
            if not dry_run:
                p.unlink()
            freed += size
        except FileNotFoundError:
            pass
    return freed


def run_once(dry_run):
    now = time.time()
    con = sqlite3.connect(DB, timeout=30)
    try:
        rows = con.execute(TO_STRIP, (TOP_N, int(now - MIN_AGE_S))).fetchall()
        referenced = {r[0] for r in con.execute(
            "SELECT clip_name FROM detections WHERE clip_name IS NOT NULL AND clip_name != ''")}
        # Base d'abord, fichiers ensuite : si la suppression d'un fichier échoue, on perd de la place,
        # pas une détection qui pointerait vers un audio disparu.
        if rows and not dry_run:
            with con:
                con.executemany("UPDATE detections SET clip_name = '' WHERE id = ?",
                                [(r[0],) for r in rows])
    finally:
        con.close()

    freed = 0
    for _, name in rows:
        wav = clip_path(name)
        if wav:
            freed += remove(files_for(wav), dry_run)

    stripped = {name.removeprefix("clips/") for _, name in rows}
    orphans = []
    for wav in CLIPS.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*.wav"):
        rel = wav.relative_to(CLIPS).as_posix()
        if rel not in referenced and rel not in stripped and now - wav.stat().st_mtime > MIN_AGE_S:
            orphans.append(wav)
    for wav in orphans:
        freed += remove(files_for(wav), dry_run)

    verb = "supprimerait" if dry_run else "supprimé"
    log(f"{verb} : audio de {len(rows)} détections hors top {TOP_N}, "
        f"{len(orphans)} clips orphelins, {freed / 1e6:.0f} Mo")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--loop", type=int, metavar="SECONDES")
    args = ap.parse_args()
    if not DB.exists():
        sys.exit(f"Base introuvable : {DB}")
    while True:
        try:
            run_once(args.dry_run)
        except sqlite3.Error as e:
            if not args.loop:
                raise
            log(f"ERREUR base : {e} (nouvel essai au prochain passage)")
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
