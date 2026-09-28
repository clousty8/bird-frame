"""WP-11 : chaque `kind` → bonne route BirdNET-Go (respx), ack applied/failed, dédup, expiration."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
import respx

from bridge.commands import CommandExecutor
from bridge.config import BridgeConfig
from bridge.csrf_client import CsrfClient
from bridge.species_dictionary import SpeciesDictionary

NODE_API = "http://localhost:8080"
SERVER_API = "http://localhost:8090/api/v1"


def _config(tmp_path) -> BridgeConfig:
    return BridgeConfig(
        server_url="http://localhost:8090",
        node_id=1,
        secret="s3cr3t",
        site_slug="pornic",
        db_path=str(tmp_path / "birdnet.db"),
        clips_dir=tmp_path / "clips",
        state_file=tmp_path / "state.json",
    )


def _mock_csrf_bootstrap(mock: respx.MockRouter) -> None:
    mock.get(f"{NODE_API}/api/v2/app/config").mock(
        return_value=httpx.Response(
            200, json={"csrfToken": "unused"}, headers={"Set-Cookie": "csrf=tok123; Path=/"}
        )
    )


async def _executor(tmp_path, node_client: httpx.AsyncClient, server_client: httpx.AsyncClient) -> CommandExecutor:
    config = _config(tmp_path)
    csrf = CsrfClient(node_client, config.node_api)
    dictionary = SpeciesDictionary(node_client, config.node_api)
    return CommandExecutor(csrf, server_client, config, dictionary)


def _command(command_id: int, kind: str, payload: dict, *, expires_at: str | None = None) -> dict:
    return {
        "id": command_id,
        "kind": kind,
        "payload": payload,
        "created_at": "2026-09-27T10:00:00Z",
        "expires_at": expires_at,
    }


@pytest.mark.asyncio
async def test_set_species_threshold_patches_config_key(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/species/dictionary/fr").mock(return_value=httpx.Response(200, json={}))
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"include": [], "exclude": [], "config": None})
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"message": "ok", "skippedFields": [], "restart_required": False}
                )
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/1/ack").mock(
                return_value=httpx.Response(200, json={"id": 1, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        1,
                        "set_species_threshold",
                        {"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4},
                    )
                ]
            )

        assert patch_route.called
        sent = json.loads(patch_route.calls.last.request.content)
        assert sent == {"config": {"larus argentatus": {"threshold": 0.4}}}

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "applied"
        assert ack_body["result"]["changed"] is True
        assert ack_body["result"]["keys"] == ["larus argentatus"]


@pytest.mark.asyncio
async def test_set_species_threshold_also_updates_shadowing_common_name_key(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/species/dictionary/fr").mock(
                return_value=httpx.Response(200, json={"Larus argentatus": "Goéland argenté"})
            )
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": [], "exclude": [], "config": {"goéland argenté": {"threshold": 0.6}}}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/2/ack").mock(
                return_value=httpx.Response(200, json={"id": 2, "status": "applied"})
            )

            csrf = CsrfClient(node_client, NODE_API)
            dictionary = SpeciesDictionary(node_client, NODE_API)
            await dictionary.ensure_loaded()
            config = _config(tmp_path)
            executor = CommandExecutor(csrf, server_client, config, dictionary)
            await executor.handle_batch(
                [
                    _command(
                        2,
                        "set_species_threshold",
                        {"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4},
                    )
                ]
            )

        sent = json.loads(patch_route.calls.last.request.content)
        assert set(sent["config"].keys()) == {"larus argentatus", "goéland argenté"}


@pytest.mark.asyncio
async def test_set_species_threshold_null_removes_key_via_put(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/species/dictionary/fr").mock(return_value=httpx.Response(200, json={}))
            full_settings = {
                "realtime": {
                    "species": {"include": [], "exclude": [], "config": {"larus argentatus": {"threshold": 0.4}}}
                }
            }
            mock.get(f"{NODE_API}/api/v2/settings").mock(return_value=httpx.Response(200, json=full_settings))
            put_route = mock.put(f"{NODE_API}/api/v2/settings").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/3/ack").mock(
                return_value=httpx.Response(200, json={"id": 3, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        3,
                        "set_species_threshold",
                        {"scientific_name": "Larus argentatus", "aliases": [], "threshold": None},
                    )
                ]
            )

        sent = json.loads(put_route.calls.last.request.content)
        assert sent["realtime"]["species"]["config"] == {}


@pytest.mark.asyncio
async def test_exclude_species_adds_to_list(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"include": [], "exclude": [], "config": None})
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/4/ack").mock(
                return_value=httpx.Response(200, json={"id": 4, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(4, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})]
            )

        sent = json.loads(patch_route.calls.last.request.content)
        assert sent == {"exclude": ["Columba livia"]}


@pytest.mark.asyncio
async def test_exclude_species_noop_when_already_excluded(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": [], "exclude": ["Columba livia"], "config": None}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species")
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/5/ack").mock(
                return_value=httpx.Response(200, json={"id": 5, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(5, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})]
            )

        assert not patch_route.called  # aucune mutation pour un no-op
        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["result"]["changed"] is False


@pytest.mark.asyncio
async def test_include_species_route(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"include": [], "exclude": [], "config": None})
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/6/ack").mock(
                return_value=httpx.Response(200, json={"id": 6, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(6, "include_species", {"scientific_name": "Larus argentatus", "aliases": []})]
            )

        assert json.loads(patch_route.calls.last.request.content) == {"include": ["Larus argentatus"]}


@pytest.mark.asyncio
async def test_reset_dynamic_threshold_deletes_matching_entries(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/dynamic-thresholds", params={"limit": "250", "offset": "0"}).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "data": [{"speciesName": "accenteur mouchet", "scientificName": "Prunella modularis"}],
                        "total": 1,
                        "limit": 250,
                        "offset": 0,
                    },
                )
            )
            delete_route = mock.delete(f"{NODE_API}/api/v2/dynamic-thresholds/accenteur%20mouchet").mock(
                return_value=httpx.Response(200, json={"success": True})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/7/ack").mock(
                return_value=httpx.Response(200, json={"id": 7, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(7, "reset_dynamic_threshold", {"scientific_name": "Prunella modularis", "aliases": []})]
            )

        assert delete_route.called


@pytest.mark.asyncio
async def test_set_main_name_applied_when_verified(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/main").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.get(f"{NODE_API}/api/v2/settings/main").mock(
                return_value=httpx.Response(200, json={"name": "pornic", "timeAs24h": True})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/8/ack").mock(
                return_value=httpx.Response(200, json={"id": 8, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch([_command(8, "set_main_name", {"name": "pornic"})])

        assert patch_route.called
        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "applied"
        assert ack_body["result"] == {"name": "pornic"}


@pytest.mark.asyncio
async def test_set_main_name_failed_when_verification_mismatches(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.patch(f"{NODE_API}/api/v2/settings/main").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.get(f"{NODE_API}/api/v2/settings/main").mock(
                return_value=httpx.Response(200, json={"name": "BirdNET-Go"})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/9/ack").mock(
                return_value=httpx.Response(200, json={"id": 9, "status": "failed"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch([_command(9, "set_main_name", {"name": "pornic"})])

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "failed"
        assert ack_body["error"] is not None


@pytest.mark.asyncio
async def test_expired_command_is_acked_failed_without_touching_node(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species")
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/10/ack").mock(
                return_value=httpx.Response(200, json={"id": 10, "status": "failed"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        10,
                        "exclude_species",
                        {"scientific_name": "Columba livia", "aliases": []},
                        expires_at="2020-01-01T00:00:00Z",
                    )
                ]
            )

        assert not patch_route.called
        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body == {"status": "failed", "result": None, "error": "expired"}


@pytest.mark.asyncio
async def test_unknown_kind_is_never_acked(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/11/ack")
            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(11, "some_future_kind_not_implemented_yet", {"scientific_name": "Columba livia"})]
            )
        assert not ack_route.called


@pytest.mark.asyncio
async def test_dedupe_executes_command_id_only_once(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"include": [], "exclude": [], "config": None})
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/12/ack").mock(
                return_value=httpx.Response(200, json={"id": 12, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            command = _command(12, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})
            await executor.handle_batch([command])
            await executor.handle_batch([command])  # livré deux fois (poll + bonus du /sync)

        assert patch_route.call_count == 1


@pytest.mark.asyncio
async def test_permanent_node_error_acks_failed(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(422, json={"error": "validation_error"})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/13/ack").mock(
                return_value=httpx.Response(200, json={"id": 13, "status": "failed"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(13, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})]
            )

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "failed"


@pytest.mark.asyncio
async def test_transient_node_error_is_never_acked(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(return_value=httpx.Response(503))
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/14/ack")

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(14, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})]
            )

        assert not ack_route.called  # pas d'ack sur échec transitoire : le serveur redélivrera


@pytest.mark.asyncio
async def test_start_live_skeleton_calls_expected_route(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            start_route = mock.post(f"{NODE_API}/api/v2/streams/hls/audio_card_1/start").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "streamToken": "tok-abc",
                        "playlistUrl": "/x.m3u8",
                        "status": "ready",
                        "playlistReady": True,
                    },
                )
            )
            mock.post(f"{NODE_API}/api/v2/streams/hls/heartbeat").mock(return_value=httpx.Response(200, json={}))
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/15/ack").mock(
                return_value=httpx.Response(200, json={"id": 15, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        15,
                        "start_live",
                        {"session_id": "3f0e6a52-2c1b-4d7e-9a57-0c6f1e8b9d21", "source_id": "audio_card_1"},
                    )
                ]
            )
            # Nettoyage : annule la tâche de heartbeat HLS auto-démarrée pour ne pas laisser
            # le test tourner en tâche de fond.
            for session in executor.live_sessions.all_sessions():
                if session.heartbeat_task:
                    session.heartbeat_task.cancel()

        assert start_route.called
        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "applied"
        assert ack_body["result"]["stream_token"] == "tok-abc"


@pytest.mark.asyncio
async def test_stop_live_unknown_session_is_idempotent_applied(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/16/ack").mock(
                return_value=httpx.Response(200, json={"id": 16, "status": "applied"})
            )
            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch([_command(16, "stop_live", {"session_id": "unknown-session"})])

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "applied"


@pytest.mark.asyncio
async def test_live_heartbeat_unknown_session_fails_permanently(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/17/ack").mock(
                return_value=httpx.Response(200, json={"id": 17, "status": "failed"})
            )
            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch([_command(17, "live_heartbeat", {"session_id": "unknown-session"})])

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body == {"status": "failed", "result": None, "error": "unknown_session"}


@pytest.mark.asyncio
async def test_hls_heartbeat_loop_auto_stops_expired_session(tmp_path, monkeypatch) -> None:
    """§5.3 : « session terminée automatiquement si aucun live_heartbeat n'est reçu pendant 60 s ».
    `_LIVE_HEARTBEAT_PERIOD_S` est raccourci pour ne pas attendre 20 s réelles dans le test."""
    monkeypatch.setattr("bridge.commands._LIVE_HEARTBEAT_PERIOD_S", 0.01)
    session_id = "3f0e6a52-2c1b-4d7e-9a57-0c6f1e8b9d21"
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.post(f"{NODE_API}/api/v2/streams/hls/audio_card_1/start").mock(
                return_value=httpx.Response(200, json={"streamToken": "tok-abc", "status": "ready"})
            )
            stop_route = mock.post(f"{NODE_API}/api/v2/streams/hls/audio_card_1/stop").mock(
                return_value=httpx.Response(200, json={"status": "stopped"})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/18/ack").mock(
                return_value=httpx.Response(200, json={"id": 18, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(18, "start_live", {"session_id": session_id, "source_id": "audio_card_1"})]
            )
            session = executor.live_sessions.get(session_id)
            assert session is not None
            session.expires_at_monotonic = time.monotonic() - 1.0  # déjà expirée

            await asyncio.sleep(0.05)  # laisse un cycle de `_hls_heartbeat_loop` s'exécuter

        assert stop_route.called
        assert executor.live_sessions.get(session_id) is None  # purgée du registre, pas orpheline


@pytest.mark.asyncio
async def test_transient_error_does_not_dedupe_the_command(tmp_path) -> None:
    """Une commande non acquittée (échec transitoire) ne doit jamais entrer dans la fenêtre de
    dédup de 30 min : sinon sa redélivrance légitime par le serveur serait sautée en silence."""
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            species_route = mock.get(f"{NODE_API}/api/v2/settings/species")
            species_route.side_effect = [
                httpx.Response(503),  # échec transitoire : pas d'ack
                httpx.Response(200, json={"include": [], "exclude": [], "config": None}),  # redélivrance
            ]
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/19/ack").mock(
                return_value=httpx.Response(200, json={"id": 19, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            command = _command(19, "exclude_species", {"scientific_name": "Columba livia", "aliases": []})
            await executor.handle_batch([command])  # 503 : échec transitoire, pas d'ack, pas de dédup
            await executor.handle_batch([command])  # redélivrée : doit être réexécutée, pas sautée

        assert species_route.call_count == 2
        assert patch_route.called
        assert ack_route.called


@pytest.mark.asyncio
async def test_set_species_threshold_resolves_common_name_via_alias_when_node_uses_raw_name(tmp_path) -> None:
    """Le dictionnaire FR du nœud est indexé sur le nom BRUT du nœud (ex. Coloeus monedula), pas
    forcément le nom canonique envoyé par le serveur (ex. Corvus monedula) — api-contract.md §1.6.
    `dictionary.get(scientific_name)` seul ne trouve donc rien pour une espèce aliasée ; il faut
    aussi essayer les alias."""
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/species/dictionary/fr").mock(
                return_value=httpx.Response(200, json={"Coloeus monedula": "Choucas des tours"})
            )
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": [], "exclude": [], "config": {"choucas des tours": {"threshold": 0.5}}}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/20/ack").mock(
                return_value=httpx.Response(200, json={"id": 20, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        20,
                        "set_species_threshold",
                        {"scientific_name": "Corvus monedula", "aliases": ["Coloeus monedula"], "threshold": 0.4},
                    )
                ]
            )

        sent = json.loads(patch_route.calls.last.request.content)
        assert set(sent["config"].keys()) == {"corvus monedula", "coloeus monedula", "choucas des tours"}


@pytest.mark.asyncio
async def test_handle_batch_loads_dictionary_automatically_before_set_species_threshold(tmp_path) -> None:
    """La boucle de commandes peut exécuter une commande déjà en file avant le premier
    `sync_once` (qui charge normalement le dictionnaire) — api-contract.md §4.1 : la boucle de
    commandes démarre en premier. Contrairement aux autres tests `set_species_threshold`, le
    dictionnaire n'est PAS pré-chargé manuellement ici."""
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            dict_route = mock.get(f"{NODE_API}/api/v2/species/dictionary/fr").mock(
                return_value=httpx.Response(200, json={"Larus argentatus": "Goéland argenté"})
            )
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": [], "exclude": [], "config": {"goéland argenté": {"threshold": 0.6}}}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/21/ack").mock(
                return_value=httpx.Response(200, json={"id": 21, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            assert not executor._dictionary.loaded
            await executor.handle_batch(
                [
                    _command(
                        21,
                        "set_species_threshold",
                        {"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4},
                    )
                ]
            )

        assert dict_route.called
        assert executor._dictionary.loaded
        sent = json.loads(patch_route.calls.last.request.content)
        assert set(sent["config"].keys()) == {"larus argentatus", "goéland argenté"}


@pytest.mark.asyncio
async def test_unexclude_species_removes_from_exclude_list(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": [], "exclude": ["Columba livia"], "config": None}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/22/ack").mock(
                return_value=httpx.Response(200, json={"id": 22, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(22, "unexclude_species", {"scientific_name": "Columba livia", "aliases": []})]
            )

        assert json.loads(patch_route.calls.last.request.content) == {"exclude": []}


@pytest.mark.asyncio
async def test_uninclude_species_removes_from_include_list(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.get(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(
                    200, json={"include": ["Larus argentatus"], "exclude": [], "config": None}
                )
            )
            patch_route = mock.patch(f"{NODE_API}/api/v2/settings/species").mock(
                return_value=httpx.Response(200, json={"restart_required": False})
            )
            mock.post(f"{SERVER_API}/nodes/1/commands/23/ack").mock(
                return_value=httpx.Response(200, json={"id": 23, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(23, "uninclude_species", {"scientific_name": "Larus argentatus", "aliases": []})]
            )

        assert json.loads(patch_route.calls.last.request.content) == {"include": []}


@pytest.mark.asyncio
async def test_mark_detection_reviewed_applied(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            review_route = mock.post(f"{NODE_API}/api/v2/detections/4627/review").mock(
                return_value=httpx.Response(200, json={"status": "ok"})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/24/ack").mock(
                return_value=httpx.Response(200, json={"id": 24, "status": "applied"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [
                    _command(
                        24,
                        "mark_detection_reviewed",
                        {"node_local_id": 4627, "verified": "false_positive", "comment": "c'était un pic"},
                    )
                ]
            )

        sent = json.loads(review_route.calls.last.request.content)
        assert sent == {"verified": "false_positive", "comment": "c'était un pic"}
        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body == {"status": "applied", "result": None, "error": None}


@pytest.mark.asyncio
async def test_mark_detection_reviewed_locked_detection_fails_permanently(tmp_path) -> None:
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            _mock_csrf_bootstrap(mock)
            mock.post(f"{NODE_API}/api/v2/detections/4627/review").mock(
                return_value=httpx.Response(409, json={"error": "locked"})
            )
            ack_route = mock.post(f"{SERVER_API}/nodes/1/commands/25/ack").mock(
                return_value=httpx.Response(200, json={"id": 25, "status": "failed"})
            )

            executor = await _executor(tmp_path, node_client, server_client)
            await executor.handle_batch(
                [_command(25, "mark_detection_reviewed", {"node_local_id": 4627, "verified": "correct"})]
            )

        ack_body = json.loads(ack_route.calls.last.request.content)
        assert ack_body["status"] == "failed"
