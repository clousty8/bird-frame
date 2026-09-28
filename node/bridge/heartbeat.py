"""Heartbeat (§4.6, toutes les `BRIDGE_HEARTBEAT_INTERVAL_S`, défaut 60 s).

Assemble : accessibilité + version de BirdNET-Go (`GET /api/v2/app/config`), micro effectivement
capté (outil optionnel `BRIDGE_MIC_STATUS_TOOL`, comparé à `GET /api/v2/settings/audio`), espace
disque libre du dossier clips, PID vivant (`BRIDGE_BIRDNET_PID_FILE`), instantané des seuils
dynamiques (`GET /api/v2/dynamic-thresholds`, paginé). Toutes ces lectures sont des GET publics
sur le nœud — aucune mutation, y compris en mode `BRIDGE_NODE_READONLY=1`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

import httpx

from bridge import __version__
from bridge.backoff import Backoff
from bridge.config import BridgeConfig
from bridge.http_errors import RetryDecision, classify
from bridge.sqlite_reader import SqliteReaderError, fetch_max_detection_id
from bridge.time_utils import format_instant, utc_now_str

logger = logging.getLogger(__name__)

MicStatusRunner = Callable[[str, int], Awaitable[list[str]]]


async def run_mic_status_tool(tool_path: str, pid: int) -> list[str]:
    """Exécute `local-test/tools/mic-status <pid>` (macOS 14+, CLAUDE.md racine) : une entrée
    audio capturée par ce process par ligne de sortie, `[]` si aucune ou en cas d'erreur."""
    try:
        proc = await asyncio.create_subprocess_exec(
            tool_path,
            str(pid),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except (OSError, TimeoutError) as exc:
        logger.warning("Outil mic-status (%s) inexécutable (%s)", tool_path, exc)
        return []
    if proc.returncode != 0:
        logger.warning(
            "mic-status %s a renvoyé %s : %s",
            pid,
            proc.returncode,
            stderr.decode("utf-8", errors="replace").strip(),
        )
        return []
    return [line.strip() for line in stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]


def read_pid_file(path: str | None) -> int | None:
    if not path:
        return None
    try:
        return int(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        logger.warning("PID illisible dans %s (%s)", path, exc)
        return None


def check_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # le process existe, appartient à un autre utilisateur
    return True


def disk_free_pct(clips_dir: Path) -> float | None:
    try:
        usage = shutil.disk_usage(clips_dir)
    except OSError as exc:
        logger.warning("Espace disque illisible pour %s (%s)", clips_dir, exc)
        return None
    if usage.total == 0:
        return None
    return round(usage.free / usage.total * 100, 1)


async def _fetch_app_config(node_client: httpx.AsyncClient, config: BridgeConfig) -> tuple[bool, str | None]:
    try:
        response = await node_client.get(f"{config.node_api}/api/v2/app/config", timeout=5)
    except httpx.HTTPError as exc:
        logger.warning("GET /api/v2/app/config injoignable (%s)", exc)
        return False, None
    if response.status_code != 200:
        logger.warning(
            "GET /api/v2/app/config a répondu %s (attendu 200) : %s",
            response.status_code,
            response.text[:200],
        )
        return False, None
    try:
        return True, response.json().get("version")
    except ValueError:
        return True, None


async def _expected_mic_device(node_client: httpx.AsyncClient, config: BridgeConfig) -> str | None:
    try:
        response = await node_client.get(f"{config.node_api}/api/v2/settings/audio", timeout=10)
        response.raise_for_status()
        sources = response.json().get("sources") or []
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("GET /api/v2/settings/audio illisible (%s) : mic_healthy restera null", exc)
        return None
    return sources[0].get("device") if sources else None


async def determine_mic_status(
    config: BridgeConfig,
    node_client: httpx.AsyncClient,
    pid: int | None,
    mic_status_runner: MicStatusRunner,
) -> tuple[str | None, bool | None]:
    if not config.mic_status_tool or pid is None:
        return None, None
    captured = await mic_status_runner(config.mic_status_tool, pid)
    device_name = captured[0] if captured else None
    expected = await _expected_mic_device(node_client, config)
    if expected is None:
        return device_name, None
    if not captured:
        return device_name, False
    return device_name, expected in captured


def _go_instant_or_none(value: str | None) -> str | None:
    """Instant Go RFC3339 → format du contrat, `None` pour un instant Go « zéro »
    (`0001-01-01T00:00:00Z`, utilisé par BirdNET-Go pour « jamais »)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.year <= 1:
        return None
    return format_instant(dt)


async def _fetch_dynamic_thresholds(node_client: httpx.AsyncClient, config: BridgeConfig) -> list[dict] | None:
    entries: list[dict] = []
    offset = 0
    limit = 250
    try:
        while True:
            response = await node_client.get(
                f"{config.node_api}/api/v2/dynamic-thresholds",
                params={"limit": limit, "offset": offset},
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
            data = body.get("data") or []
            entries.extend(data)
            offset += limit
            if offset >= int(body.get("total", 0)) or not data:
                break
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Lecture de /api/v2/dynamic-thresholds impossible (%s) : instantané précédent conservé",
            exc,
        )
        return None

    result: list[dict] = []
    for entry in entries:
        try:
            result.append(
                {
                    "species_name": entry["speciesName"],
                    "scientific_name": entry["scientificName"],
                    "level": entry["level"],
                    "current_value": entry["currentValue"],
                    "base_threshold": entry["baseThreshold"],
                    "high_conf_count": entry["highConfCount"],
                    "trigger_count": entry["triggerCount"],
                    "is_active": entry["isActive"],
                    "expires_at_utc": _go_instant_or_none(entry.get("expiresAt")),
                    "last_triggered_utc": _go_instant_or_none(entry.get("lastTriggered")),
                    "first_created_utc": _go_instant_or_none(entry.get("firstCreated")),
                }
            )
        except (KeyError, TypeError) as exc:
            # Un champ manquant/renommé (dérive de schéma BirdNET-Go) ne doit jamais faire
            # planter tout le heartbeat (et, via le TaskGroup, les trois autres boucles) : ignorer
            # cette seule entrée plutôt que de laisser un KeyError remonter jusqu'à
            # `run_heartbeat_loop`.
            logger.warning("Entrée de seuil dynamique incomplète ou mal formée (%s), ignorée : %s", exc, entry)
    return result


async def build_heartbeat_payload(
    conn: sqlite3.Connection,
    node_client: httpx.AsyncClient,
    config: BridgeConfig,
    *,
    mic_status_runner: MicStatusRunner = run_mic_status_tool,
) -> dict:
    pid = read_pid_file(config.birdnet_pid_file)
    reachable, version = await _fetch_app_config(node_client, config)
    mic_device_name, mic_healthy = await determine_mic_status(config, node_client, pid, mic_status_runner)
    return {
        "sent_at_utc": utc_now_str(),
        "bridge_version": __version__,
        "birdnet_go_version": version,
        "birdnet_go_reachable": reachable,
        "birdnet_go_pid_alive": check_pid_alive(pid) if pid is not None else None,
        "mic_device_name": mic_device_name,
        "mic_healthy": mic_healthy,
        "disk_free_pct": disk_free_pct(config.clips_dir),
        "node_db_max_id": fetch_max_detection_id(conn),
        "dynamic_thresholds_snapshot": await _fetch_dynamic_thresholds(node_client, config),
    }


async def run_heartbeat_loop(
    conn: sqlite3.Connection,
    node_client: httpx.AsyncClient,
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    stop_event: asyncio.Event,
    *,
    mic_status_runner: MicStatusRunner = run_mic_status_tool,
) -> None:
    backoff = Backoff()
    while not stop_event.is_set():
        try:
            payload = await build_heartbeat_payload(conn, node_client, config, mic_status_runner=mic_status_runner)
        except SqliteReaderError as exc:
            # Même classe d'incident que dans `sync_once` (verrou WAL transitoire, E/S disque,
            # base déplacée pendant une bascule de lieu) : `fetch_max_detection_id` peut lever
            # cette erreur avant même d'atteindre le POST réseau ci-dessous. Doit suivre le même
            # backoff générique (§4.1) plutôt que de faire planter la boucle heartbeat (et, via le
            # TaskGroup, les trois autres boucles avec elle).
            logger.warning("Heartbeat : lecture locale de birdnet.db impossible (%s), backoff", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff.next_delay())
            except TimeoutError:
                pass
            continue
        try:
            response = await server_client.post(f"/nodes/{config.node_id}/heartbeat", json=payload, timeout=15)
        except httpx.HTTPError as exc:
            logger.warning("POST /heartbeat : erreur réseau (%s)", exc)
            delay = backoff.next_delay()
        else:
            decision = classify(response)
            if decision == RetryDecision.SUCCESS:
                backoff.reset()
                delay = config.heartbeat_interval_s
            elif decision == RetryDecision.CONFIG_ERROR:
                logger.error(
                    "POST /heartbeat : configuration invalide (%s) : %s",
                    response.status_code,
                    response.text[:300],
                )
                delay = 300.0
            elif decision == RetryDecision.TRANSIENT:
                logger.warning("POST /heartbeat a échoué (%s), backoff", response.status_code)
                delay = backoff.next_delay()
            else:
                logger.error("POST /heartbeat rejeté (%s) : %s", response.status_code, response.text[:300])
                delay = config.heartbeat_interval_s
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass
