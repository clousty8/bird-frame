"""Mise à jour des nœuds (contrat §12) : `GET /nodes/{id}/update`, `/update/bundle`, heartbeat.

Le bundle est construit par le vrai `scripts/build_node_bundle.py` à partir du vrai `node/` du
dépôt (lecture seule), dans `tmp_path`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import logging
import sys
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.version import __version__
from tests.conftest import ADMIN_TOKEN

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "bird_frame_build_node_bundle", REPO_ROOT / "scripts" / "build_node_bundle.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()


@contextmanager
def captured_logs(logger_name: str, level: int) -> Iterator[list[logging.LogRecord]]:
    """Capture directe sur un logger nommé. `caplog` ne convient pas ici : les migrations Alembic
    lancées au démarrage de l'app (`fileConfig` de alembic.ini) retirent les handlers du logger
    racine, dont celui de `caplog`, quand l'app est créée pendant la phase « call » du test."""
    records: list[logging.LogRecord] = []
    handler = logging.Handler(level)
    handler.emit = records.append  # type: ignore[method-assign]
    target = logging.getLogger(logger_name)
    previous_level = target.level
    target.addHandler(handler)
    target.setLevel(level)
    try:
        yield records
    finally:
        target.removeHandler(handler)
        target.setLevel(previous_level)


@pytest.fixture
def bundle_path(tmp_path: Path) -> Path:
    return builder.build_bundle(REPO_ROOT / "node", __version__, tmp_path / "bundle")


def _client(app_settings: Settings, **overrides):
    return TestClient(create_app(app_settings.model_copy(update=overrides)))


def _register(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Test node",
            "timezone": "Europe/Paris",
            "lat": 47.1155,
            "lon": -2.1046,
            "auto_main_name": False,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _heartbeat_body(**extra) -> dict:
    body = {
        "sent_at_utc": "2026-09-28T10:00:00Z",
        "bridge_version": "0.0.9",
        "birdnet_go_version": "20260823",
        "birdnet_go_reachable": True,
        "birdnet_go_pid_alive": True,
        "mic_device_name": None,
        "mic_healthy": None,
        "disk_free_pct": 50.0,
        "node_db_max_id": 10,
        "dynamic_thresholds_snapshot": None,
    }
    body.update(extra)
    return body


# --- Bundle (script de construction) -----------------------------------------------------------


def test_bundle_content_is_the_bridge_without_tests_or_caches(bundle_path: Path) -> None:
    assert bundle_path.name == f"node-bundle-{__version__}.tar.gz"
    with tarfile.open(bundle_path, "r:gz") as archive:
        names = archive.getnames()
        assert archive.extractfile("VERSION").read().decode().strip() == __version__
        members = archive.getmembers()
    assert {
        "VERSION",
        "pyproject.toml",
        "uv.lock",
        "bridge/__init__.py",
        "bridge/__main__.py",
    } <= set(names)
    assert all(m.isfile() and m.uid == 0 and m.mode == 0o644 for m in members)
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert not [n for n in names if n.startswith(("tests/", "config/", "state/")) or "/tests/" in n]
    sidecar = bundle_path.with_name(bundle_path.name + ".sha256").read_text()
    assert sidecar.split()[0] == hashlib.sha256(bundle_path.read_bytes()).hexdigest()


def test_bundle_is_reproducible(tmp_path: Path) -> None:
    first = builder.build_bundle(REPO_ROOT / "node", __version__, tmp_path / "a")
    second = builder.build_bundle(REPO_ROOT / "node", __version__, tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()


def test_bundle_refuses_version_mismatch(tmp_path: Path) -> None:
    with pytest.raises(builder.BundleError, match="VERSION dit 9.9.9"):
        builder.build_bundle(REPO_ROOT / "node", "9.9.9", tmp_path / "out")


# --- Routes -----------------------------------------------------------------------------------


def test_update_info_and_bundle_download(app_settings: Settings, bundle_path: Path) -> None:
    with _client(app_settings, node_bundle=str(bundle_path)) as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        node_id = node["node_id"]

        resp = client.get(f"/api/v1/nodes/{node_id}/update", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        payload = bundle_path.read_bytes()
        assert data == {
            "latest_version": __version__,
            "bundle_sha256": hashlib.sha256(payload).hexdigest(),
            "bundle_size": len(payload),
            "bundle_url": f"/api/v1/nodes/{node_id}/update/bundle",
        }

        resp = client.get(data["bundle_url"], headers=headers)
        assert resp.status_code == 200
        assert resp.content == payload
        assert resp.headers["content-type"] == "application/gzip"
        assert resp.headers["x-bundle-sha256"] == data["bundle_sha256"]

        # Toute requête authentifiée met à jour last_seen_at (§2.1), comme l'ingestion.
        nodes = client.get("/api/v1/nodes").json()["nodes"]
        assert nodes[0]["last_seen_at"] is not None


@pytest.mark.parametrize("suffix", ["", "/bundle"])
def test_update_routes_require_node_bearer(
    app_settings: Settings, bundle_path: Path, suffix: str
) -> None:
    with _client(app_settings, node_bundle=str(bundle_path)) as client:
        node = _register(client)
        url = f"/api/v1/nodes/{node['node_id']}/update{suffix}"

        resp = client.get(url)
        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"
        assert resp.headers["www-authenticate"] == "Bearer"

        resp = client.get(url, headers={"Authorization": "Bearer pas-le-bon-secret"})
        assert resp.status_code == 401

        resp = client.get(
            f"/api/v1/nodes/999/update{suffix}",
            headers={"Authorization": f"Bearer {node['bridge_shared_secret']}"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "node_not_found"


@pytest.mark.parametrize("suffix", ["", "/bundle"])
def test_update_routes_404_when_no_bundle_configured(app_settings: Settings, suffix: str) -> None:
    with _client(app_settings, node_bundle="") as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        # auth d'abord : sans Bearer, 401 même sans bundle
        assert client.get(f"/api/v1/nodes/{node['node_id']}/update{suffix}").status_code == 401
        resp = client.get(f"/api/v1/nodes/{node['node_id']}/update{suffix}", headers=headers)
        assert resp.status_code == 404
        assert resp.json()["error"] == "node_bundle_not_configured"


def _tampered_bundle(path: Path, version: str) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        data = f"{version}\n".encode()
        info = tarfile.TarInfo("VERSION")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    path.write_bytes(buffer.getvalue())


def test_bundle_with_other_version_is_unavailable(app_settings: Settings, tmp_path: Path) -> None:
    bad = tmp_path / "node-bundle-x.tar.gz"
    _tampered_bundle(bad, "9.9.9")
    with (
        captured_logs("bird_frame.main", logging.ERROR) as records,
        _client(app_settings, node_bundle=str(bad)) as client,
    ):
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        resp = client.get(f"/api/v1/nodes/{node['node_id']}/update", headers=headers)
        assert resp.status_code == 503
        assert resp.json()["error"] == "node_bundle_unavailable"
        assert "9.9.9" in resp.json()["message"]
        hb = client.post(
            f"/api/v1/nodes/{node['node_id']}/heartbeat", headers=headers, json=_heartbeat_body()
        )
        assert hb.json()["latest_node_version"] is None
    assert any("Bundle du bridge inutilisable" in r.getMessage() for r in records)


def test_bundle_with_wrong_sidecar_sha_is_unavailable(
    app_settings: Settings, bundle_path: Path
) -> None:
    bundle_path.with_name(bundle_path.name + ".sha256").write_text("0" * 64 + "  x\n")
    with _client(app_settings, node_bundle=str(bundle_path)) as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        resp = client.get(f"/api/v1/nodes/{node['node_id']}/update/bundle", headers=headers)
        assert resp.status_code == 503
        assert "SHA-256" in resp.json()["message"]


# --- Heartbeat : latest_node_version + update_status ------------------------------------------


@pytest.mark.parametrize("with_bundle", [True, False])
def test_heartbeat_reports_latest_node_version_only_with_bundle(
    app_settings: Settings, bundle_path: Path, with_bundle: bool
) -> None:
    with _client(app_settings, node_bundle=str(bundle_path) if with_bundle else "") as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        resp = client.post(
            f"/api/v1/nodes/{node['node_id']}/heartbeat", headers=headers, json=_heartbeat_body()
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["latest_node_version"] == (__version__ if with_bundle else None)
        assert "server_time_utc" in resp.json()


def test_heartbeat_update_status_is_stored_exposed_and_logged(app_settings: Settings) -> None:
    with _client(app_settings) as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        url = f"/api/v1/nodes/{node['node_id']}/heartbeat"

        # Bridge antérieur : pas de champ → null.
        assert client.post(url, headers=headers, json=_heartbeat_body()).status_code == 200
        assert client.get("/api/v1/nodes").json()["nodes"][0]["update_status"] is None

        failed = {
            "state": "failed",
            "target_version": "0.2.0",
            "error": "uv sync a échoué (code 1)",
        }
        with captured_logs("bird_frame.ingest", logging.WARNING) as records:
            for _ in range(2):  # deux heartbeats identiques → un seul WARNING
                assert (
                    client.post(
                        url, headers=headers, json=_heartbeat_body(update_status=failed)
                    ).status_code
                    == 200
                )
        warnings = [r for r in records if "mise à jour du bridge" in r.getMessage()]
        assert len(warnings) == 1
        assert "0.2.0" in warnings[0].getMessage()

        status = client.get("/api/v1/nodes").json()["nodes"][0]["update_status"]
        assert status == failed
        now = client.get("/api/v1/sites/pornic/now").json()
        assert now["node_status"]["update_status"] == failed

        ok = {"state": "up_to_date", "target_version": None, "error": None}
        assert (
            client.post(url, headers=headers, json=_heartbeat_body(update_status=ok)).status_code
            == 200
        )
        assert client.get("/api/v1/nodes").json()["nodes"][0]["update_status"] == ok


def test_heartbeat_update_status_validation(app_settings: Settings) -> None:
    with _client(app_settings) as client:
        node = _register(client)
        headers = {"Authorization": f"Bearer {node['bridge_shared_secret']}"}
        url = f"/api/v1/nodes/{node['node_id']}/heartbeat"
        too_long = {"state": "failed", "target_version": "0.2.0", "error": "x" * 2001}
        assert (
            client.post(
                url, headers=headers, json=_heartbeat_body(update_status=too_long)
            ).status_code
            == 422
        )
        # état inconnu d'un bridge plus récent : accepté tel quel (compatibilité ascendante)
        future = {"state": "some_future_state", "target_version": None, "error": None}
        assert (
            client.post(
                url, headers=headers, json=_heartbeat_body(update_status=future)
            ).status_code
            == 200
        )
