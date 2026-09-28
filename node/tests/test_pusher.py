"""WP-03 (sync) + WP-08 amendé (upload/missing des clips demandés)."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx

from bridge.config import BridgeConfig
from bridge.http_errors import RetryDecision
from bridge.pusher import sync_once
from bridge.species_dictionary import SpeciesDictionary
from bridge.sqlite_reader import connect_readonly

SERVER_API = "http://localhost:8090/api/v1"


class _StubExecutor:
    def __init__(self) -> None:
        self.received: list[list[dict]] = []

    async def handle_batch(self, commands: list[dict]) -> None:
        self.received.append(commands)


def _make_config(tmp_path: Path, seeded_db_path: Path, *, batch_size: int = 200) -> BridgeConfig:
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    return BridgeConfig(
        server_url="http://localhost:8090",
        node_id=1,
        secret="s3cr3t",
        site_slug="pornic",
        db_path=str(seeded_db_path),
        clips_dir=clips_dir,
        state_file=tmp_path / "state.json",
        batch_size=batch_size,
    )


async def _loaded_dictionary(node_client: httpx.AsyncClient, config: BridgeConfig) -> SpeciesDictionary:
    dictionary = SpeciesDictionary(node_client, config.node_api)
    await dictionary.ensure_loaded()
    return dictionary


@pytest.mark.asyncio
async def test_sync_once_builds_payload_filters_primary_and_adopts_cursor(
    tmp_path: Path, seeded_db_path: Path
) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    (config.clips_dir / "2026" / "09").mkdir(parents=True)
    (config.clips_dir / "2026" / "09" / "erithacus_rubecula_98p.wav").write_bytes(b"RIFF....WAVEfake")

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={"Erithacus rubecula": "Rougegorge familier"})
                )
                sync_route = mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 3,
                            "duplicates": 0,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [],
                            "commands": [],
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert cursor == 12
        assert outcome.retry_decision == RetryDecision.SUCCESS
        assert outcome.should_continue_immediately is False
        assert outcome.should_stop_loop is False

        sent_body = json.loads(sync_route.calls.last.request.content)
        assert sent_body["since_id"] == 0
        assert sent_body["node_max_id"] == 12
        assert len(sent_body["detections"]) == 3

        first = sent_body["detections"][0]
        assert first["node_local_id"] == 10
        assert first["scientific_name"] == "Erithacus rubecula"
        assert first["common_name"] == "Rougegorge familier"
        assert first["has_clip"] is True  # fichier présent sur disque
        # La prédiction primaire (même nom que la détection) est retirée de la liste secondaire.
        pred_names = [p["scientific_name"] for p in first["predictions"]]
        assert "Erithacus rubecula" not in pred_names
        assert pred_names == ["Columba palumbus", "Turdus merula"]  # tri par confiance décroissante

        second = sent_body["detections"][1]
        assert second["node_local_id"] == 11
        assert second["has_clip"] is False  # clip_name renseigné mais fichier absent, détection ancienne

        third = sent_body["detections"][2]
        assert third["node_local_id"] == 12
        assert third["has_clip"] is False  # pas de clip_name du tout
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_network_error_is_transient_and_cursor_unchanged(
    tmp_path: Path, seeded_db_path: Path
) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    side_effect=httpx.ConnectError("down")
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(side_effect=httpx.ConnectError("no route to host"))
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=5)
        assert cursor == 5
        assert outcome.retry_decision == RetryDecision.TRANSIENT
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_5xx_is_transient(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(return_value=httpx.Response(503, text="oops"))
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=0)
        assert cursor == 0
        assert outcome.retry_decision == RetryDecision.TRANSIENT
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_cursor_ahead_adopts_server_value_and_continues(
    tmp_path: Path, seeded_db_path: Path
) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        409,
                        json={"error": "cursor_ahead", "message": "…", "details": {"synced_up_to_id": 9}},
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=999)
        assert cursor == 9
        assert outcome.should_continue_immediately is True
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_node_db_reset_stops_loop(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        409,
                        json={
                            "error": "node_db_reset",
                            "message": "…",
                            "details": {"synced_up_to_id": 500, "node_max_id": 3},
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=500)
        assert outcome.should_stop_loop is True
        assert cursor == 500  # curseur laissé intact, intervention humaine attendue
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_full_batch_continues_immediately(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path, batch_size=1)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 1,
                            "duplicates": 0,
                            "rejected": [],
                            "synced_up_to_id": 10,
                            "want_clips": [],
                            "commands": [],
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                _, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=0)
        assert outcome.should_continue_immediately is True
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_uploads_existing_file(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    (config.clips_dir / "2026" / "09").mkdir(parents=True)
    clip_path = config.clips_dir / "2026" / "09" / "erithacus_rubecula_98p.wav"
    clip_path.write_bytes(b"RIFFxxxxWAVEfake-audio-bytes")

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [10],
                            "commands": [],
                        },
                    )
                )
                clip_route = mock.post(f"{SERVER_API}/nodes/1/clips/10").mock(
                    return_value=httpx.Response(
                        201,
                        json={
                            "kept_clip_id": 88,
                            "detection_id": 1,
                            "rank": 1,
                            "already_stored": False,
                            "spectrogram_generated": True,
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert clip_route.called
        sent = clip_route.calls.last.request
        assert b'name="clip_name"' in sent.content
        assert b"2026/09/erithacus_rubecula_98p.wav" in sent.content
        assert b"RIFFxxxxWAVEfake-audio-bytes" in sent.content
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_missing_local_file_reports_not_found(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)  # clips_dir vide : le fichier de la détection 11 n'existe pas
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [11],
                            "commands": [],
                        },
                    )
                )
                missing_route = mock.post(f"{SERVER_API}/nodes/1/clips/11/missing").mock(
                    return_value=httpx.Response(200, json={"status": "marked_missing"})
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert missing_route.called
        body = json.loads(missing_route.calls.last.request.content)
        assert body["reason"] == "not_found"
        assert body["clip_name"] == "2026/09/turdus_merula_91p.wav"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_no_clip_name_reports_no_clip_name(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [12],
                            "commands": [],
                        },
                    )
                )
                missing_route = mock.post(f"{SERVER_API}/nodes/1/clips/12/missing").mock(
                    return_value=httpx.Response(200, json={"status": "marked_missing"})
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        body = json.loads(missing_route.calls.last.request.content)
        assert body["reason"] == "no_clip_name"
        assert body["clip_name"] is None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_commands_bonus_is_forwarded_to_executor(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    executor = _StubExecutor()
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [],
                            "commands": [
                                {
                                    "id": 1,
                                    "kind": "exclude_species",
                                    "payload": {},
                                    "created_at": "2026-01-01T00:00:00Z",
                                    "expires_at": None,
                                }
                            ],
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, executor, cursor=0)
        assert len(executor.received) == 1
        assert executor.received[0][0]["kind"] == "exclude_species"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_rejected_elements_do_not_block_cursor_advance(tmp_path: Path, seeded_db_path: Path) -> None:
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 2,
                            "duplicates": 0,
                            "rejected": [{"node_local_id": 11, "error": "confidence hors bornes"}],
                            "synced_up_to_id": 12,
                            "want_clips": [],
                            "commands": [],
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=0)
        assert cursor == 12
        assert outcome.retry_decision == RetryDecision.SUCCESS
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_sync_once_sqlite_read_error_is_transient_not_a_crash(tmp_path: Path, seeded_db_path: Path) -> None:
    """`sync_once` ne doit jamais laisser une erreur de lecture locale (verrou WAL transitoire,
    E/S disque, base déplacée pendant une bascule de lieu, cf. CLAUDE.md racine « stop → mv →
    start ») se propager : même contrat de backoff qu'une erreur réseau (§4.1), pas un crash de la
    boucle de synchro (qui, via le TaskGroup, tuerait aussi les trois autres boucles)."""
    config = _make_config(tmp_path, seeded_db_path)
    conn = connect_readonly(config.db_path)
    conn.close()  # simule une lecture locale devenue impossible
    async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                return_value=httpx.Response(200, json={})
            )
            dictionary = await _loaded_dictionary(node_client, config)
            cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=7)
    assert cursor == 7
    assert outcome.retry_decision == RetryDecision.TRANSIENT


@pytest.mark.asyncio
async def test_sync_once_state_write_failure_is_logged_and_does_not_crash_the_cycle(
    tmp_path: Path, seeded_db_path: Path, caplog
) -> None:
    """`save_state` journalise puis re-lève volontairement une OSError (state.py) : le fichier
    d'état n'est qu'un cache local (le curseur canonique est celui renvoyé par le serveur). Un
    disque plein / répertoire inaccessible sur BRIDGE_STATE_FILE ne doit jamais faire planter tout
    le cycle de sync."""
    config = _make_config(tmp_path, seeded_db_path)
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_bytes(b"obstacle")
    config = replace(config, state_file=blocking_file / "state.json")  # mkdir(parents=True) échouera

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 3,
                            "duplicates": 0,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [],
                            "commands": [],
                        },
                    )
                )
                dictionary = await _loaded_dictionary(node_client, config)
                with caplog.at_level(logging.ERROR, logger="bridge.pusher"):
                    cursor, outcome = await sync_once(conn, config, server_client, dictionary, None, cursor=0)
        assert cursor == 12  # curseur serveur adopté malgré l'échec d'écriture locale
        assert outcome.retry_decision == RetryDecision.SUCCESS
        assert any("Écriture de l'état local" in r.message for r in caplog.records)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_missing_404_from_server_is_logged(
    tmp_path: Path, seeded_db_path: Path, caplog
) -> None:
    """api-contract.md §4.4 : POST .../missing peut répondre 404 detection_not_found (curseur local
    en avance sur ce que le serveur a réellement persisté). Doit être visible dans les logs, tout
    comme le 404 analogue et déjà loggé sur l'upload de clip (§4.3)."""
    config = _make_config(tmp_path, seeded_db_path)  # clips_dir vide : le fichier de la détection 11 n'existe pas
    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [11],
                            "commands": [],
                        },
                    )
                )
                mock.post(f"{SERVER_API}/nodes/1/clips/11/missing").mock(
                    return_value=httpx.Response(404, json={"error": "detection_not_found"})
                )
                dictionary = await _loaded_dictionary(node_client, config)
                with caplog.at_level(logging.WARNING, logger="bridge.pusher"):
                    await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert any("404" in r.message for r in caplog.records)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_oversized_file_is_never_read_and_reported_missing(
    tmp_path: Path, seeded_db_path: Path, monkeypatch
) -> None:
    """Sans ce garde-fou, un clip anormalement gros (bug d'export, format mal segmenté) serait relu
    en entier en mémoire et renvoyé au serveur à chaque cycle (~20 s) indéfiniment, celui-ci
    répondant 413 à chaque fois sans que le bridge n'arrête jamais de réessayer."""
    monkeypatch.setattr("bridge.pusher._MAX_CLIP_UPLOAD_BYTES", 10)  # limite artificiellement basse
    config = _make_config(tmp_path, seeded_db_path)
    (config.clips_dir / "2026" / "09").mkdir(parents=True)
    clip_path = config.clips_dir / "2026" / "09" / "erithacus_rubecula_98p.wav"
    clip_path.write_bytes(b"RIFF....WAVE-bien-plus-long-que-la-limite-de-test")

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [10],
                            "commands": [],
                        },
                    )
                )
                upload_route = mock.post(f"{SERVER_API}/nodes/1/clips/10")
                missing_route = mock.post(f"{SERVER_API}/nodes/1/clips/10/missing").mock(
                    return_value=httpx.Response(200, json={"status": "marked_missing"})
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert not upload_route.called  # jamais lu ni envoyé
        assert missing_route.called
        body = json.loads(missing_route.calls.last.request.content)
        assert body["reason"] == "unreadable"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_want_clips_413_from_server_reports_missing_instead_of_retrying_forever(
    tmp_path: Path, seeded_db_path: Path
) -> None:
    """413 payload_too_large (§4.3) tombait auparavant dans la branche générique (ERROR loggé, sans
    signalement 'missing') : le serveur redemandait alors ce même clip indéfiniment."""
    config = _make_config(tmp_path, seeded_db_path)
    (config.clips_dir / "2026" / "09").mkdir(parents=True)
    clip_path = config.clips_dir / "2026" / "09" / "erithacus_rubecula_98p.wav"
    clip_path.write_bytes(b"RIFFxxxxWAVEfake-audio-bytes")

    conn = connect_readonly(config.db_path)
    try:
        async with httpx.AsyncClient() as node_client, httpx.AsyncClient(base_url=SERVER_API) as server_client:
            with respx.mock(assert_all_called=False) as mock:
                mock.get(f"{config.node_api}/api/v2/species/dictionary/fr").mock(
                    return_value=httpx.Response(200, json={})
                )
                mock.post(f"{SERVER_API}/nodes/1/sync").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "accepted": 0,
                            "duplicates": 3,
                            "rejected": [],
                            "synced_up_to_id": 12,
                            "want_clips": [10],
                            "commands": [],
                        },
                    )
                )
                mock.post(f"{SERVER_API}/nodes/1/clips/10").mock(
                    return_value=httpx.Response(413, json={"error": "payload_too_large"})
                )
                missing_route = mock.post(f"{SERVER_API}/nodes/1/clips/10/missing").mock(
                    return_value=httpx.Response(200, json={"status": "marked_missing"})
                )
                dictionary = await _loaded_dictionary(node_client, config)
                await sync_once(conn, config, server_client, dictionary, None, cursor=0)

        assert missing_route.called
        body = json.loads(missing_route.calls.last.request.content)
        assert body["reason"] == "unreadable"
    finally:
        conn.close()
