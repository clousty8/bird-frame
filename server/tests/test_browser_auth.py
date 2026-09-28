"""Session navigateur à mot de passe unique — contrat §2.2.

Couvre : hash scrypt + script de génération, jeton signé (expiration, falsification,
changement de secret), login/logout/me, anti-force brute, chaque route protégée (401
sans session, fonctionnelle avec), routes publiques, contrôle d'`Origin`, mode dev sans
hash et refus de démarrer en production. L'énumération exhaustive des routes est dans
`tests/test_route_protection.py`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.browser_auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_S,
    ConfigError,
    build_browser_auth,
    derive_signing_key,
    sign_session_token,
    verify_session_token,
)
from app.config import Settings
from app.main import create_app
from app.passwords import (
    PasswordHashError,
    hash_password,
    parse_password_hash,
    verify_password,
)
from tests.conftest import ADMIN_TOKEN, make_detection, make_wav_bytes

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_DIR.parent

PASSWORD = "mésange-charbonnière-42"
# n réduit pour la vitesse des tests : le format porte ses paramètres, la vérification
# utilise ceux du hash (la production utilise n=2**15, valeur par défaut de hash_password).
PASSWORD_HASH = hash_password(PASSWORD, n=2**10)
SESSION_SECRET = "secret-de-session-de-test-au-moins-32-caracteres"
SAME_ORIGIN = "http://testserver"


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def auth_settings(app_settings: Settings) -> Settings:
    return app_settings.model_copy(
        update={"ui_password_hash": PASSWORD_HASH, "session_secret": SESSION_SECRET}
    )


@pytest.fixture
def auth_app(auth_settings: Settings):
    return create_app(auth_settings)


@pytest.fixture
def anon(auth_app) -> TestClient:
    """Client sans session sur une application où l'authentification est active."""
    with TestClient(auth_app) as c:
        yield c


def register_site(client: TestClient) -> dict:
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
    node = resp.json()
    return {**node, "headers": {"Authorization": f"Bearer {node['bridge_shared_secret']}"}}


@pytest.fixture
def site(anon: TestClient) -> dict:
    return register_site(anon)


def login(client: TestClient, password: str = PASSWORD, **kwargs):
    return client.post("/api/v1/auth/login", json={"password": password}, **kwargs)


def set_cookie_header(resp) -> str:
    values = resp.headers.get_list("set-cookie")
    assert len(values) == 1, values
    return values[0]


def ingest_one_clip(client: TestClient, site: dict) -> int:
    """Une détection + son clip (via l'API d'ingestion, Bearer du nœud) ; renvoie kept_clip_id."""
    node_id = site["node_id"]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=site["headers"],
        json={
            "since_id": 0,
            "node_max_id": 1,
            "detections": [make_detection(1, has_clip=True, clip_name="2026/09/clip1.wav")],
        },
    )
    assert resp.status_code == 200, resp.text
    up = client.post(
        f"/api/v1/nodes/{node_id}/clips/1",
        headers=site["headers"],
        data={"clip_name": "2026/09/clip1.wav"},
        files={"audio": ("1.wav", make_wav_bytes(), "audio/wav")},
    )
    assert up.status_code == 201, up.text
    return up.json()["kept_clip_id"]


# ---- Hash du mot de passe ------------------------------------------------------------


def test_hash_password_format_and_roundtrip():
    encoded = hash_password("un mot de passe")
    scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
    assert (scheme, n, r, p) == ("scrypt", "32768", "8", "1")
    assert salt_b64 and hash_b64
    assert verify_password("un mot de passe", encoded)
    assert not verify_password("un mot de passE", encoded)
    # Sel aléatoire : deux hashs du même mot de passe diffèrent.
    assert hash_password("un mot de passe", n=2**10) != hash_password("un mot de passe", n=2**10)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "bcrypt$10$abc",
        "scrypt$32768$8$1$c2Fs",  # champ manquant
        "scrypt$1000$8$1$c2Fsc2Fsc2Fsc2Fs$aGFzaGhhc2hoYXNoaGFzaA==",  # n pas puissance de 2
        "scrypt$32768$8$1$pas-du-base64!$aGFzaGhhc2hoYXNoaGFzaA==",
        "scrypt$x$8$1$c2Fsc2Fsc2Fsc2Fs$aGFzaGhhc2hoYXNoaGFzaA==",
    ],
)
def test_parse_password_hash_rejects_malformed(bad: str):
    with pytest.raises(PasswordHashError):
        parse_password_hash(bad)


def test_hash_password_script_prints_a_verifiable_hash():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "hash_password.py"), "--stdin"],
        input="un-mot-de-passe-assez-long\n",
        capture_output=True,
        text=True,
        check=True,
    )
    encoded = result.stdout.strip()
    assert encoded.startswith("scrypt$32768$8$1$")
    # Le saut de ligne final de l'entrée ne fait pas partie du mot de passe.
    assert verify_password("un-mot-de-passe-assez-long", encoded)


# ---- Jeton de session ----------------------------------------------------------------


def test_session_token_roundtrip_expiration_and_forgery():
    key = derive_signing_key(SESSION_SECRET, PASSWORD_HASH)
    now = time.time()
    token = sign_session_token(key, now)
    assert verify_session_token(key, token, now)
    assert verify_session_token(key, token, now + SESSION_MAX_AGE_S - 5)
    assert not verify_session_token(key, token, now + SESSION_MAX_AGE_S + 5)

    version, exp, nonce, sig = token.split(".")
    # Expiration repoussée à la main : la signature ne correspond plus.
    assert not verify_session_token(key, f"{version}.{int(exp) + 3600}.{nonce}.{sig}", now)
    assert not verify_session_token(key, f"{version}.{exp}.{nonce}.{sig[:-2]}AA", now)
    assert not verify_session_token(key, "n'importe quoi", now)
    assert not verify_session_token(key, "v1.abc.def.ghi", now)

    # Changer le secret, ou le mot de passe, invalide toutes les sessions.
    other_secret = derive_signing_key(SESSION_SECRET + "-change", PASSWORD_HASH)
    other_password = derive_signing_key(SESSION_SECRET, hash_password("autre", n=2**10))
    assert not verify_session_token(other_secret, token, now)
    assert not verify_session_token(other_password, token, now)


# ---- Login / logout / me -------------------------------------------------------------


def test_me_reports_anonymous_when_auth_enabled(anon: TestClient):
    resp = anon.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "auth_enabled": True}
    assert resp.headers["cache-control"] == "no-store"


def test_login_ok_sets_signed_session_cookie(anon: TestClient):
    resp = login(anon)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"authenticated": True, "auth_enabled": True}

    cookie = set_cookie_header(resp)
    attributes = [a.strip().lower() for a in cookie.split(";")]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=v1.")
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert "path=/" in attributes
    assert f"max-age={SESSION_MAX_AGE_S}" in attributes
    assert "secure" not in attributes  # requête en http

    assert anon.get("/api/v1/auth/me").json() == {"authenticated": True, "auth_enabled": True}


def test_login_over_https_sets_secure_cookie(auth_app):
    with TestClient(auth_app, base_url="https://testserver") as c:
        resp = login(c)
        assert resp.status_code == 200
        assert "secure" in [a.strip().lower() for a in set_cookie_header(resp).split(";")]


def test_login_wrong_password_is_rejected_without_cookie(anon: TestClient):
    resp = login(anon, "mauvais mot de passe")
    assert resp.status_code == 401
    assert resp.json() == {
        "error": "invalid_password",
        "message": "Mot de passe incorrect.",
        "details": None,
    }
    assert "set-cookie" not in resp.headers
    assert anon.get("/api/v1/auth/me").json()["authenticated"] is False


def test_login_validates_body(anon: TestClient):
    resp = anon.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


def test_logout_clears_cookie_and_session(anon: TestClient):
    assert login(anon).status_code == 200
    resp = anon.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "auth_enabled": True}
    cookie = set_cookie_header(resp).lower()
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "max-age=0" in cookie
    assert anon.get("/api/v1/auth/me").json()["authenticated"] is False
    # Idempotent : se déconnecter sans session n'est pas une erreur.
    assert anon.post("/api/v1/auth/logout").status_code == 200


# ---- Anti-force brute ----------------------------------------------------------------


def test_rate_limit_blocks_ip_after_five_failures_for_five_minutes(auth_app, anon: TestClient):
    fake_now = [1000.0]
    auth_app.state.browser_auth.limiter.clock = lambda: fake_now[0]

    for _ in range(5):
        assert login(anon, "mauvais").status_code == 401

    blocked = login(anon)  # même le bon mot de passe est refusé pendant le blocage
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"] == "too_many_attempts"
    assert body["details"]["retry_after_s"] == 300
    assert blocked.headers["retry-after"] == "300"
    assert "set-cookie" not in blocked.headers

    # Une autre IP n'est pas concernée.
    with TestClient(auth_app, client=("203.0.113.9", 4242)) as other_ip:
        assert login(other_ip).status_code == 200

    fake_now[0] += 299
    assert login(anon).status_code == 429
    fake_now[0] += 2
    assert login(anon).status_code == 200


def test_rate_limit_window_is_five_minutes_and_success_resets(auth_app, anon: TestClient):
    fake_now = [1000.0]
    auth_app.state.browser_auth.limiter.clock = lambda: fake_now[0]

    for _ in range(4):
        assert login(anon, "mauvais").status_code == 401
    # Les 4 échecs sortent de la fenêtre de 5 min : le compteur repart de zéro.
    fake_now[0] += 301
    for _ in range(4):
        assert login(anon, "mauvais").status_code == 401
    # Une connexion réussie remet aussi le compteur à zéro.
    assert login(anon).status_code == 200
    for _ in range(4):
        assert login(anon, "mauvais").status_code == 401
    assert login(anon).status_code == 200


# ---- Cookie expiré ou falsifié -------------------------------------------------------


def _put_rule(client: TestClient, **kwargs):
    return client.put(
        "/api/v1/sites/pornic/species-rules/Erithacus%20rubecula",
        json={"rule": "impossible"},
        **kwargs,
    )


def test_expired_session_is_rejected(anon: TestClient, site: dict):
    key = derive_signing_key(SESSION_SECRET, PASSWORD_HASH)
    expired = sign_session_token(key, time.time() - SESSION_MAX_AGE_S - 60)
    anon.cookies.set(SESSION_COOKIE_NAME, expired)
    assert anon.get("/api/v1/auth/me").json()["authenticated"] is False
    resp = _put_rule(anon)
    assert resp.status_code == 401
    assert resp.json()["error"] == "auth_required"


@pytest.mark.parametrize(
    "forge",
    [
        lambda token: token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB"),
        lambda token: "v1.9999999999.nonce.signature",
        lambda token: sign_session_token(
            derive_signing_key("un-autre-secret-de-session-de-32-caracteres", PASSWORD_HASH),
            time.time(),
        ),
        lambda token: "",
    ],
    ids=["signature-alteree", "jeton-invente", "autre-secret", "vide"],
)
def test_forged_session_cookie_is_rejected(anon: TestClient, site: dict, forge):
    assert login(anon).status_code == 200
    genuine = anon.cookies.get(SESSION_COOKIE_NAME)
    anon.cookies.clear()
    anon.cookies.set(SESSION_COOKIE_NAME, forge(genuine))
    assert anon.get("/api/v1/auth/me").json()["authenticated"] is False
    assert _put_rule(anon).status_code == 401


def test_changing_session_secret_invalidates_existing_sessions(auth_settings: Settings, site):
    with TestClient(create_app(auth_settings)) as first:
        assert login(first).status_code == 200
        token = first.cookies.get(SESSION_COOKIE_NAME)
    rotated = auth_settings.model_copy(update={"session_secret": SESSION_SECRET + "-rotation"})
    with TestClient(create_app(rotated), cookies={SESSION_COOKIE_NAME: token}) as second:
        assert second.get("/api/v1/auth/me").json()["authenticated"] is False


# ---- Routes protégées ----------------------------------------------------------------

PROTECTED_REQUESTS = [
    ("PUT", "/api/v1/sites/pornic/species-rules/Erithacus%20rubecula", {"rule": "impossible"}),
    ("DELETE", "/api/v1/sites/pornic/species-rules/Erithacus%20rubecula", None),
    ("POST", "/api/v1/sites/pornic/reviews", {"detection_id": 1, "kind": "correct"}),
    ("POST", "/api/v1/sites/pornic/false-negatives", {"scientific_name": "Strix aluco"}),
    ("DELETE", "/api/v1/sites/pornic/dynamic-thresholds/Erithacus%20rubecula", None),
    ("GET", "/api/v1/recordings/1/audio", None),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_REQUESTS)
def test_each_protected_route_requires_a_session(anon: TestClient, site: dict, method, path, body):
    ingest_one_clip(anon, site)
    resp = anon.request(method, path, json=body)
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"] == "auth_required"
    assert resp.json()["details"] is None


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_REQUESTS)
def test_protected_route_checks_session_before_anything_else(anon: TestClient, method, path, body):
    # Site inconnu, corps absent : la session est vérifiée d'abord (401, pas 404/422).
    resp = anon.request(method, path.replace("/pornic/", "/inconnu/"))
    assert resp.status_code == 401
    assert resp.json()["error"] == "auth_required"


def test_protected_routes_work_with_a_session(anon: TestClient, site: dict):
    kept_clip_id = ingest_one_clip(anon, site)
    assert login(anon).status_code == 200

    headers = {"Origin": SAME_ORIGIN}
    put = _put_rule(anon, headers=headers)
    assert put.status_code == 200, put.text
    assert anon.delete(
        "/api/v1/sites/pornic/species-rules/Erithacus%20rubecula", headers=headers
    ).status_code == 200

    detection_id = anon.get("/api/v1/sites/pornic/detections").json()["detections"][0]["detection_id"]
    review = anon.post(
        "/api/v1/sites/pornic/reviews",
        json={"detection_id": detection_id, "kind": "correct"},
        headers=headers,
    )
    assert review.status_code == 201, review.text
    fn = anon.post(
        "/api/v1/sites/pornic/false-negatives",
        json={"scientific_name": "Strix aluco"},
        headers=headers,
    )
    assert fn.status_code == 201, fn.text
    # Aucun seuil dynamique dans le dernier heartbeat : 404 métier, mais plus 401.
    reset = anon.delete(
        "/api/v1/sites/pornic/dynamic-thresholds/Erithacus%20rubecula", headers=headers
    )
    assert reset.status_code == 404
    assert reset.json()["error"] == "threshold_not_found"

    audio = anon.get(f"/api/v1/recordings/{kept_clip_id}/audio")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    # Réponse soumise à session : jamais en cache partagé.
    assert audio.headers["cache-control"].startswith("private")
    ranged = anon.get(f"/api/v1/recordings/{kept_clip_id}/audio", headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206


def test_public_routes_stay_public_when_auth_is_enabled(anon: TestClient, site: dict):
    kept_clip_id = ingest_one_clip(anon, site)
    for path in [
        "/health",
        "/api/v1/sites",
        "/api/v1/nodes",
        "/api/v1/species",
        "/api/v1/species/Erithacus%20rubecula",
        "/api/v1/species/Erithacus%20rubecula/sites/pornic/top-clips",
        "/api/v1/species/Erithacus%20rubecula/presence",
        "/api/v1/sites/pornic/now",
        "/api/v1/sites/pornic/calendar",
        "/api/v1/sites/pornic/species",
        "/api/v1/sites/pornic/stats/kpis",
        "/api/v1/sites/pornic/species-rules",
        "/api/v1/sites/pornic/dynamic-thresholds",
        "/api/v1/sites/pornic/reviews",
        "/api/v1/sites/pornic/false-negatives",
        "/api/v1/sites/pornic/commands",
        "/api/v1/sites/pornic/detections",
        f"/api/v1/recordings/{kept_clip_id}/spectrogram",
    ]:
        resp = anon.get(path)
        assert resp.status_code == 200, (path, resp.status_code, resp.text[:200])

    clips = anon.get("/api/v1/species/Erithacus%20rubecula/sites/pornic/top-clips").json()["clips"]
    assert clips[0]["audio_url"] == f"/api/v1/recordings/{kept_clip_id}/audio"
    assert anon.get(clips[0]["audio_url"]).status_code == 401
    assert anon.get(clips[0]["spectrogram_url"]).headers["content-type"] == "image/png"


def test_node_and_admin_auth_are_unchanged(anon: TestClient, site: dict):
    # Ingestion : Bearer du nœud, sans cookie ni Origin.
    assert anon.post(
        f"/api/v1/nodes/{site['node_id']}/heartbeat", json={}, headers=site["headers"]
    ).status_code != 401
    assert anon.post(f"/api/v1/nodes/{site['node_id']}/heartbeat", json={}).status_code == 401
    # Admin : X-Admin-Token, une session navigateur ne suffit pas.
    assert login(anon).status_code == 200
    assert anon.post("/api/v1/admin/species-data/reload").status_code == 401
    assert (
        anon.post(
            "/api/v1/admin/species-data/reload", headers={"X-Admin-Token": ADMIN_TOKEN}
        ).status_code
        == 200
    )


# ---- Contrôle d'origine (CSRF) --------------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        ("http://testserver", 200),
        ("http://TestServer:80", 200),
        ("http://localhost:5173", 200),  # BIRDFRAME_CORS_ORIGINS (proxy Vite en dev)
        ("https://evil.example", 403),
        ("http://testserver.evil.example", 403),
        ("http://testserver:8443", 403),
        ("null", 403),
    ],
)
def test_mutations_check_origin_header(anon: TestClient, site: dict, origin: str, expected: int):
    assert login(anon).status_code == 200
    resp = _put_rule(anon, headers={"Origin": origin})
    assert resp.status_code == expected, resp.text
    if expected == 403:
        assert resp.json()["error"] == "origin_mismatch"


def test_login_and_logout_reject_foreign_origin(anon: TestClient):
    resp = login(anon, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "origin_mismatch"
    assert "set-cookie" not in resp.headers
    assert anon.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403


def test_origin_matches_forwarded_https_host(auth_app, site):
    # Derrière le proxy Railway : Origin https://<domaine>, Host = <domaine>.
    with TestClient(auth_app, base_url="https://bird-frame.up.railway.app") as c:
        assert login(c, headers={"Origin": "https://bird-frame.up.railway.app"}).status_code == 200
        resp = _put_rule(c, headers={"Origin": "https://bird-frame.up.railway.app"})
        assert resp.status_code == 200, resp.text


# ---- Mode dev sans hash, production -----------------------------------------------------


def test_dev_without_hash_disables_auth_with_warning(app_settings: Settings, caplog):
    with caplog.at_level(logging.WARNING, logger="bird_frame.auth"):
        app = create_app(app_settings)
    assert any("DÉSACTIVÉE" in r.getMessage() for r in caplog.records)

    with TestClient(app) as c:
        assert c.get("/api/v1/auth/me").json() == {"authenticated": False, "auth_enabled": False}
        login_resp = login(c)
        assert login_resp.status_code == 409
        assert login_resp.json()["error"] == "auth_disabled"

        register_site(c)
        # Tout est autorisé sans session…
        assert _put_rule(c).status_code == 200
        # …mais le contrôle d'origine reste actif.
        assert _put_rule(c, headers={"Origin": "https://evil.example"}).status_code == 403


def test_dev_with_hash_applies_auth_and_generates_ephemeral_secret(app_settings, caplog):
    settings = app_settings.model_copy(update={"ui_password_hash": PASSWORD_HASH})
    with caplog.at_level(logging.WARNING, logger="bird_frame.auth"):
        app = create_app(settings)
    assert any("BIRDFRAME_SESSION_SECRET absent" in r.getMessage() for r in caplog.records)
    with TestClient(app) as c:
        assert c.get("/api/v1/auth/me").json() == {"authenticated": False, "auth_enabled": True}
        assert login(c).status_code == 200
        assert c.get("/api/v1/auth/me").json()["authenticated"] is True


@pytest.mark.parametrize(
    ("update", "missing"),
    [
        ({"ui_password_hash": PASSWORD_HASH, "session_secret": ""}, "BIRDFRAME_SESSION_SECRET"),
        ({"ui_password_hash": "", "session_secret": SESSION_SECRET}, "BIRDFRAME_UI_PASSWORD_HASH"),
        ({"ui_password_hash": "", "session_secret": ""}, "BIRDFRAME_UI_PASSWORD_HASH, BIRDFRAME_SESSION_SECRET"),
    ],
)
def test_production_refuses_to_start_without_hash_or_secret(app_settings, update, missing):
    settings = app_settings.model_copy(update={"env": "production", **update})
    with pytest.raises(ConfigError, match=f"manquant : {missing}"):
        create_app(settings)


def test_production_with_hash_and_secret_starts(app_settings, caplog):
    settings = app_settings.model_copy(
        update={"env": "production", "ui_password_hash": PASSWORD_HASH, "session_secret": SESSION_SECRET}
    )
    with caplog.at_level(logging.WARNING, logger="bird_frame.auth"):
        auth = build_browser_auth(settings)
    assert auth.enabled
    assert not caplog.records


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"ui_password_hash": "scrypt$pas$un$hash"}, "BIRDFRAME_UI_PASSWORD_HASH invalide"),
        ({"ui_password_hash": PASSWORD_HASH, "session_secret": "trop-court"}, "trop court"),
    ],
)
@pytest.mark.parametrize("env", ["dev", "production"])
def test_invalid_hash_or_short_secret_refuses_to_start(app_settings, update, message, env):
    settings = app_settings.model_copy(
        update={"env": env, "session_secret": SESSION_SECRET, **update}
    )
    with pytest.raises(ConfigError, match=message):
        create_app(settings)


def test_uvicorn_entrypoint_exits_with_clear_message_in_production_without_secret(tmp_path):
    env = {
        **os.environ,
        "BIRDFRAME_ENV": "production",
        "BIRDFRAME_UI_PASSWORD_HASH": PASSWORD_HASH,
        "BIRDFRAME_SESSION_SECRET": "",
        "BIRDFRAME_DB_PATH": str(tmp_path / "db.sqlite"),
        "BIRDFRAME_DATA_DIR": str(tmp_path / "data"),
    }
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=SERVER_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "bird-frame refuse de démarrer" in result.stderr
    assert "BIRDFRAME_SESSION_SECRET" in result.stderr
    assert "Traceback" not in result.stderr
