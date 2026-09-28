"""Scripts d'installation gérée (api-contract.md §12) : superviseur `node/deploy/run-bridge.sh`,
`scripts/install-node.sh`, `scripts/uninstall-node.sh`.

Tout se passe dans `tmp_path` : faux bridges (scripts shell à la place de `.venv/bin/python`), faux
`uv`, `HOME` redirigé, `--no-launchd` (jamais d'agent launchd installé pendant les tests), jamais
`local-test/`, et le vrai bridge lancé en bout de chaîne pointe sur des ports morts (aucun appel à
BirdNET-Go ni à un serveur réel).
"""

from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_BRIDGE = REPO_ROOT / "node" / "deploy" / "run-bridge.sh"
INSTALL = REPO_ROOT / "scripts" / "install-node.sh"
UNINSTALL = REPO_ROOT / "scripts" / "uninstall-node.sh"
REPO_VERSION = (REPO_ROOT / "VERSION").read_text().strip()

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="scripts bash POSIX")


def _executable(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# --- Superviseur run-bridge.sh ------------------------------------------------------------------

CRASH = 'echo "$(basename "$PWD") $*" >> "$MARKS"\necho "Traceback: boom" >&2\nexit 1\n'
OK = 'echo "$(basename "$PWD") $*" >> "$MARKS"\nexit 0\n'


def fake_version(root: Path, version: str, body: str) -> None:
    _executable(root / "versions" / version / ".venv" / "bin" / "python", "#!/bin/sh\n" + body)


def point_current(root: Path, version: str) -> None:
    link = root / "current"
    if link.is_symlink():
        link.unlink()
    os.symlink(f"versions/{version}", link)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "node-root"
    (root / "state").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "config" / "bridge.env").write_text("# factice\n")
    return root


def run_supervisor(root: Path, tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    full_env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "MARKS": str(tmp_path / "marks.log"),
        "ROOT": str(root),
        **env,
    }
    return subprocess.run(
        ["/bin/bash", str(RUN_BRIDGE), str(root)], env=full_env, capture_output=True, text=True, timeout=30
    )


def marks(tmp_path: Path) -> list[str]:
    path = tmp_path / "marks.log"
    return path.read_text().splitlines() if path.exists() else []


def test_supervisor_rolls_back_after_three_startup_crashes(root: Path, tmp_path: Path) -> None:
    fake_version(root, "0.1.0", OK)
    fake_version(root, "0.2.0", CRASH)
    point_current(root, "0.2.0")
    (root / "previous").write_text("0.1.0\n")

    for attempt in (1, 2):
        result = run_supervisor(root, tmp_path)
        assert result.returncode == 1, result.stderr
        assert f"plantage au démarrage n°{attempt}" in result.stderr
        assert os.readlink(root / "current") == "versions/0.2.0"
        assert not (root / "state" / "rolled-back-versions").exists()

    result = run_supervisor(root, tmp_path)
    assert result.returncode == 1
    assert "RETOUR ARRIÈRE" in result.stderr
    assert os.readlink(root / "current") == "versions/0.1.0"
    assert (root / "state" / "rolled-back-versions").read_text().split() == ["0.2.0"]
    assert not (root / "previous").exists()
    assert (root / "state" / "supervisor-crashes").read_text() == ""

    result = run_supervisor(root, tmp_path)  # relance par launchd : l'ancienne version tourne
    assert result.returncode == 0, result.stderr
    assert marks(tmp_path)[-1] == f"0.1.0 -m bridge --config {root}/config/bridge.env"
    assert marks(tmp_path).count(f"0.2.0 -m bridge --config {root}/config/bridge.env") == 3


def test_supervisor_ignores_old_crashes_outside_the_window(root: Path, tmp_path: Path) -> None:
    fake_version(root, "0.1.0", OK)
    fake_version(root, "0.2.0", CRASH)
    point_current(root, "0.2.0")
    (root / "previous").write_text("0.1.0\n")
    old = int(time.time()) - 400
    (root / "state" / "supervisor-crashes").write_text(f"{old} 0.2.0\n{old} 0.2.0\n{old + 1} 0.1.0\n")

    result = run_supervisor(root, tmp_path)
    assert "plantage au démarrage n°1" in result.stderr
    assert os.readlink(root / "current") == "versions/0.2.0"


def test_supervisor_does_not_count_environment_errors_or_late_crashes(root: Path, tmp_path: Path) -> None:
    fake_version(root, "0.1.0", OK)
    fake_version(root, "0.2.0", 'echo "Configuration invalide" >&2\nexit 2\n')
    point_current(root, "0.2.0")
    (root / "previous").write_text("0.1.0\n")
    for _ in range(4):
        result = run_supervisor(root, tmp_path)
        assert result.returncode == 2
        assert "pas compté comme plantage" in result.stderr
    assert os.readlink(root / "current") == "versions/0.2.0"

    fake_version(root, "0.3.0", CRASH)
    point_current(root, "0.3.0")
    for _ in range(4):  # fenêtre de démarrage nulle : tout plantage est « tardif »
        assert run_supervisor(root, tmp_path, BRIDGE_SUPERVISOR_STARTUP_WINDOW_S="0").returncode == 1
    assert os.readlink(root / "current") == "versions/0.3.0"
    assert not (root / "state" / "rolled-back-versions").exists()


def test_supervisor_without_previous_keeps_current_and_says_so(root: Path, tmp_path: Path) -> None:
    fake_version(root, "0.2.0", CRASH)
    point_current(root, "0.2.0")
    for _ in range(3):
        result = run_supervisor(root, tmp_path)
    assert "aucune version précédente utilisable" in result.stderr
    assert os.readlink(root / "current") == "versions/0.2.0"


def test_supervisor_relaunches_immediately_after_update(root: Path, tmp_path: Path) -> None:
    # 0.1.0 « installe » 0.2.0 (bascule current) puis sort en 75, comme bridge/updater.py.
    fake_version(
        root,
        "0.1.0",
        'echo "$(basename "$PWD")" >> "$MARKS"\ncd "$ROOT" && rm current && ln -s versions/0.2.0 current\nexit 75\n',
    )
    fake_version(root, "0.2.0", OK)
    point_current(root, "0.1.0")
    result = run_supervisor(root, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "relance immédiate" in result.stderr
    assert marks(tmp_path)[0] == "0.1.0"
    assert marks(tmp_path)[1].startswith("0.2.0 -m bridge")


def test_supervisor_forwards_sigterm_for_a_clean_stop(root: Path, tmp_path: Path) -> None:
    fake_version(
        root,
        "0.1.0",
        'trap \'echo term >> "$MARKS"; exit 0\' TERM\necho started >> "$MARKS"\nwhile :; do sleep 0.1; done\n',
    )
    point_current(root, "0.1.0")
    env = {"PATH": os.environ["PATH"], "MARKS": str(tmp_path / "marks.log"), "HOME": str(tmp_path)}
    proc = subprocess.Popen(
        ["/bin/bash", str(RUN_BRIDGE), str(root)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        deadline = time.time() + 10
        while "started" not in marks(tmp_path):
            assert time.time() < deadline, "le faux bridge n'a pas démarré"
            time.sleep(0.05)
        proc.send_signal(signal.SIGTERM)
        _, stderr = proc.communicate(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, stderr
    assert marks(tmp_path) == ["started", "term"]
    assert "arrêt demandé" in stderr
    assert not (root / "state" / "supervisor-crashes").exists()


def test_supervisor_without_current_fails_clearly(root: Path, tmp_path: Path) -> None:
    result = run_supervisor(root, tmp_path)
    assert result.returncode == 78
    assert "current absent" in result.stderr


# --- install-node.sh / uninstall-node.sh ---------------------------------------------------------


@pytest.fixture
def fake_uv(tmp_path: Path) -> Path:
    return _executable(
        tmp_path / "bin" / "uv",
        f"""#!/bin/sh
[ "$*" = "sync --frozen --no-dev" ] || {{ echo "arguments inattendus : $*" >&2; exit 3; }}
mkdir -p .venv/bin
printf '#!/bin/sh\\nexec "{sys.executable}" "$@"\\n' > .venv/bin/python
chmod +x .venv/bin/python
""",
    )


@pytest.fixture
def source_config(tmp_path: Path, seeded_db_path: Path) -> Path:
    old_state = tmp_path / "ancien-etat.json"
    old_state.write_text('{"cursor": 12, "updated_at": "2026-09-28T10:00:00Z"}')
    config = tmp_path / "pornic.env"
    config.write_text(
        "\n".join(
            [
                "# config de test — ports morts : aucun serveur ni BirdNET-Go réel contacté",
                "BRIDGE_SERVER_URL=http://127.0.0.1:9",
                "BRIDGE_NODE_ID=1",
                "BRIDGE_SECRET=secret-de-test",
                "BRIDGE_SITE_SLUG=pornic",
                f"BRIDGE_DB_PATH={seeded_db_path}",
                f"BRIDGE_CLIPS_DIR={tmp_path}",
                "BRIDGE_NODE_API=http://127.0.0.1:9",
                f"BRIDGE_STATE_FILE={old_state}",
                "BRIDGE_NODE_READONLY=1",
                "BRIDGE_AUTO_UPDATE=0",
                "",
            ]
        )
    )
    return config


def run_script(script: Path, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {"PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}", "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir(exist_ok=True)
    return subprocess.run(
        ["/bin/bash", str(script), *args], env=env, capture_output=True, text=True, timeout=120
    )


def test_install_node_creates_managed_install_idempotently(
    tmp_path: Path, fake_uv: Path, source_config: Path
) -> None:
    root = tmp_path / "managed"
    args = ("--config", str(source_config), "--root", str(root), "--no-launchd", "--uv", str(fake_uv))

    for _ in range(2):  # la réinstallation doit donner exactement le même résultat
        result = run_script(INSTALL, tmp_path, *args)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--no-launchd" in result.stdout
        assert f"tail -f {root}/logs/bridge.log" in result.stdout

    version_dir = root / "versions" / REPO_VERSION
    assert os.readlink(root / "current") == f"versions/{REPO_VERSION}"
    assert sorted(p.name for p in (root / "versions").iterdir()) == [REPO_VERSION]  # pas de reste
    assert (version_dir / "VERSION").read_text().strip() == REPO_VERSION
    assert (version_dir / "bridge" / "updater.py").is_file()
    assert (version_dir / "uv.lock").is_file()
    assert not (version_dir / "tests").exists()
    assert not (root / "previous").exists()
    for name in ("state", "logs", "downloads"):
        assert (root / name).is_dir()
    assert os.access(root / "bin" / "run-bridge.sh", os.X_OK)

    config = root / "config" / "bridge.env"
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    lines = config.read_text().splitlines()
    assert lines.count(f"BRIDGE_INSTALL_ROOT={root}") == 1
    assert lines.count("BRIDGE_AUTO_UPDATE=1") == 1
    assert "BRIDGE_AUTO_UPDATE=0" not in lines
    assert lines.count(f"BRIDGE_UV={fake_uv}") == 1
    assert lines.count(f"BRIDGE_STATE_FILE={root}/state/pornic.json") == 1
    assert "BRIDGE_SECRET=secret-de-test" in lines
    assert '"cursor": 12' in (root / "state" / "pornic.json").read_text()
    assert not (tmp_path / "home" / "Library").exists()  # aucun agent launchd

    # Une version plus ancienne pointée par current devient « previous » à la réinstallation.
    fake_version(root, "0.0.1", OK)
    point_current(root, "0.0.1")
    result = run_script(INSTALL, tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert (root / "previous").read_text().strip() == "0.0.1"
    assert os.readlink(root / "current") == f"versions/{REPO_VERSION}"


def test_installed_bridge_runs_under_the_supervisor_with_auto_update(
    tmp_path: Path, fake_uv: Path, source_config: Path
) -> None:
    """Bout en bout : le vrai bridge installé tourne sous run-bridge.sh, reconnaît l'installation
    gérée (updater actif), échoue proprement à joindre le serveur (port mort), s'arrête sur SIGTERM."""
    root = tmp_path / "managed"
    result = run_script(
        INSTALL, tmp_path, "--config", str(source_config), "--root", str(root), "--no-launchd", "--uv", str(fake_uv)
    )
    assert result.returncode == 0, result.stderr

    log = tmp_path / "bridge.log"
    with log.open("w") as handle:
        proc = subprocess.Popen(
            ["/bin/bash", str(root / "bin" / "run-bridge.sh"), str(root)],
            env={"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "PYTHONUNBUFFERED": "1"},
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.time() + 20
            while "serveur injoignable" not in log.read_text():
                assert proc.poll() is None, log.read_text()
                assert time.time() < deadline, log.read_text()
                time.sleep(0.1)
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=20)
        finally:
            if proc.poll() is None:
                proc.kill()
    output = log.read_text()
    assert proc.returncode == 0, output
    assert "Mise à jour automatique active" in output
    assert f"démarrage du bridge {REPO_VERSION}" in output
    assert "arrêt demandé" in output


def test_install_refuses_a_root_inside_local_test(tmp_path: Path, fake_uv: Path, source_config: Path) -> None:
    forbidden = REPO_ROOT / "local-test" / "ne-jamais-creer-ce-dossier"
    result = run_script(
        INSTALL, tmp_path, "--config", str(source_config), "--root", str(forbidden), "--no-launchd", "--uv", str(fake_uv)
    )
    assert result.returncode != 0
    assert "local-test" in result.stderr
    assert not forbidden.exists()


def test_install_failure_restores_previous_install(tmp_path: Path, fake_uv: Path, source_config: Path) -> None:
    root = tmp_path / "managed"
    ok = run_script(
        INSTALL, tmp_path, "--config", str(source_config), "--root", str(root), "--no-launchd", "--uv", str(fake_uv)
    )
    assert ok.returncode == 0, ok.stderr
    marker = root / "versions" / REPO_VERSION / "marqueur"
    marker.write_text("installation d'origine")

    failing_uv = _executable(tmp_path / "failing-uv", "#!/bin/sh\necho 'uv: échec simulé' >&2\nexit 1\n")
    result = run_script(
        INSTALL, tmp_path, "--config", str(source_config), "--root", str(root), "--no-launchd", "--uv", str(failing_uv)
    )
    assert result.returncode != 0
    assert "restauré" in result.stderr
    assert marker.read_text() == "installation d'origine"
    assert os.readlink(root / "current") == f"versions/{REPO_VERSION}"
    assert sorted(p.name for p in (root / "versions").iterdir()) == [REPO_VERSION]


def test_uninstall_keeps_config_and_state_unless_purge(tmp_path: Path, fake_uv: Path, source_config: Path) -> None:
    root = tmp_path / "managed"
    install = run_script(
        INSTALL, tmp_path, "--config", str(source_config), "--root", str(root), "--no-launchd", "--uv", str(fake_uv)
    )
    assert install.returncode == 0, install.stderr

    result = run_script(UNINSTALL, tmp_path, "--root", str(root), "--no-launchd")
    assert result.returncode == 0, result.stderr
    assert not (root / "versions").exists()
    assert not (root / "current").is_symlink()
    assert not (root / "bin").exists()
    assert (root / "config" / "bridge.env").is_file()
    assert (root / "state" / "pornic.json").is_file()

    result = run_script(UNINSTALL, tmp_path, "--root", str(root), "--no-launchd", "--purge")
    assert result.returncode == 0, result.stderr
    assert not root.exists()


def test_uninstall_refuses_a_directory_that_is_not_a_managed_install(tmp_path: Path) -> None:
    precious = tmp_path / "autre-chose"
    precious.mkdir()
    (precious / "fichier.txt").write_text("à garder")
    result = run_script(UNINSTALL, tmp_path, "--root", str(precious), "--no-launchd", "--purge")
    assert result.returncode != 0
    assert (precious / "fichier.txt").read_text() == "à garder"
