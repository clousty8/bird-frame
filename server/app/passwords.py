"""Hash du mot de passe de l'interface (contrat §2.2) — bibliothèque standard uniquement.

Format auto-descriptif, une seule ligne, sans espace :

    scrypt$<n>$<r>$<p>$<sel_base64>$<hash_base64>

(base64 standard, avec remplissage). Les paramètres voyagent avec le hash : on peut
durcir `DEFAULT_N` plus tard sans invalider les hashs déjà configurés.

Ce module n'importe **que** la bibliothèque standard : `scripts/hash_password.py` (racine
du dépôt) l'importe directement, sans dépendre de FastAPI ni de l'environnement `uv` du
serveur.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass

SCHEME = "scrypt"
DEFAULT_N = 2**15
DEFAULT_R = 8
DEFAULT_P = 1
SALT_BYTES = 16
DKLEN = 32

# Garde-fous sur les paramètres lus dans un hash configuré : un hash aberrant (faute de
# frappe, copier-coller tronqué) doit être refusé au démarrage, pas faire exploser la
# mémoire à la première connexion.
_MAX_N = 2**20
_MAX_R = 32
_MAX_P = 16


class PasswordHashError(ValueError):
    """Hash mal formé ou paramètres hors bornes."""


@dataclass(frozen=True)
class ParsedHash:
    n: int
    r: int
    p: int
    salt: bytes
    digest: bytes


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # OpenSSL refuse au-delà de `maxmem` (32 Mio par défaut, juste en dessous de ce que
    # demande n=2**15, r=8) : mémoire exacte requise = 128·r·(n+p+2) octets, plus une marge.
    maxmem = 128 * r * (n + p + 2) + 1024 * 1024
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=maxmem
    )


def hash_password(
    password: str, *, n: int = DEFAULT_N, r: int = DEFAULT_R, p: int = DEFAULT_P
) -> str:
    """Hash scrypt salé, au format auto-descriptif du module."""
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")
    _check_params(n, r, p)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt, n, r, p, DKLEN)
    return "$".join(
        [
            SCHEME,
            str(n),
            str(r),
            str(p),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def parse_password_hash(encoded: str) -> ParsedHash:
    """Décode et valide un hash ; lève `PasswordHashError` avec un message explicite."""
    parts = encoded.strip().split("$")
    if len(parts) != 6 or parts[0] != SCHEME:
        raise PasswordHashError(
            "format attendu « scrypt$n$r$p$sel_base64$hash_base64 » "
            "(générer avec scripts/hash_password.py)"
        )
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError as exc:
        raise PasswordHashError("paramètres n, r, p non entiers") from exc
    _check_params(n, r, p)
    try:
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PasswordHashError("sel ou hash non encodé en base64") from exc
    if len(salt) < 8 or len(digest) < 16:
        raise PasswordHashError("sel ou hash trop court")
    return ParsedHash(n=n, r=r, p=p, salt=salt, digest=digest)


def verify_password(password: str, encoded: str | ParsedHash) -> bool:
    """Vrai si `password` correspond au hash. Comparaison en temps constant."""
    parsed = encoded if isinstance(encoded, ParsedHash) else parse_password_hash(encoded)
    candidate = _scrypt(password, parsed.salt, parsed.n, parsed.r, parsed.p, len(parsed.digest))
    return hmac.compare_digest(candidate, parsed.digest)


def _check_params(n: int, r: int, p: int) -> None:
    if n < 2 or n > _MAX_N or n & (n - 1) != 0:
        raise PasswordHashError(f"n doit être une puissance de 2 entre 2 et {_MAX_N} (reçu {n})")
    if not 1 <= r <= _MAX_R:
        raise PasswordHashError(f"r doit être entre 1 et {_MAX_R} (reçu {r})")
    if not 1 <= p <= _MAX_P:
        raise PasswordHashError(f"p doit être entre 1 et {_MAX_P} (reçu {p})")
