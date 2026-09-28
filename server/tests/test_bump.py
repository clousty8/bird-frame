"""Tests de `scripts/bump.py` (version unique du monorepo).

Le script vit à la racine du dépôt (`scripts/`), hors du paquet serveur : il est chargé par
chemin. Chaque test travaille sur une copie des VRAIS fichiers versionnés (dans `tmp_path`),
jamais sur le dépôt lui-même — sauf `test_real_repository_is_consistent`, en lecture seule.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUMP_PATH = REPO_ROOT / "scripts" / "bump.py"

VERSIONED_FILES = (
    "VERSION",
    "server/pyproject.toml",
    "server/uv.lock",
    "server/app/version.py",
    "node/pyproject.toml",
    "node/uv.lock",
    "node/bridge/__init__.py",
    "web/package.json",
    "web/package-lock.json",
)


def _load_bump():
    spec = importlib.util.spec_from_file_location("bird_frame_bump", BUMP_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # requis par @dataclass
    spec.loader.exec_module(module)
    return module


bump = _load_bump()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel in VERSIONED_FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dest)
    return tmp_path


def _run(capsys, *args: str) -> tuple[int, str, str]:
    code = bump.main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_real_repository_is_consistent(capsys) -> None:
    code, out, err = _run(capsys, "--check", "--root", str(REPO_ROOT))
    assert code == 0, err
    assert out.startswith("ok : ")


def test_print_outputs_version_only(repo: Path, capsys) -> None:
    current = (repo / "VERSION").read_text().strip()
    code, out, _ = _run(capsys, "--print", "--root", str(repo))
    assert code == 0
    assert out == f"{current}\n"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("patch", (0, 0, 1)), ("minor", (0, 1, 0)), ("major", (1, 0, 0))],
)
def test_bump_kinds_compute_next_version(kind: str, expected: tuple[int, int, int]) -> None:
    assert bump.bumped("0.0.0", kind) == "{}.{}.{}".format(*expected)
    assert bump.bumped("1.9.9", "patch") == "1.9.10"
    assert bump.bumped("1.9.9", "minor") == "1.10.0"
    assert bump.bumped("1.9.9", "major") == "2.0.0"


def test_minor_bump_updates_every_location_and_nothing_else(repo: Path, capsys) -> None:
    before = {rel: (repo / rel).read_text() for rel in VERSIONED_FILES}
    current = before["VERSION"].strip()
    target = bump.bumped(current, "minor")

    code, out, err = _run(capsys, "minor", "--root", str(repo))
    assert code == 0, err
    assert out == f"{target}\n"  # seule la version sur stdout (utilisable par /release)

    assert (repo / "VERSION").read_text() == f"{target}\n"
    assert f'__version__ = "{target}"' in (repo / "server/app/version.py").read_text()
    assert f'__version__ = "{target}"' in (repo / "node/bridge/__init__.py").read_text()
    for pyproject in ("server/pyproject.toml", "node/pyproject.toml"):
        assert tomllib.loads((repo / pyproject).read_text())["project"]["version"] == target
    for lock, name in (
        ("server/uv.lock", "bird-frame-server"),
        ("node/uv.lock", "bird-frame-bridge"),
    ):
        packages = tomllib.loads((repo / lock).read_text())["package"]
        assert [p["version"] for p in packages if p["name"] == name] == [target]
        # les dépendances tierces n'ont pas bougé
        old_packages = tomllib.loads(before[lock])["package"]
        assert [p for p in packages if p["name"] != name] == [
            p for p in old_packages if p["name"] != name
        ]
    assert json.loads((repo / "web/package.json").read_text())["version"] == target
    lock = json.loads((repo / "web/package-lock.json").read_text())
    assert lock["version"] == target
    assert lock["packages"][""]["version"] == target

    # Diff minimal : chaque fichier ne diffère que sur les lignes de version.
    for rel in VERSIONED_FILES:
        old_lines = before[rel].splitlines()
        new_lines = (repo / rel).read_text().splitlines()
        assert len(old_lines) == len(new_lines), rel
        changed = [(o, n) for o, n in zip(old_lines, new_lines, strict=True) if o != n]
        assert changed, rel
        for old_line, new_line in changed:
            assert old_line.replace(current, target) == new_line, rel

    code, _, err = _run(capsys, "--check", "--root", str(repo))
    assert code == 0, err


def test_explicit_version(repo: Path, capsys) -> None:
    code, out, err = _run(capsys, "3.2.1", "--root", str(repo))
    assert code == 0, err
    assert out == "3.2.1\n"
    assert bump.read_versions(repo) == dict.fromkeys(bump.read_versions(repo), "3.2.1")


@pytest.mark.parametrize("spec", ["1.2", "v1.2.3", "1.2.3-rc1", "01.2.3", "patchy"])
def test_invalid_spec_is_refused_without_writing(repo: Path, capsys, spec: str) -> None:
    before = (repo / "VERSION").read_text()
    code, out, err = _run(capsys, spec, "--root", str(repo))
    assert code == 1
    assert out == ""
    assert "invalide" in err
    assert (repo / "VERSION").read_text() == before


def test_downgrade_and_noop_are_refused(repo: Path, capsys) -> None:
    (repo / "VERSION").write_text("0.1.0\n")
    code, _, err = _run(capsys, "0.0.9", "--root", str(repo))
    assert code == 1
    assert "inférieure" in err
    code, _, err = _run(capsys, "0.1.0", "--root", str(repo))
    assert code == 1
    assert "rien à faire" in err


def test_check_fails_and_names_the_divergent_file(repo: Path, capsys) -> None:
    pkg = repo / "web/package.json"
    current = (repo / "VERSION").read_text().strip()
    pkg.write_text(pkg.read_text().replace(f'"version": "{current}"', '"version": "9.9.9"', 1))

    code, out, err = _run(capsys, "--check", "--root", str(repo))
    assert code == 1
    assert out == ""
    assert "web/package.json : 9.9.9" in err


def test_increment_refused_when_diverged_but_explicit_realign_works(repo: Path, capsys) -> None:
    init = repo / "node/bridge/__init__.py"
    current = (repo / "VERSION").read_text().strip()
    init.write_text(init.read_text().replace(f'"{current}"', '"0.0.1"'))

    code, _, err = _run(capsys, "patch", "--root", str(repo))
    assert code == 1
    assert "node/bridge/__init__.py : 0.0.1" in err

    code, out, err = _run(
        capsys, current, "--root", str(repo)
    )  # réalignement sur la version courante
    assert code == 0, err
    assert out == f"{current}\n"
    code, _, _ = _run(capsys, "--check", "--root", str(repo))
    assert code == 0


def test_missing_package_lock_is_optional(repo: Path, capsys) -> None:
    (repo / "web/package-lock.json").unlink()
    code, _, err = _run(capsys, "patch", "--root", str(repo))
    assert code == 0, err
    assert not (repo / "web/package-lock.json").exists()


def test_unreadable_location_is_an_error_not_a_skip(repo: Path, capsys) -> None:
    (repo / "server/app/version.py").write_text("VERSION = 'oops'\n")
    code, _, err = _run(capsys, "--check", "--root", str(repo))
    assert code == 1
    assert "server/app/version.py" in err
