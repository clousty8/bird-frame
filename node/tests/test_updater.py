"""Mise à jour automatique du bridge (`bridge/updater.py`, api-contract.md §12).

Serveur bird-frame mocké avec respx ; installation gérée construite dans `tmp_path` ; `uv` remplacé
par un faux script (BRIDGE_UV) qui crée `.venv/bin/python` (enveloppe de l'interpréteur des tests)
ou échoue. Jamais `local-test/`, jamais le vrai `~/.bird-frame-node`.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
from pathlib import Path

import httpx
import pytest
import respx

from bridge.config import BridgeConfig, ConfigError, load_config
from bridge.heartbeat import _latest_node_version
from bridge.updater import (
    EXIT_CODE_UPDATE_APPLIED,
    RETRY_SAME_VERSION_AFTER_S,
    UpdateError,
    Updater,
    is_newer,
    validate_archive_members,
)

SERVER = "http://server.test"
UPDATE_URL = f"{SERVER}/api/v1/nodes/1/update"
BUNDLE_URL = f"{SERVER}/api/v1/nodes/1/update/bundle"


# --- Fabrication d'archives -------------------------------------------------------------------


def _file(name: str, data: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    return info, data


def make_bundle(version: str, *, code_version: str | None = None, extra: list | None = None) -> bytes:
    entries = [
        _file("VERSION", f"{version}\n".encode()),
        _file("pyproject.toml", b'[project]\nname = "bird-frame-bridge"\nversion = "' + version.encode() + b'"\n'),
        _file("uv.lock", b"version = 1\n"),
        _file("bridge/__init__.py", f'__version__ = "{code_version or version}"\n'.encode()),
        _file("bridge/__main__.py", b"import sys\nprint('bridge factice')\nsys.exit(0)\n"),
    ]
    entries.extend(extra or [])
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, data in entries:
            archive.addfile(info, io.BytesIO(data) if data is not None else None)
    return buffer.getvalue()


def _special(name: str, kind: bytes, linkname: str = "") -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    return info, None


def update_info(bundle: bytes, version: str = "0.2.0", **overrides) -> dict:
    info = {
        "latest_version": version,
        "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "bundle_size": len(bundle),
        "bundle_url": "/api/v1/nodes/1/update/bundle",
    }
    info.update(overrides)
    return info


# --- Installation gérée + faux uv ---------------------------------------------------------------


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "node-root"
    current = root / "versions" / "0.1.0"
    (current / "bridge").mkdir(parents=True)
    (current / "bridge" / "__init__.py").write_text('__version__ = "0.1.0"\n')
    (root / "state").mkdir()
    os.symlink("versions/0.1.0", root / "current")
    return root


def _executable(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def fake_uv_ok(tmp_path: Path) -> Path:
    """Faux `uv` : vérifie les arguments, crée `.venv/bin/python` qui délègue à l'interpréteur
    des tests (pour que l'essai à blanc `python -m bridge --help` s'exécute réellement)."""
    return _executable(
        tmp_path / "fake-uv-ok",
        f"""#!/bin/sh
echo "$PWD $*" >> "{tmp_path}/uv-calls.log"
[ "$*" = "sync --frozen --no-dev" ] || {{ echo "arguments inattendus : $*" >&2; exit 3; }}
mkdir -p .venv/bin
printf '#!/bin/sh\\nexec "{sys.executable}" "$@"\\n' > .venv/bin/python
chmod +x .venv/bin/python
""",
    )


@pytest.fixture
def fake_uv_fail(tmp_path: Path) -> Path:
    return _executable(
        tmp_path / "fake-uv-fail",
        "#!/bin/sh\necho 'error: Failed to download `httpx==0.28.1`' >&2\nexit 1\n",
    )


def make_config(tmp_path: Path, root: Path | None, uv: Path | str = "uv", **overrides) -> BridgeConfig:
    kwargs = dict(
        server_url=SERVER,
        node_id=1,
        secret="s3cr3t",
        site_slug="pornic",
        db_path=str(tmp_path / "birdnet.db"),
        clips_dir=tmp_path,
        state_file=tmp_path / "state.json",
        auto_update=True,
        install_root=root,
        uv_path=str(uv),
    )
    kwargs.update(overrides)
    return BridgeConfig(**kwargs)


class Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


def make_updater(config: BridgeConfig, client: httpx.AsyncClient, root: Path | None, clock=None) -> Updater:
    package_dir = (root / "versions" / "0.1.0" / "bridge") if root else Path(__file__).parent
    return Updater(config, client, current_version="0.1.0", package_dir=package_dir, clock=clock or Clock())


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=f"{SERVER}/api/v1", headers={"Authorization": "Bearer s3cr3t"})


def _current_target(root: Path) -> str:
    return os.readlink(root / "current")


# --- Fonctions pures -------------------------------------------------------------------------


def test_is_newer_is_numeric_semver() -> None:
    assert is_newer("0.2.0", "0.1.0")
    assert is_newer("1.10.0", "1.9.7")
    assert is_newer("1.0.0", "0.99.99")
    assert not is_newer("0.1.0", "0.1.0")
    assert not is_newer("0.0.9", "0.1.0")
    assert not is_newer("0.2.0-rc1", "0.1.0")
    assert not is_newer("v0.2.0", "0.1.0")


@pytest.mark.parametrize(
    ("member", "message"),
    [
        (_file("/etc/evil", b"x")[0], "chemin absolu"),
        (_file("../evil.txt", b"x")[0], "sortant"),
        (_file("bridge/../../evil.txt", b"x")[0], "sortant"),
        (_special("bridge/lien", tarfile.SYMTYPE, "/etc/passwd")[0], "lien"),
        (_special("bridge/dur", tarfile.LNKTYPE, "VERSION")[0], "lien"),
        (_special("bridge/fifo", tarfile.FIFOTYPE)[0], "type de fichier"),
        (_special("bridge/dev", tarfile.CHRTYPE)[0], "type de fichier"),
    ],
)
def test_validate_archive_members_refuses_dangerous_entries(member: tarfile.TarInfo, message: str) -> None:
    with pytest.raises(UpdateError, match=message):
        validate_archive_members([_file("VERSION", b"0.2.0")[0], member])


def test_validate_archive_members_refuses_archive_bombs() -> None:
    huge = tarfile.TarInfo("bridge/huge.bin")
    huge.size = 300 * 1024 * 1024
    with pytest.raises(UpdateError, match="octets"):
        validate_archive_members([huge])


# --- Activation --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_without_auto_update_or_managed_install(tmp_path: Path, root: Path) -> None:
    async with _client() as client:
        with respx.mock(assert_all_called=False) as mock:  # aucune route : tout appel échouerait
            for config in (
                make_config(tmp_path, root, auto_update=False),
                make_config(tmp_path, None),
                make_config(tmp_path, tmp_path / "pas-une-installation"),
            ):
                updater = make_updater(config, client, root)
                assert not updater.enabled
                assert updater.status_payload() == {"state": "disabled", "target_version": None, "error": None}
                assert await updater.check_once() is False
                stop = asyncio.Event()
                await asyncio.wait_for(updater.run(stop), timeout=1)  # rend la main immédiatement
            assert not mock.calls


@pytest.mark.asyncio
async def test_disabled_when_process_runs_outside_versions(tmp_path: Path, root: Path) -> None:
    """Un bridge de développement lancé avec la config de l'installation gérée ne doit jamais
    toucher au lien `current`."""
    async with _client() as client:
        updater = Updater(make_config(tmp_path, root), client, current_version="0.1.0", package_dir=tmp_path)
    assert not updater.enabled
    assert "hors de" in updater.disabled_reason


# --- Cycle de mise à jour ---------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("remote", ["0.1.0", "0.0.9"])
async def test_no_update_when_remote_is_not_newer(
    tmp_path: Path, root: Path, fake_uv_ok: Path, remote: str
) -> None:
    bundle = make_bundle(remote)
    async with _client() as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle, remote)))
            bundle_route = mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert not bundle_route.called
    assert updater.status["state"] == "up_to_date"
    assert _current_target(root) == "versions/0.1.0"
    assert sorted(p.name for p in (root / "versions").iterdir()) == ["0.1.0"]


@pytest.mark.asyncio
async def test_success_switches_current_and_requests_restart(tmp_path: Path, root: Path, fake_uv_ok: Path) -> None:
    (root / "versions" / "0.0.5").mkdir()  # très ancienne version : sera nettoyée
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            bundle_route = mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            stop = asyncio.Event()
            await asyncio.wait_for(updater.run(stop), timeout=30)

    assert stop.is_set()  # toutes les boucles s'arrêtent…
    assert updater.exit_code == EXIT_CODE_UPDATE_APPLIED == 75  # …et le process sortira en 75
    assert bundle_route.calls[0].request.headers["authorization"] == "Bearer s3cr3t"
    assert _current_target(root) == "versions/0.2.0"
    assert (root / "current" / "bridge" / "__init__.py").read_text() == '__version__ = "0.2.0"\n'
    assert (root / "current" / ".venv" / "bin" / "python").exists()
    assert (root / "previous").read_text().strip() == "0.1.0"
    assert sorted(p.name for p in (root / "versions").iterdir()) == ["0.1.0", "0.2.0"]
    assert list((root / "downloads").iterdir()) == []  # fichier temporaire supprimé
    uv_calls = (tmp_path / "uv-calls.log").read_text().split("\n")[0]
    assert uv_calls.endswith("sync --frozen --no-dev")
    assert "versions/0.2.0" in uv_calls


@pytest.mark.asyncio
async def test_wrong_sha256_is_refused_and_not_retried_for_an_hour(
    tmp_path: Path, root: Path, fake_uv_ok: Path
) -> None:
    bundle = make_bundle("0.2.0")
    clock = Clock()
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(
                return_value=httpx.Response(200, json=update_info(bundle, bundle_sha256="0" * 64))
            )
            bundle_route = mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root, clock)

            assert await updater.check_once() is False
            assert updater.status["state"] == "failed"
            assert updater.status["target_version"] == "0.2.0"
            assert "SHA-256" in updater.status["error"]
            assert bundle_route.call_count == 1

            clock.now += RETRY_SAME_VERSION_AFTER_S - 60
            assert await updater.check_once() is False
            assert bundle_route.call_count == 1  # pas de nouvel essai avant 1 h
            assert updater.status["state"] == "failed"

            # Mémorisé sur disque : un process relancé ne réessaie pas non plus.
            fresh = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root, clock)
            assert await fresh.check_once() is False
            assert bundle_route.call_count == 1

            clock.now += 120
            assert await updater.check_once() is False
            assert bundle_route.call_count == 2  # plus d'une heure après : nouvel essai

    assert _current_target(root) == "versions/0.1.0"
    assert not (root / "versions" / "0.2.0").exists()
    assert not (root / "previous").exists()
    assert not (tmp_path / "uv-calls.log").exists()  # jamais allé jusqu'à uv
    assert json.loads((root / "state" / "updater.json").read_text())["failures"]["0.2.0"]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "evil",
    [
        [_file("../evil.txt", b"pwned")],
        [_file("/tmp/bird-frame-evil.txt", b"pwned")],
        [_special("bridge/lien", tarfile.SYMTYPE, "../../../evil.txt")],
        [_special("bridge/dur", tarfile.LNKTYPE, "../../evil.txt")],
    ],
    ids=["dotdot", "absolu", "symlink", "hardlink"],
)
async def test_malicious_archive_is_refused(tmp_path: Path, root: Path, fake_uv_ok: Path, evil: list) -> None:
    bundle = make_bundle("0.2.0", extra=evil)
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False

    assert updater.status["state"] == "failed"
    assert "archive refusée" in updater.status["error"]
    assert not (root / "versions" / "0.2.0").exists()
    assert not (root / "evil.txt").exists() and not (tmp_path / "evil.txt").exists()
    assert not Path("/tmp/bird-frame-evil.txt").exists()
    assert _current_target(root) == "versions/0.1.0"


@pytest.mark.asyncio
async def test_bundle_content_must_match_announced_version(tmp_path: Path, root: Path, fake_uv_ok: Path) -> None:
    bundle = make_bundle("0.2.0", code_version="0.1.0")  # VERSION dit 0.2.0, le code dit 0.1.0
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert "__version__" in updater.status["error"]
    assert not (root / "versions" / "0.2.0").exists()


@pytest.mark.asyncio
async def test_uv_failure_keeps_old_version_and_reports_status(
    tmp_path: Path, root: Path, fake_uv_fail: Path, caplog
) -> None:
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_fail), client, root)
            with caplog.at_level("ERROR", logger="bridge.updater"):
                assert await updater.check_once() is False

    assert updater.exit_code is None
    assert _current_target(root) == "versions/0.1.0"
    assert not (root / "versions" / "0.2.0").exists()  # dossier partiel supprimé
    assert not (root / "previous").exists()
    status = updater.status_payload()
    assert status["state"] == "failed"
    assert status["target_version"] == "0.2.0"
    assert "uv sync a échoué (code 1)" in status["error"]
    assert "Failed to download" in status["error"]
    assert any(r.levelname == "ERROR" and "uv sync" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_missing_uv_binary_is_a_clear_failure(tmp_path: Path, root: Path) -> None:
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, tmp_path / "pas-de-uv"), client, root)
            assert await updater.check_once() is False
    assert "impossible de lancer" in updater.status["error"]
    assert _current_target(root) == "versions/0.1.0"


@pytest.mark.asyncio
async def test_stop_during_uv_sync_aborts_cleanly(tmp_path: Path, root: Path) -> None:
    """SIGTERM (stop_event) pendant un `uv sync` interminable : l'installation est abandonnée tout de
    suite, le sous-process tué, le dossier partiel supprimé, `current` intact, pas de code 75."""
    started = tmp_path / "uv-started"
    slow_uv = tmp_path / "slow-uv"
    slow_uv.write_text(f'#!/bin/sh\necho $$ > "{started}"\nexec sleep 60\n')
    slow_uv.chmod(0o755)
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, slow_uv), client, root)
            stop = asyncio.Event()
            task = asyncio.create_task(updater.run(stop))
            for _ in range(200):
                if started.exists() and started.read_text().strip():
                    break
                await asyncio.sleep(0.02)
            assert (root / "versions" / "0.2.0").exists()  # installation en cours
            stop.set()
            await asyncio.wait_for(task, timeout=5)

    uv_pid = int(started.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(uv_pid, 0)  # sous-process tué (et récolté)
    assert updater.exit_code is None
    assert not (root / "versions" / "0.2.0").exists()
    assert _current_target(root) == "versions/0.1.0"
    assert list((root / "downloads").iterdir()) == []


@pytest.mark.asyncio
async def test_unexpected_error_during_install_is_a_recorded_failure(
    tmp_path: Path, root: Path, fake_uv_ok: Path
) -> None:
    """Une archive dont VERSION n'est pas de l'UTF-8 (UnicodeDecodeError, pas une UpdateError) :
    échec propre, dossier nettoyé, échec mémorisé comme les autres."""
    bundle = make_bundle("0.2.0")
    raw = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as src,
        tarfile.open(fileobj=raw, mode="w:gz") as dst,
    ):
        for member in src.getmembers():
            data = src.extractfile(member).read()
            if member.name == "VERSION":
                data = b"\xff\xfe\x00"
                member.size = len(data)
            dst.addfile(member, io.BytesIO(data))
    bundle = raw.getvalue()
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert updater.status["state"] == "failed"
    assert "erreur inattendue" in updater.status["error"]
    assert not (root / "versions" / "0.2.0").exists()
    assert "0.2.0" in json.loads((root / "state" / "updater.json").read_text())["failures"]


@pytest.mark.asyncio
async def test_version_rolled_back_by_supervisor_is_never_retried(
    tmp_path: Path, root: Path, fake_uv_ok: Path
) -> None:
    (root / "state" / "rolled-back-versions").write_text("0.2.0\n")
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle)))
            bundle_route = mock.get(BUNDLE_URL).mock(return_value=httpx.Response(200, content=bundle))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
            updater.notify_latest_version("0.2.0")
            assert not updater._wake.is_set()
    assert not bundle_route.called
    assert updater.status["state"] == "failed"
    assert "annulée par le superviseur" in updater.status["error"]


@pytest.mark.asyncio
async def test_bundle_url_on_another_origin_is_refused(tmp_path: Path, root: Path, fake_uv_ok: Path) -> None:
    bundle = make_bundle("0.2.0")
    async with _client() as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(UPDATE_URL).mock(
                return_value=httpx.Response(
                    200, json=update_info(bundle, bundle_url="https://ailleurs.example/bundle.tar.gz")
                )
            )
            other = mock.get("https://ailleurs.example/bundle.tar.gz").mock(return_value=httpx.Response(200))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert not other.called  # le secret du nœud ne part jamais vers un autre hôte
    assert "hors de l'origine" in updater.status["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(404, json={"error": "node_bundle_not_configured", "message": "…"}), "ne publie pas"),
        (httpx.Response(503, json={"error": "node_bundle_unavailable", "message": "…"}), "503"),
        (httpx.Response(200, json={"latest_version": "latest"}), "réponse invalide"),
    ],
)
async def test_check_failures_are_reported_without_touching_anything(
    tmp_path: Path, root: Path, fake_uv_ok: Path, response: httpx.Response, expected: str
) -> None:
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(return_value=response)
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert updater.status["state"] == "check_failed"
    assert expected in updater.status["error"]
    assert _current_target(root) == "versions/0.1.0"


@pytest.mark.asyncio
async def test_network_error_is_a_check_failure(tmp_path: Path, root: Path, fake_uv_ok: Path) -> None:
    async with _client() as client:
        with respx.mock() as mock:
            mock.get(UPDATE_URL).mock(side_effect=httpx.ConnectError("refusé"))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok), client, root)
            assert await updater.check_once() is False
    assert updater.status["state"] == "check_failed"
    assert "injoignable" in updater.status["error"]


@pytest.mark.asyncio
async def test_heartbeat_hint_wakes_the_loop_early(tmp_path: Path, root: Path, fake_uv_ok: Path) -> None:
    bundle = make_bundle("0.1.0")
    async with _client() as client:
        with respx.mock() as mock:
            route = mock.get(UPDATE_URL).mock(return_value=httpx.Response(200, json=update_info(bundle, "0.1.0")))
            updater = make_updater(make_config(tmp_path, root, fake_uv_ok, update_interval_s=3600), client, root)
            stop = asyncio.Event()
            task = asyncio.create_task(updater.run(stop))
            await _until(lambda: route.call_count == 1)  # vérification au démarrage

            updater.notify_latest_version("0.1.0")  # pas plus récent : aucun effet
            await asyncio.sleep(0.1)
            assert route.call_count == 1

            updater.notify_latest_version("0.3.0")  # annoncé par le heartbeat : vérification immédiate
            await _until(lambda: route.call_count == 2)

            stop.set()
            await asyncio.wait_for(task, timeout=1)
    assert updater.exit_code is None


async def _until(condition, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        assert loop.time() < deadline, "condition jamais remplie"
        await asyncio.sleep(0.01)


def test_latest_node_version_parsing() -> None:
    assert _latest_node_version(httpx.Response(200, json={"latest_node_version": "0.2.0"})) == "0.2.0"
    assert _latest_node_version(httpx.Response(200, json={"latest_node_version": None})) is None
    assert _latest_node_version(httpx.Response(200, json={"server_time_utc": "x"})) is None
    assert _latest_node_version(httpx.Response(200, content=b"pas du json")) is None


# --- Configuration ------------------------------------------------------------------------------


def _write_env(tmp_path: Path, **extra: str) -> Path:
    lines = {
        "BRIDGE_SERVER_URL": "http://localhost:8090",
        "BRIDGE_NODE_ID": "1",
        "BRIDGE_SECRET": "x",
        "BRIDGE_SITE_SLUG": "pornic",
        "BRIDGE_DB_PATH": str(tmp_path / "birdnet.db"),
        "BRIDGE_CLIPS_DIR": str(tmp_path),
        "BRIDGE_STATE_FILE": str(tmp_path / "state.json"),
        **extra,
    }
    path = tmp_path / "bridge.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in lines.items()))
    return path


def test_config_update_defaults_and_values(tmp_path: Path) -> None:
    defaults = load_config(_write_env(tmp_path))
    assert (defaults.auto_update, defaults.install_root, defaults.update_interval_s, defaults.uv_path) == (
        False,
        None,
        600.0,
        "uv",
    )
    config = load_config(
        _write_env(
            tmp_path,
            BRIDGE_AUTO_UPDATE="1",
            BRIDGE_INSTALL_ROOT=str(tmp_path / "root"),
            BRIDGE_UPDATE_INTERVAL_S="120",
            BRIDGE_UV="/opt/homebrew/bin/uv",
        )
    )
    assert config.auto_update is True
    assert config.install_root == tmp_path / "root"
    assert config.update_interval_s == 120.0
    assert config.uv_path == "/opt/homebrew/bin/uv"


@pytest.mark.parametrize(
    "extra",
    [{"BRIDGE_INSTALL_ROOT": "relatif/root"}, {"BRIDGE_UPDATE_INTERVAL_S": "1"}, {"BRIDGE_AUTO_UPDATE": "oui"}],
)
def test_config_update_invalid_values(tmp_path: Path, extra: dict) -> None:
    with pytest.raises(ConfigError):
        load_config(_write_env(tmp_path, **extra))
