"""Boucle de synchro : détections + prédictions + clips demandés (WP-03, WP-08 amendé, §4.2-§4.4).

Un cycle (`sync_once`) :
1. lit `birdnet.db` depuis le curseur courant (≤ `BRIDGE_BATCH_SIZE`) ;
2. construit le payload JSON du contrat (noms, `has_clip`, prédictions secondaires seules) ;
3. `POST /nodes/{id}/sync` ;
4. adopte `synced_up_to_id` comme nouveau curseur (toujours, même s'il diffère du fichier local) ;
5. traite `want_clips` séquentiellement (upload multipart, ou signalement `missing`) ;
6. transmet le bonus `commands` à l'exécuteur (sauf en mode lecture seule).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from bridge.backoff import Backoff
from bridge.commands import CommandExecutor
from bridge.config import BridgeConfig
from bridge.http_errors import RetryDecision, classify
from bridge.species_dictionary import SpeciesDictionary
from bridge.sqlite_reader import (
    DetectionRow,
    SqliteReaderError,
    fetch_clip_name,
    fetch_detections_since,
    fetch_max_detection_id,
    fetch_predictions,
)
from bridge.state import save_state
from bridge.time_utils import unix_to_instant_str

logger = logging.getLogger(__name__)

# Une détection de moins de 120 s est considérée « possiblement en cours d'écriture » : has_clip
# reste true même si le fichier n'est pas encore sur le disque (§4.2).
_CLIP_GRACE_PERIOD_S = 120

_MAX_CLIP_UPLOAD_BYTES = 25 * 1024 * 1024  # limite serveur, api-contract.md §4.3 (413 payload_too_large)

_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/mp4",
    ".opus": "audio/ogg",
}


@dataclass
class SyncOutcome:
    should_continue_immediately: bool = False
    should_stop_loop: bool = False
    retry_decision: RetryDecision = RetryDecision.SUCCESS


def _build_detection_payload(
    row: DetectionRow,
    predictions_by_id: dict[int, list],
    clips_dir: Path,
    dictionary: SpeciesDictionary,
) -> dict:
    clip_path = clips_dir / row.clip_name if row.clip_name else None
    detection_age_s = time.time() - row.detected_at
    has_clip = bool(row.clip_name) and (
        (clip_path is not None and clip_path.is_file()) or detection_age_s < _CLIP_GRACE_PERIOD_S
    )

    raw_predictions = predictions_by_id.get(row.id, [])
    secondary = [p for p in raw_predictions if p.scientific_name != row.scientific_name][:20]

    return {
        "node_local_id": row.id,
        "detected_at_utc": unix_to_instant_str(row.detected_at),
        "scientific_name": row.scientific_name,
        "common_name": dictionary.get(row.scientific_name),
        "confidence": row.confidence,
        "source_id": row.source_id,
        "source_display_name": row.source_display_name,
        "clip_name": row.clip_name,
        "has_clip": has_clip,
        "predictions": [
            {
                "scientific_name": p.scientific_name,
                "common_name": dictionary.get(p.scientific_name),
                "confidence": p.confidence,
            }
            for p in secondary
        ],
    }


async def sync_once(
    conn: sqlite3.Connection,
    config: BridgeConfig,
    server_client: httpx.AsyncClient,
    dictionary: SpeciesDictionary,
    executor: CommandExecutor | None,
    cursor: int,
) -> tuple[int, SyncOutcome]:
    """Un cycle de synchro. Retourne le curseur (éventuellement mis à jour) et le résultat du
    cycle. Ne lève jamais d'exception réseau ni d'erreur de lecture locale de `birdnet.db` : elles
    sont capturées et traduites en `SyncOutcome` pour que l'appelant applique le backoff générique
    (§4.1) plutôt que de laisser la boucle de synchro planter."""
    await dictionary.ensure_loaded()

    try:
        rows = fetch_detections_since(conn, cursor, limit=config.batch_size)
        node_max_id = fetch_max_detection_id(conn)
        predictions_by_id = fetch_predictions(conn, [row.id for row in rows])
    except SqliteReaderError as exc:
        # Lecture locale en échec (verrou WAL transitoire, E/S disque, base déplacée pendant une
        # bascule de lieu, cf. CLAUDE.md racine « stop → mv → start ») : jamais une exception
        # réseau, mais doit suivre le même contrat de backoff (§4.1) plutôt que de faire planter
        # la boucle de synchro (et, via le TaskGroup, les trois autres boucles avec elle).
        logger.warning("Lecture locale de birdnet.db impossible (%s), backoff", exc)
        return cursor, SyncOutcome(retry_decision=RetryDecision.TRANSIENT)

    payload = {
        "since_id": cursor,
        "node_max_id": node_max_id,
        "detections": [
            _build_detection_payload(row, predictions_by_id, config.clips_dir, dictionary) for row in rows
        ],
    }

    try:
        response = await server_client.post(f"/nodes/{config.node_id}/sync", json=payload, timeout=30)
    except httpx.HTTPError as exc:
        logger.warning("POST /sync : erreur réseau (%s), backoff", exc)
        return cursor, SyncOutcome(retry_decision=RetryDecision.TRANSIENT)

    if response.status_code == 409:
        body = response.json()
        error_code = body.get("error")
        details = body.get("details") or {}
        if error_code == "cursor_ahead":
            new_cursor = int(details["synced_up_to_id"])
            logger.warning("409 cursor_ahead : curseur local %s en avance, adoption de %s", cursor, new_cursor)
            return new_cursor, SyncOutcome(should_continue_immediately=True)
        if error_code == "node_db_reset":
            logger.critical(
                "409 node_db_reset : la base BirdNET-Go du nœud est repartie à zéro (synced=%s, node_max_id=%s). "
                "Arrêt de la boucle de synchro — intervention humaine requise (réenregistrer le nœud).",
                details.get("synced_up_to_id"),
                details.get("node_max_id"),
            )
            return cursor, SyncOutcome(should_stop_loop=True)
        logger.error("409 inattendu sur /sync : %s", body)
        return cursor, SyncOutcome(retry_decision=RetryDecision.PERMANENT)

    decision = classify(response)
    if decision != RetryDecision.SUCCESS:
        logger.warning("POST /sync a échoué (%s) : %s", response.status_code, response.text[:500])
        return cursor, SyncOutcome(retry_decision=decision)

    body = response.json()
    new_cursor = int(body["synced_up_to_id"])
    if new_cursor != cursor:
        try:
            save_state(config.state_file, new_cursor)
        except OSError as exc:
            # `save_state` journalise déjà puis re-lève volontairement (state.py) pour ne jamais
            # masquer une écriture ratée à qui l'appelle directement. Ici, le curseur canonique
            # reste de toute façon `new_cursor` renvoyé par le serveur (state.py : « optimisation
            # seulement ») : un disque plein sur BRIDGE_STATE_FILE ne doit donc jamais faire
            # planter tout le cycle de sync (want_clips, commandes bonus) pour un fichier qui n'est
            # qu'un cache local.
            logger.error(
                "Écriture de l'état local (%s) impossible (%s) : curseur %s conservé en mémoire "
                "seulement, le serveur le redonnera au prochain /sync",
                config.state_file,
                exc,
                new_cursor,
            )
    if body.get("rejected"):
        logger.warning("Éléments rejetés par le serveur (curseur avancé quand même) : %s", body["rejected"])
    logger.info(
        "sync : accepted=%s duplicates=%s curseur=%s want_clips=%s",
        body.get("accepted", 0),
        body.get("duplicates", 0),
        new_cursor,
        len(body.get("want_clips", [])),
    )

    for node_local_id in body.get("want_clips", []):
        await _handle_want_clip(conn, config, server_client, node_local_id)

    if executor is not None and body.get("commands"):
        await executor.handle_batch(body["commands"])

    outcome = SyncOutcome(should_continue_immediately=len(rows) >= config.batch_size)
    return new_cursor, outcome


async def _handle_want_clip(
    conn: sqlite3.Connection,
    config: BridgeConfig,
    server_client: httpx.AsyncClient,
    node_local_id: int,
) -> None:
    clip_name = fetch_clip_name(conn, node_local_id)
    if not clip_name:
        await _report_missing(server_client, config, node_local_id, clip_name=None, reason="no_clip_name")
        return

    file_path = config.clips_dir / clip_name
    if not file_path.is_file():
        await _report_missing(server_client, config, node_local_id, clip_name=clip_name, reason="not_found")
        return

    try:
        file_size = file_path.stat().st_size
    except OSError as exc:
        logger.warning("Taille du clip %s illisible (%s)", file_path, exc)
        await _report_missing(server_client, config, node_local_id, clip_name=clip_name, reason="unreadable")
        return
    if file_size > _MAX_CLIP_UPLOAD_BYTES:
        # Le serveur rejetterait de toute façon (413 payload_too_large, §4.3) : ne jamais relire ce
        # fichier en mémoire à chaque cycle (~20 s). Le contrat ne prévoit pas de raison dédiée
        # « trop gros » pour /missing (§4.4 : not_found | unreadable | no_clip_name) — `unreadable`
        # est la plus proche des trois pour signaler que ce fichier ne peut pas être livré, ce qui
        # libère le rang côté serveur plutôt que de laisser `want_clips` le redemander indéfiniment.
        logger.error(
            "Clip %s (détection %s) : %d octets > limite serveur de %d, abandon sans upload",
            clip_name,
            node_local_id,
            file_size,
            _MAX_CLIP_UPLOAD_BYTES,
        )
        await _report_missing(server_client, config, node_local_id, clip_name=clip_name, reason="unreadable")
        return

    try:
        data = await asyncio.to_thread(file_path.read_bytes)
    except OSError as exc:
        logger.warning("Clip %s illisible (%s)", file_path, exc)
        await _report_missing(server_client, config, node_local_id, clip_name=clip_name, reason="unreadable")
        return

    content_type = _CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    files = {"audio": (file_path.name, data, content_type)}
    form = {"clip_name": clip_name}
    try:
        response = await server_client.post(
            f"/nodes/{config.node_id}/clips/{node_local_id}", data=form, files=files, timeout=30
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Upload du clip %s (détection %s) : erreur réseau (%s), sera retenté au prochain cycle",
            clip_name,
            node_local_id,
            exc,
        )
        return

    if response.status_code in (200, 201):
        logger.info("Clip %s uploadé pour la détection %s", clip_name, node_local_id)
        return
    if response.status_code == 409:
        logger.info(
            "Clip %s (détection %s) n'est plus voulu (409 clip_not_wanted), abandon",
            clip_name,
            node_local_id,
        )
        return
    if response.status_code == 404:
        logger.warning(
            "Détection %s inconnue du serveur pour l'upload du clip %s (404)",
            node_local_id,
            clip_name,
        )
        return
    if response.status_code == 413:
        logger.error(
            "Upload du clip %s (détection %s) : 413 payload_too_large côté serveur (%d octets envoyés), "
            "abandon signalé comme manquant plutôt que de réessayer indéfiniment",
            clip_name,
            node_local_id,
            file_size,
        )
        await _report_missing(server_client, config, node_local_id, clip_name=clip_name, reason="unreadable")
        return
    logger.error(
        "Upload du clip %s (détection %s) a échoué (%s) : %s",
        clip_name,
        node_local_id,
        response.status_code,
        response.text[:300],
    )


async def run_sync_loop(
    conn: sqlite3.Connection,
    config: BridgeConfig,
    server_client: httpx.AsyncClient,
    dictionary: SpeciesDictionary,
    executor: CommandExecutor | None,
    stop_event: asyncio.Event,
    *,
    initial_cursor: int,
) -> None:
    """Boucle de synchro (§4.1) : cadence `BRIDGE_SYNC_INTERVAL_S`, immédiatement à nouveau si le
    lot était plein, backoff exponentiel sur erreur réseau/5xx, arrêt propre sur `node_db_reset`."""
    backoff = Backoff()
    cursor = initial_cursor
    while not stop_event.is_set():
        cursor, outcome = await sync_once(conn, config, server_client, dictionary, executor, cursor)

        if outcome.should_stop_loop:
            return

        if outcome.should_continue_immediately:
            backoff.reset()
            continue

        if outcome.retry_decision == RetryDecision.SUCCESS:
            backoff.reset()
            delay = config.sync_interval_s
        elif outcome.retry_decision == RetryDecision.CONFIG_ERROR:
            delay = 300.0
        elif outcome.retry_decision == RetryDecision.PERMANENT:
            delay = config.sync_interval_s
        else:  # TRANSIENT, CONFLICT déjà résolu plus haut
            delay = backoff.next_delay()

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass


async def _report_missing(
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    node_local_id: int,
    *,
    clip_name: str | None,
    reason: str,
) -> None:
    try:
        response = await server_client.post(
            f"/nodes/{config.node_id}/clips/{node_local_id}/missing",
            json={"clip_name": clip_name, "reason": reason},
            timeout=15,
        )
        if response.status_code == 404:
            # detection_not_found (§4.4) : cas réel et documenté (curseur local en avance sur ce
            # que le serveur a réellement persisté, désynchro de curseur, mauvais node_id) — même
            # traitement que le 404 analogue sur l'upload de clip (ci-dessus), jamais silencieux.
            logger.warning(
                "Détection %s inconnue du serveur pour le signalement '.../missing' (404, reason=%s)",
                node_local_id,
                reason,
            )
        elif response.status_code >= 400:
            logger.warning(
                "POST .../missing (détection %s, reason=%s) a échoué (%s)",
                node_local_id,
                reason,
                response.status_code,
            )
    except httpx.HTTPError as exc:
        logger.warning("POST .../missing (détection %s) : erreur réseau (%s)", node_local_id, exc)
