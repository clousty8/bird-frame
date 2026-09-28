#!/usr/bin/env python3
"""Version unique de bird-frame : lit, vérifie et incrémente d'un coup tous les emplacements.

Usage (depuis la racine du dépôt, Python ≥ 3.11, bibliothèque standard uniquement) :

    python3 scripts/bump.py patch|minor|major   # incrémente, écrit partout, affiche la nouvelle version
    python3 scripts/bump.py 1.4.0               # version explicite (strictement supérieure, ou égale
                                                # pour réaligner des fichiers qui divergent)
    python3 scripts/bump.py --check             # CI : code 1 si un emplacement diverge de VERSION
    python3 scripts/bump.py --print             # affiche la version courante (fichier VERSION)

Seule la nouvelle version est écrite sur la sortie standard (`NEW=$(python3 scripts/bump.py minor)`
pour la commande /release) ; le détail des fichiers touchés va sur la sortie d'erreur.

Emplacements tenus à jour (tous DOIVENT porter la même version) :
- `VERSION` (racine) — la référence ;
- `server/pyproject.toml`, `server/uv.lock` (paquet `bird-frame-server`), `server/app/version.py` ;
- `node/pyproject.toml`, `node/uv.lock` (paquet `bird-frame-bridge`), `node/bridge/__init__.py` ;
- `web/package.json`, `web/package-lock.json` (racine et `packages[""]`, si la version y figure).

Les fichiers sont modifiés textuellement (mise en forme conservée), puis relus et vérifiés : un
fichier JSON/TOML dont autre chose que la version aurait changé fait échouer le script.
Format accepté : `X.Y.Z` (entiers, sans préversion) — c'est aussi ce que compare le bridge pour
décider d'une mise à jour (docs/api-contract.md §12).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
BUMP_KINDS = ("patch", "minor", "major")


class BumpError(Exception):
    """Erreur attendue (divergence, fichier illisible, argument invalide) : message clair, code 1."""


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value)
    if not match:
        raise BumpError(f"version invalide {value!r} : format attendu X.Y.Z (entiers, sans préfixe ni suffixe)")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def bumped(current: str, kind: str) -> str:
    major, minor, patch = parse_version(current)
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise BumpError(f"type d'incrément inconnu : {kind!r}")


# --- Lecteurs / écrivains par format -----------------------------------------------------------


def _sub_exactly_once(pattern: re.Pattern[str], text: str, new_version: str, where: str) -> str:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise BumpError(f"{where} : {len(matches)} occurrence(s) de la version trouvée(s), 1 attendue")
    return pattern.sub(lambda m: f"{m.group(1)}{new_version}{m.group(3)}", text, count=1)


def _read_version_file(text: str) -> str:
    return text.strip()


def _write_version_file(_text: str, new_version: str) -> str:
    return f"{new_version}\n"


_PY_VERSION_RE = re.compile(r'^(__version__ = ")([^"]*)(")$', re.MULTILINE)


def _read_python(text: str) -> str:
    matches = _PY_VERSION_RE.findall(text)
    if len(matches) != 1:
        raise BumpError(f"{len(matches)} ligne(s) `__version__ = \"…\"` trouvée(s), 1 attendue")
    return matches[0][1]


def _write_python(text: str, new_version: str) -> str:
    return _sub_exactly_once(_PY_VERSION_RE, text, new_version, "__version__")


def _project_table_span(text: str) -> tuple[int, int]:
    start = re.search(r"^\[project\]\s*$", text, re.MULTILINE)
    if start is None:
        raise BumpError("table [project] introuvable")
    end = re.search(r"^\[", text[start.end() :], re.MULTILINE)
    return start.end(), (start.end() + end.start()) if end else len(text)


_PYPROJECT_VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]*)(")\s*$', re.MULTILINE)


def _read_pyproject(text: str) -> str:
    data = tomllib.loads(text)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        raise BumpError("[project].version absent (version dynamique non prise en charge)")
    return version


def _write_pyproject(text: str, new_version: str) -> str:
    start, end = _project_table_span(text)
    section = _sub_exactly_once(_PYPROJECT_VERSION_RE, text[start:end], new_version, "[project].version")
    return text[:start] + section + text[end:]


def _uv_lock_reader(package: str) -> Callable[[str], str]:
    def read(text: str) -> str:
        data = tomllib.loads(text)
        found = [p for p in data.get("package", []) if p.get("name") == package]
        if len(found) != 1 or not isinstance(found[0].get("version"), str):
            raise BumpError(f"paquet {package!r} introuvable (ou sans version) dans uv.lock")
        return found[0]["version"]

    return read


def _uv_lock_writer(package: str) -> Callable[[str, str], str]:
    pattern = re.compile(
        r'(\[\[package\]\]\nname = "' + re.escape(package) + r'"\nversion = ")([^"]*)(")'
    )

    def write(text: str, new_version: str) -> str:
        return _sub_exactly_once(pattern, text, new_version, f"uv.lock ({package})")

    return write


_JSON_TOP_VERSION_RE = re.compile(r'^(  "version": ")([^"]*)(")', re.MULTILINE)
_LOCK_ROOT_PACKAGE_VERSION_RE = re.compile(r'(\n    "": \{\n(?:      .*\n)*?      "version": ")([^"]*)(")')


def _read_package_json(text: str) -> str:
    version = json.loads(text).get("version")
    if not isinstance(version, str):
        raise BumpError("champ racine \"version\" absent")
    return version


def _write_package_json(text: str, new_version: str) -> str:
    return _sub_exactly_once(_JSON_TOP_VERSION_RE, text, new_version, "package.json")


def _read_lock_root(text: str) -> str | None:
    version = json.loads(text).get("version")
    return version if isinstance(version, str) else None


def _read_lock_package(text: str) -> str | None:
    version = json.loads(text).get("packages", {}).get("", {}).get("version")
    return version if isinstance(version, str) else None


def _write_lock_root(text: str, new_version: str) -> str:
    # Première occurrence à 2 espaces d'indentation = le champ racine (les paquets sont à 6+).
    return _JSON_TOP_VERSION_RE.sub(lambda m: f"{m.group(1)}{new_version}{m.group(3)}", text, count=1)


def _write_lock_package(text: str, new_version: str) -> str:
    return _sub_exactly_once(_LOCK_ROOT_PACKAGE_VERSION_RE, text, new_version, 'package-lock.json packages[""]')


@dataclass(frozen=True)
class Location:
    """Un emplacement de version : un fichier, et comment y lire / écrire la version.

    `optional` : le fichier (ou le champ) peut ne pas porter de version — `read` renvoie alors
    `None` et l'emplacement est ignoré (cas de `package-lock.json` sans champ `version`).
    """

    label: str
    rel_path: str
    read: Callable[[str], str | None]
    write: Callable[[str, str], str]
    optional: bool = False


LOCATIONS: tuple[Location, ...] = (
    Location("VERSION", "VERSION", _read_version_file, _write_version_file),
    Location("server/pyproject.toml", "server/pyproject.toml", _read_pyproject, _write_pyproject),
    Location(
        "server/uv.lock",
        "server/uv.lock",
        _uv_lock_reader("bird-frame-server"),
        _uv_lock_writer("bird-frame-server"),
    ),
    Location("server/app/version.py", "server/app/version.py", _read_python, _write_python),
    Location("node/pyproject.toml", "node/pyproject.toml", _read_pyproject, _write_pyproject),
    Location(
        "node/uv.lock",
        "node/uv.lock",
        _uv_lock_reader("bird-frame-bridge"),
        _uv_lock_writer("bird-frame-bridge"),
    ),
    Location("node/bridge/__init__.py", "node/bridge/__init__.py", _read_python, _write_python),
    Location("web/package.json", "web/package.json", _read_package_json, _write_package_json),
    Location(
        "web/package-lock.json (racine)",
        "web/package-lock.json",
        _read_lock_root,
        _write_lock_root,
        optional=True,
    ),
    Location(
        'web/package-lock.json (packages[""])',
        "web/package-lock.json",
        _read_lock_package,
        _write_lock_package,
        optional=True,
    ),
)


# --- Opérations --------------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BumpError(f"{path} illisible : {exc}") from exc


def read_versions(root: Path) -> dict[str, str]:
    """Version lue à chaque emplacement (les emplacements optionnels absents sont omis)."""
    versions: dict[str, str] = {}
    for loc in LOCATIONS:
        path = root / loc.rel_path
        if loc.optional and not path.exists():
            continue
        try:
            value = loc.read(_read_text(path))
        except (BumpError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise BumpError(f"{loc.label} : {exc}") from exc
        if value is None:
            if loc.optional:
                continue
            raise BumpError(f"{loc.label} : aucune version trouvée")
        versions[loc.label] = value
    return versions


def current_version(root: Path) -> str:
    version = _read_version_file(_read_text(root / "VERSION"))
    parse_version(version)
    return version


def divergences(root: Path) -> tuple[str, list[str]]:
    """(version de référence, liste lisible des emplacements qui en divergent)."""
    reference = current_version(root)
    problems = [
        f"{label} : {value} (attendu {reference})"
        for label, value in read_versions(root).items()
        if value != reference
    ]
    return reference, problems


def _write_atomic(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.chmod(tmp, path.stat().st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _check_json_only_version_changed(old_text: str, new_text: str, rel_path: str, new_version: str) -> None:
    old, new = json.loads(old_text), json.loads(new_text)
    if "version" in old:
        old["version"] = new_version
    root_pkg = old.get("packages", {}).get("")
    if isinstance(root_pkg, dict) and "version" in root_pkg:
        root_pkg["version"] = new_version
    if old != new:
        raise BumpError(f"{rel_path} : la réécriture aurait modifié autre chose que la version (abandon)")


def write_version(root: Path, new_version: str) -> list[str]:
    """Écrit `new_version` à tous les emplacements. Renvoie la liste des fichiers modifiés."""
    parse_version(new_version)
    # Regroupe par fichier (package-lock.json porte deux emplacements).
    by_file: dict[str, list[Location]] = {}
    for loc in LOCATIONS:
        by_file.setdefault(loc.rel_path, []).append(loc)

    staged: dict[Path, str] = {}
    for rel_path, locs in by_file.items():
        path = root / rel_path
        if all(loc.optional for loc in locs) and not path.exists():
            continue
        original = _read_text(path)
        text = original
        for loc in locs:
            try:
                present = loc.read(text)
            except (BumpError, ValueError, tomllib.TOMLDecodeError) as exc:
                raise BumpError(f"{loc.label} : {exc}") from exc
            if present is None and loc.optional:
                continue
            text = loc.write(text, new_version)
        if rel_path.endswith(".json"):
            _check_json_only_version_changed(original, text, rel_path, new_version)
        if text != original:
            staged[path] = text

    # Toutes les réécritures sont calculées (et validées) avant la première écriture disque.
    for path, text in staged.items():
        _write_atomic(path, text)
    return [str(path.relative_to(root)) for path in staged]


def resolve_target(root: Path, spec: str) -> str:
    reference, problems = divergences(root)
    if spec in BUMP_KINDS:
        if problems:
            raise BumpError(
                "versions divergentes, incrément refusé :\n  - "
                + "\n  - ".join(problems)
                + f"\nRéalignez d'abord avec : python3 scripts/bump.py {reference}"
            )
        return bumped(reference, spec)
    target = spec
    if parse_version(target) < parse_version(reference):
        raise BumpError(f"{target} est inférieure à la version courante {reference} (retour en arrière refusé)")
    if target == reference and not problems:
        raise BumpError(f"déjà en {reference} partout : rien à faire")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bump.py",
        description="Version unique de bird-frame (VERSION, pyproject, uv.lock, package.json, __version__).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("spec", nargs="?", help="patch | minor | major | X.Y.Z")
    group.add_argument("--check", action="store_true", help="échoue (code 1) si un emplacement diverge")
    group.add_argument("--print", dest="print_version", action="store_true", help="affiche la version courante")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="racine du dépôt (défaut : celle du script)")
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    try:
        if args.print_version:
            print(current_version(root))
            return 0
        if args.check:
            reference, problems = divergences(root)
            if problems:
                print(f"Versions divergentes (référence VERSION = {reference}) :", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                print(f"Réalignez avec : python3 scripts/bump.py {reference}", file=sys.stderr)
                return 1
            count = len(read_versions(root))
            print(f"ok : {reference} ({count} emplacements concordants)")
            return 0

        target = resolve_target(root, args.spec)
        changed = write_version(root, target)
        _, problems = divergences(root)
        if problems:  # ne devrait jamais arriver : défaut de ce script
            print("Incohérence après écriture :\n  - " + "\n  - ".join(problems), file=sys.stderr)
            return 1
        for rel_path in changed:
            print(f"  mis à jour : {rel_path}", file=sys.stderr)
        print(target)
        return 0
    except BumpError as exc:
        print(f"bump.py : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
