#!/usr/bin/env python3
"""Génère la valeur de BIRDFRAME_UI_PASSWORD_HASH (mot de passe de l'interface web).

Hash scrypt salé, format `scrypt$n$r$p$sel_base64$hash_base64` (contrat §2.2), calculé
par `server/app/passwords.py` — bibliothèque standard uniquement : tourne avec
`python3 scripts/hash_password.py` comme avec `uv run scripts/hash_password.py`.

Exemples :
    uv run scripts/hash_password.py              # demande le mot de passe deux fois, sans écho
    printf '%s' "$MOT_DE_PASSE" | python3 scripts/hash_password.py --stdin

Le hash contient des `$` : entre apostrophes dans un shell
(`export BIRDFRAME_UI_PASSWORD_HASH='scrypt$32768$…'`), `$$` dans un fichier
docker-compose ; tel quel dans `server/.env` et dans les variables Railway.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

from app.passwords import hash_password  # noqa: E402  (après l'ajout de server/ au chemin)


def read_password(from_stdin: bool) -> str:
    if from_stdin:
        # Une seule ligne ; le saut de ligne final (echo, heredoc) ne fait pas partie du
        # mot de passe.
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Mot de passe de l'interface : ")
    second = getpass.getpass("Confirmer : ")
    if first != second:
        raise SystemExit("Les deux saisies diffèrent, rien n'a été généré.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="lire le mot de passe sur l'entrée standard (première ligne) au lieu de le demander",
    )
    args = parser.parse_args(argv)

    password = read_password(args.stdin)
    if not password:
        raise SystemExit("Mot de passe vide : rien n'a été généré.")
    if len(password) < 12:
        # Sur stderr : stdout ne contient que le hash (utilisable tel quel dans un script).
        print("Attention : mot de passe de moins de 12 caractères, interface publique.", file=sys.stderr)

    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
