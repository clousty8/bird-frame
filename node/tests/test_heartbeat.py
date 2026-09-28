"""Heartbeat (§4.6) : assemblage du payload, micro effectivement capté, PID vivant, seuils
dynamiques paginés — sans jamais muter le nœud."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import pytest
import respx

from bridge.config import BridgeConfig
from bridge.heartbeat import (
    build_heartbeat_payload,
    check_pid_alive,
    disk_free_pct,
    read_pid_file,
    run_heartbeat_loop,
)
from bridge.sqlite_reader import connect_readonly

NODE_API = "http://localhost:8080"


def _config(tmp_path: Path, seeded_db_path: Path, **overrides) -> BridgeConfig:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir(exist_ok=True)
    kwargs = dict(
        server_url="http://localhost:8090",
        node_id=1,
        secret="s3cr3t",
        site_slug="pornic",
        db_path=str(seeded_db_path),
        clips_dir=clips_dir,
        state_file=tmp_path / "state.json",
    )
    kwargs.update(overrides)
    return BridgeConfig(**kwargs)


async def _always_present(_tool: str, _pid: int) -> list[str]:
    return ["HyperX QuadCast 2"]


async def _always_absent(_tool: str, _pid: int) -> list[str]:
    return []


@pytest.mark.asyncio
async def test_build_heartbeat_payload_happy_path(tmp_path: Path, seeded_db_path: Path) -> None:
    pid_file = tmp_path / "birdnet.pid"
    pid_file.write_text("999999999\n")  # PID quasi certainement inexistant → pid_alive False, sans planter
    config = _config(tmp_path, seeded_db_path, birdnet_pid_file=str(pid_file), mic_status_tool="fake-tool")

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(
                    return_value=httpx.Response(200, json={"version": "20260823"})
                )
                mock.get(f"{NODE_API}/api/v2/settings/audio").mock(
                    return_value=httpx.Response(
                        200, json={"sources": [{"name": "Sound Card 1", "device": "HyperX QuadCast 2"}]}
                    )
                )
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "data": [
                                {
                                    "speciesName": "accenteur mouchet",
                                    "scientificName": "Prunella modularis",
                                    "level": 3,
                                    "currentValue": 0.2,
                                    "baseThreshold": 0.6,
                                    "highConfCount": 19,
                                    "triggerCount": 19,
                                    "isActive": True,
                                    "expiresAt": "2026-09-28T14:26:19.26845+02:00",
                                    "lastTriggered": "2026-09-27T14:39:38.558881+02:00",
                                    "firstCreated": "0001-01-01T00:00:00Z",
                                }
                            ],
                            "total": 1,
                            "limit": 250,
                            "offset": 0,
                        },
                    )
                )
                payload = await build_heartbeat_payload(
                    conn, node_client, config, mic_status_runner=_always_present
                )
    finally:
        conn.close()

    assert payload["birdnet_go_reachable"] is True
    assert payload["birdnet_go_version"] == "20260823"
    assert payload["birdnet_go_pid_alive"] is False
    assert payload["mic_device_name"] == "HyperX QuadCast 2"
    assert payload["mic_healthy"] is True
    assert payload["node_db_max_id"] == 12  # MAX(detections.id) du fixture partagé
    assert payload["disk_free_pct"] is not None

    thresholds = payload["dynamic_thresholds_snapshot"]
    assert thresholds == [
        {
            "species_name": "accenteur mouchet",
            "scientific_name": "Prunella modularis",
            "level": 3,
            "current_value": 0.2,
            "base_threshold": 0.6,
            "high_conf_count": 19,
            "trigger_count": 19,
            "is_active": True,
            "expires_at_utc": "2026-09-28T12:26:19Z",
            "last_triggered_utc": "2026-09-27T12:39:38Z",
            "first_created_utc": None,  # instant Go "zéro" → null
        }
    ]


@pytest.mark.asyncio
async def test_build_heartbeat_payload_mic_mismatch_is_unhealthy(tmp_path: Path, seeded_db_path: Path) -> None:
    pid_file = tmp_path / "birdnet.pid"
    pid_file.write_text("123\n")
    config = _config(tmp_path, seeded_db_path, mic_status_tool="fake-tool", birdnet_pid_file=str(pid_file))
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(
                    return_value=httpx.Response(200, json={"version": "x"})
                )
                mock.get(f"{NODE_API}/api/v2/settings/audio").mock(
                    return_value=httpx.Response(200, json={"sources": [{"device": "HyperX QuadCast 2"}]})
                )
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                    return_value=httpx.Response(200, json={"data": [], "total": 0, "limit": 250, "offset": 0})
                )
                payload = await build_heartbeat_payload(
                    conn, node_client, config, mic_status_runner=_always_absent
                )
    finally:
        conn.close()

    assert payload["mic_device_name"] is None  # aucun micro capté
    assert payload["mic_healthy"] is False  # un micro est attendu mais aucun n'est capté
    assert payload["dynamic_thresholds_snapshot"] == []


@pytest.mark.asyncio
async def test_build_heartbeat_payload_unreachable_node(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(side_effect=httpx.ConnectError("down"))
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                    side_effect=httpx.ConnectError("down")
                )
                payload = await build_heartbeat_payload(conn, node_client, config)
    finally:
        conn.close()

    assert payload["birdnet_go_reachable"] is False
    assert payload["birdnet_go_version"] is None
    assert payload["dynamic_thresholds_snapshot"] is None  # lecture impossible : instantané précédent conservé
    assert payload["mic_device_name"] is None  # BRIDGE_MIC_STATUS_TOOL non configuré
    assert payload["mic_healthy"] is None


@pytest.mark.asyncio
async def test_build_heartbeat_payload_app_config_non_200_is_logged(
    tmp_path: Path, seeded_db_path: Path, caplog
) -> None:
    """Un statut != 200 sans exception réseau (500, 401, 503 maintenance…) doit être visible dans
    les logs locaux du bridge, pas seulement déduit à distance via birdnet_go_reachable=false dans
    le payload envoyé au serveur."""
    config = _config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(
                    return_value=httpx.Response(500, text="internal error")
                )
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                    return_value=httpx.Response(200, json={"data": [], "total": 0, "limit": 250, "offset": 0})
                )
                with caplog.at_level(logging.WARNING, logger="bridge.heartbeat"):
                    payload = await build_heartbeat_payload(conn, node_client, config)
    finally:
        conn.close()

    assert payload["birdnet_go_reachable"] is False
    assert any("500" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_build_heartbeat_payload_skips_malformed_dynamic_threshold_entry(
    tmp_path: Path, seeded_db_path: Path, caplog
) -> None:
    """Une entrée incomplète (champ Go `omitempty` omis, dérive de schéma BirdNET-Go) ne doit
    jamais faire planter tout le heartbeat (et, via le TaskGroup, les trois autres boucles) —
    seule cette entrée est ignorée, journalisée en WARNING."""
    config = _config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(
                    return_value=httpx.Response(200, json={"version": "x"})
                )
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "data": [
                                # incomplet : highConfCount (et les champs suivants) manquent
                                {"speciesName": "accenteur mouchet", "scientificName": "Prunella modularis"},
                                {
                                    "speciesName": "choucas des tours",
                                    "scientificName": "Corvus monedula",
                                    "level": 1,
                                    "currentValue": 0.3,
                                    "baseThreshold": 0.5,
                                    "highConfCount": 5,
                                    "triggerCount": 5,
                                    "isActive": True,
                                    "expiresAt": None,
                                    "lastTriggered": None,
                                    "firstCreated": None,
                                },
                            ],
                            "total": 2,
                            "limit": 250,
                            "offset": 0,
                        },
                    )
                )
                with caplog.at_level(logging.WARNING, logger="bridge.heartbeat"):
                    payload = await build_heartbeat_payload(conn, node_client, config)
    finally:
        conn.close()

    thresholds = payload["dynamic_thresholds_snapshot"]
    assert len(thresholds) == 1  # l'entrée incomplète est ignorée, pas de KeyError qui plante tout
    assert thresholds[0]["scientific_name"] == "Corvus monedula"
    assert any("mal formée" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_run_heartbeat_loop_survives_sqlite_read_error(
    tmp_path: Path, seeded_db_path: Path, caplog
) -> None:
    """`fetch_max_detection_id` (appelé par `build_heartbeat_payload`) peut lever un
    `SqliteReaderError` (verrou WAL transitoire, E/S disque). Avant le correctif, cet appel était
    hors du try/except réseau de `run_heartbeat_loop` : l'exception remontait non rattrapée et
    tuait la boucle heartbeat (et, via le TaskGroup unique, les trois autres boucles avec elle)."""
    config = _config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    conn.close()  # simule une lecture locale devenue impossible
    stop_event = asyncio.Event()

    async def _stop_soon() -> None:
        await asyncio.sleep(0.05)
        stop_event.set()

    async with (
        httpx.AsyncClient() as node_client,
        httpx.AsyncClient(base_url="http://localhost:8090/api/v1") as server_client,
    ):
        with respx.mock(assert_all_called=False) as mock:
            mock.get(f"{NODE_API}/api/v2/app/config").mock(return_value=httpx.Response(200, json={"version": "x"}))
            with caplog.at_level(logging.WARNING, logger="bridge.heartbeat"):
                await asyncio.gather(
                    run_heartbeat_loop(conn, node_client, server_client, config, stop_event),
                    _stop_soon(),
                )

    assert any("birdnet.db impossible" in r.message for r in caplog.records)


def test_read_pid_file_missing_returns_none(tmp_path: Path) -> None:
    assert read_pid_file(str(tmp_path / "absent.pid")) is None
    assert read_pid_file(None) is None


def test_read_pid_file_garbage_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "birdnet.pid"
    path.write_text("not-a-pid")
    assert read_pid_file(str(path)) is None


def test_check_pid_alive_for_current_process() -> None:
    import os

    assert check_pid_alive(os.getpid()) is True


def test_check_pid_alive_for_nonexistent_pid() -> None:
    assert check_pid_alive(999999999) is False


def test_disk_free_pct_returns_percentage(tmp_path: Path) -> None:
    value = disk_free_pct(tmp_path)
    assert value is not None
    assert 0.0 <= value <= 100.0


def test_disk_free_pct_missing_dir_returns_none(tmp_path: Path) -> None:
    assert disk_free_pct(tmp_path / "does" / "not" / "exist") is None


@pytest.mark.asyncio
async def test_run_heartbeat_loop_reports_update_status_and_forwards_latest_version(
    tmp_path: Path, seeded_db_path: Path
) -> None:
    """Contrat §12.4 : le heartbeat porte `update_status` de l'updater, et transmet à l'updater
    le `latest_node_version` de la réponse (réveil anticipé de la vérification)."""
    import json

    config = _config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    stop_event = asyncio.Event()

    class FakeUpdater:
        def __init__(self) -> None:
            self.hints: list[object] = []

        def status_payload(self) -> dict:
            return {"state": "failed", "target_version": "0.2.0", "error": "uv sync a échoué (code 1)"}

        def notify_latest_version(self, latest: object) -> None:
            self.hints.append(latest)
            stop_event.set()

    updater = FakeUpdater()
    try:
        async with (
            httpx.AsyncClient() as node_client,
            httpx.AsyncClient(base_url="http://localhost:8090/api/v1") as server_client,
        ):
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{NODE_API}/api/v2/app/config").mock(
                    return_value=httpx.Response(200, json={"version": "x"})
                )
                mock.get(f"{NODE_API}/api/v2/dynamic-thresholds").mock(
                    return_value=httpx.Response(200, json={"data": [], "total": 0, "limit": 250, "offset": 0})
                )
                route = mock.post("http://localhost:8090/api/v1/nodes/1/heartbeat").mock(
                    return_value=httpx.Response(
                        200, json={"server_time_utc": "2026-09-28T10:00:00Z", "latest_node_version": "0.3.0"}
                    )
                )
                await asyncio.wait_for(
                    run_heartbeat_loop(conn, node_client, server_client, config, stop_event, updater=updater),
                    timeout=5,
                )
    finally:
        conn.close()

    body = json.loads(route.calls[0].request.content)
    assert body["update_status"] == updater.status_payload()
    assert updater.hints == ["0.3.0"]
