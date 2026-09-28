"""Service de l'interface web par le serveur (`BIRDFRAME_WEB_DIST`, `app/web_ui.py`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.web_ui import IMMUTABLE_CACHE, NO_CACHE, WebUi, WebUiError

INDEX_HTML = "<!doctype html><title>bird-frame</title><div id=app></div>"
ASSET_JS = "console.log('bird-frame');"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML)
    (root / "assets" / "index-3f9a1c.js").write_text(ASSET_JS)
    (root / "assets" / "index-3f9a1c.css").write_text("body{}")
    (root / "robots.txt").write_text("User-agent: *\n")
    (tmp_path / "secret.txt").write_text("hors du build")
    return root


@pytest.fixture
def web_client(app_settings: Settings, dist: Path):
    app = create_app(app_settings.model_copy(update={"web_dist": str(dist)}))
    with TestClient(app) as client:
        yield client


def _is_index(resp) -> bool:
    return (
        resp.status_code == 200
        and resp.text == INDEX_HTML
        and resp.headers["content-type"].startswith("text/html")
        and resp.headers["cache-control"] == NO_CACHE
    )


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/species/Erithacus%20rubecula",
        "/stats",
        "/systeme/noeuds/1",
        "/favicon.ico",
        "/deep/path/",
    ],
)
def test_spa_fallback_serves_index(web_client: TestClient, path: str) -> None:
    assert _is_index(web_client.get(path))


def test_hashed_assets_are_immutable(web_client: TestClient) -> None:
    resp = web_client.get("/assets/index-3f9a1c.js")
    assert resp.status_code == 200
    assert resp.text == ASSET_JS
    assert "javascript" in resp.headers["content-type"]
    assert resp.headers["cache-control"] == IMMUTABLE_CACHE
    css = web_client.get("/assets/index-3f9a1c.css")
    assert css.headers["content-type"].startswith("text/css")
    assert css.headers["cache-control"] == IMMUTABLE_CACHE


def test_other_static_files_are_revalidated(web_client: TestClient) -> None:
    resp = web_client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.text == "User-agent: *\n"
    assert resp.headers["cache-control"] == NO_CACHE
    assert _is_index(web_client.get("/index.html"))


def test_missing_asset_is_a_real_404(web_client: TestClient) -> None:
    resp = web_client.get("/assets/index-ancien.js")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_api_routes_keep_priority_and_json_errors(web_client: TestClient) -> None:
    resp = web_client.get("/api/v1/species", params={"limit": 5})
    assert resp.status_code == 200
    assert "species" in resp.json()
    assert web_client.get("/health").json()["status"] == "ok"

    for path in ("/api/v1/nope", "/api", "/api/", "/health/extra"):
        resp = web_client.get(path)
        assert resp.status_code == 404, path
        assert resp.json()["error"] == "not_found", path

    # Un POST sur une route inconnue reste un 404 JSON (pas un 405 dû à un « attrape-tout »),
    # et une méthode non prévue sur une route existante reste un 405.
    assert web_client.post("/api/v1/nope", json={}).json()["error"] == "not_found"
    assert web_client.post("/species/x", json={}).status_code == 404
    assert web_client.post("/api/v1/sites", json={}).status_code == 405


def test_head_is_supported(web_client: TestClient) -> None:
    resp = web_client.head("/species/Turdus%20merula")
    assert resp.status_code == 200
    assert resp.content == b""
    assert resp.headers["cache-control"] == NO_CACHE


def test_path_traversal_never_leaves_the_build(web_client: TestClient, dist: Path) -> None:
    (dist / "lien-sortant.txt").symlink_to(dist.parent / "secret.txt")
    web_ui = web_client.app.state.web_ui
    assert web_ui._existing_file("../secret.txt") is None
    assert web_ui._existing_file("assets/../../secret.txt") is None
    assert web_ui._existing_file("lien-sortant.txt") is None
    assert web_ui._existing_file("a\x00b") is None
    for path in ("/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/lien-sortant.txt"):
        resp = web_client.get(path)
        assert "hors du build" not in resp.text, path


def test_without_web_dist_root_is_a_json_404(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_web_dist_without_index_refuses_to_start(app_settings: Settings, tmp_path: Path) -> None:
    empty = tmp_path / "vide"
    empty.mkdir()
    with pytest.raises(WebUiError, match="index.html"):
        create_app(app_settings.model_copy(update={"web_dist": str(empty)}))
    with pytest.raises(WebUiError):
        WebUi(tmp_path / "inexistant")
