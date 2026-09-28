"""Point d'entrée du bridge : `uv run python -m bridge --config node/config/<slug>.env [--once]`.

`--once` exécute un seul cycle de synchro puis sort (démo, cron, vérification manuelle) ; sans
cette option, les quatre boucles indépendantes tournent jusqu'à SIGINT/SIGTERM (api-contract.md
§4.1) : synchro, relais « en écoute », heartbeat, commandes (sauf `BRIDGE_NODE_READONLY=1`, où la
boucle de commandes n'est jamais lancée — §7.1).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from collections.abc import Coroutine
from typing import Any

import httpx

from bridge import __version__
from bridge.commands import CommandExecutor, run_commands_loop, run_readonly_reminder_loop
from bridge.config import BridgeConfig, ConfigError, load_config
from bridge.csrf_client import CsrfClient
from bridge.heartbeat import run_heartbeat_loop
from bridge.pending_relay import run_pending_relay
from bridge.pusher import run_sync_loop, sync_once
from bridge.species_dictionary import SpeciesDictionary
from bridge.sqlite_reader import SqliteReaderError, connect_readonly
from bridge.state import load_state

logger = logging.getLogger("bridge")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m bridge", description=__doc__)
    parser.add_argument("--config", required=True, help="Chemin vers node/config/<slug>.env")
    parser.add_argument("--once", action="store_true", help="Un seul cycle de sync, puis sortie (démo)")
    return parser.parse_args(argv)


async def _supervised(name: str, coro: Coroutine[Any, Any, None]) -> None:
    """Empêche qu'une exception inattendue dans une boucle ne tue les boucles sœurs via le
    `asyncio.TaskGroup` (celui-ci annule TOUTES les tâches dès qu'UNE lève une exception non
    gérée). Chaque boucle a déjà son propre filet pour les incidents connus (réseau, sqlite) ;
    celui-ci est le filet de dernier recours qui tient la promesse documentée (README, docstring
    ci-dessus, api-contract.md §4.1) : « une panne d'une boucle n'affecte jamais les autres ».
    N'essaie pas de relancer la boucle (elle reste arrêtée jusqu'au prochain redémarrage du
    process) : seule garantie donnée ici, ne pas propager l'échec aux autres."""
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.critical(
            "Boucle '%s' s'est arrêtée sur une exception inattendue — les autres boucles "
            "continuent de tourner (redémarrage manuel du bridge nécessaire pour la relancer)",
            name,
            exc_info=True,
        )


def _make_server_client(config: BridgeConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.api_base_url,
        headers={"Authorization": f"Bearer {config.secret}"},
    )


async def _run_once(config: BridgeConfig) -> int:
    conn = connect_readonly(config.db_path)
    try:
        state = load_state(config.state_file)
        async with _make_server_client(config) as server_client, httpx.AsyncClient() as node_client:
            dictionary = SpeciesDictionary(node_client, config.node_api)
            csrf = CsrfClient(node_client, config.node_api, config.node_api_token)
            executor = None if config.node_readonly else CommandExecutor(csrf, server_client, config, dictionary)
            cursor, outcome = await sync_once(conn, config, server_client, dictionary, executor, state.cursor)
            logger.info(
                "Cycle unique terminé : curseur=%s continue_immediatement=%s stop=%s",
                cursor,
                outcome.should_continue_immediately,
                outcome.should_stop_loop,
            )
        return 0
    finally:
        conn.close()


async def _run_forever(config: BridgeConfig) -> int:
    conn = connect_readonly(config.db_path)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # plateforme sans add_signal_handler (ex. Windows) : Ctrl+C lèvera KeyboardInterrupt

    try:
        state = load_state(config.state_file)
        async with _make_server_client(config) as server_client, httpx.AsyncClient() as node_client:
            dictionary = SpeciesDictionary(node_client, config.node_api)
            csrf = CsrfClient(node_client, config.node_api, config.node_api_token)
            executor = CommandExecutor(csrf, server_client, config, dictionary)

            if config.node_readonly:
                logger.warning(
                    "BRIDGE_NODE_READONLY=1 : mode nœud en lecture seule. La boucle de commandes ne sera "
                    "PAS lancée — aucune mutation contre %s pendant ce lot.",
                    config.node_api,
                )

            async with asyncio.TaskGroup() as tg:
                if config.node_readonly:
                    tg.create_task(
                        _supervised(
                            "readonly_reminder",
                            run_readonly_reminder_loop(server_client, config, stop_event),
                        )
                    )
                else:
                    tg.create_task(
                        _supervised("commands", run_commands_loop(server_client, config, executor, stop_event))
                    )
                tg.create_task(
                    _supervised(
                        "sync",
                        run_sync_loop(
                            conn,
                            config,
                            server_client,
                            dictionary,
                            None if config.node_readonly else executor,
                            stop_event,
                            initial_cursor=state.cursor,
                        ),
                    )
                )
                tg.create_task(
                    _supervised("pending_relay", run_pending_relay(node_client, server_client, config, stop_event))
                )
                tg.create_task(
                    _supervised(
                        "heartbeat", run_heartbeat_loop(conn, node_client, server_client, config, stop_event)
                    )
                )
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        # Erreur de configuration : jamais silencieuse, message clair sur stderr avant de sortir.
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    _setup_logging(config.log_level)
    logger.info(
        "bird-frame bridge %s — site=%s node_id=%s readonly=%s",
        __version__,
        config.site_slug,
        config.node_id,
        config.node_readonly,
    )

    try:
        connect_readonly(config.db_path).close()
    except SqliteReaderError as exc:
        logger.critical("Impossible d'ouvrir birdnet.db en lecture seule au démarrage : %s", exc)
        return 2

    if args.once:
        return asyncio.run(_run_once(config))
    return asyncio.run(_run_forever(config))


if __name__ == "__main__":
    raise SystemExit(main())
