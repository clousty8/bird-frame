#!/usr/bin/env python3
"""Empaquette le bridge en `node-bundle-<version>.tar.gz` (+ `.sha256`) pour la mise à jour des nœuds.

Usage (bibliothèque standard uniquement, Python ≥ 3.11) :

    python3 scripts/build_node_bundle.py --out /chemin/sortie
    # → /chemin/sortie/node-bundle-0.1.0.tar.gz et node-bundle-0.1.0.tar.gz.sha256

Appelé au build de l'image Docker (`Dockerfile`), servi ensuite par le serveur (contrat §12).

Contenu de l'archive (entrées à la racine, sans dossier englobant) :
- `VERSION` — la version (doit être égale au `__version__` de `node/bridge/__init__.py`) ;
- `pyproject.toml`, `uv.lock` — de quoi faire `uv sync --frozen --no-dev` sur le nœud ;
- `bridge/**` — le code, sans `__pycache__`, `*.pyc`, ni les tests (qui vivent dans `node/tests/`,
  jamais inclus) ; jamais `node/config/*.env` ni `node/state/`.

L'archive est reproductible (entrées triées, dates, propriétaires et droits normalisés, en-tête
gzip sans date) : deux builds du même commit donnent le même SHA-256. `SOURCE_DATE_EPOCH` fixe la
date des fichiers (défaut 0).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_VERSION_RE = re.compile(r'^__version__ = "([^"]*)"$', re.MULTILINE)
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_EXCLUDED_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache", ".ruff_cache"}
_EXCLUDED_SUFFIXES = (".pyc", ".pyo")


class BundleError(Exception):
    pass


def bundle_name(version: str) -> str:
    return f"node-bundle-{version}.tar.gz"


def _bridge_files(node_dir: Path) -> list[tuple[str, Path]]:
    bridge_dir = node_dir / "bridge"
    if not (bridge_dir / "__init__.py").is_file():
        raise BundleError(f"{bridge_dir}/__init__.py introuvable")
    entries: list[tuple[str, Path]] = []
    for path in sorted(bridge_dir.rglob("*")):
        rel_parts = path.relative_to(node_dir).parts
        if any(part in _EXCLUDED_NAMES or part == "tests" for part in rel_parts):
            continue
        if path.is_dir() or path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if path.is_symlink():
            raise BundleError(f"lien symbolique refusé dans le bundle : {path}")
        entries.append(("/".join(rel_parts), path))
    return entries


def _add_bytes(archive: tarfile.TarFile, name: str, data: bytes, mtime: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = mtime
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.type = tarfile.REGTYPE
    archive.addfile(info, io.BytesIO(data))


def build_bundle(node_dir: Path, version: str, out_dir: Path, *, mtime: int = 0) -> Path:
    """Construit l'archive et son `.sha256` dans `out_dir`. Renvoie le chemin de l'archive."""
    if not _SEMVER_RE.match(version):
        raise BundleError(f"version invalide {version!r} (attendu X.Y.Z)")
    init_text = (node_dir / "bridge" / "__init__.py").read_text(encoding="utf-8")
    found = _VERSION_RE.findall(init_text)
    if found != [version]:
        raise BundleError(
            f"node/bridge/__init__.py porte {found or 'aucun __version__'}, VERSION dit {version} "
            "(lancer `python3 scripts/bump.py --check`)"
        )
    for required in ("pyproject.toml", "uv.lock"):
        if not (node_dir / required).is_file():
            raise BundleError(f"{node_dir / required} introuvable")

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / bundle_name(version)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
            _add_bytes(archive, "VERSION", f"{version}\n".encode(), mtime)
            _add_bytes(archive, "pyproject.toml", (node_dir / "pyproject.toml").read_bytes(), mtime)
            _add_bytes(archive, "uv.lock", (node_dir / "uv.lock").read_bytes(), mtime)
            for name, path in _bridge_files(node_dir):
                _add_bytes(archive, name, path.read_bytes(), mtime)
    data = buffer.getvalue()
    target.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_node_bundle.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="dossier de sortie")
    parser.add_argument("--node-dir", type=Path, default=REPO_ROOT / "node", help="dossier node/ (défaut : dépôt)")
    parser.add_argument("--version-file", type=Path, default=REPO_ROOT / "VERSION", help="fichier VERSION")
    args = parser.parse_args(argv)
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
        target = build_bundle(args.node_dir, version, args.out, mtime=mtime)
    except (BundleError, OSError, ValueError) as exc:
        print(f"build_node_bundle.py : {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
