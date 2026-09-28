"""Client CSRF + file de commandes (WP-11, api-contract.md §5).

`CommandExecutor` exécute localement, contre `BRIDGE_NODE_API`, les commandes créées par le
serveur (`node_commands`), puis en accuse réception. Toutes les commandes sont idempotentes par
construction (§5.1) : une redélivrance ne doit jamais faire de dégâts.

Handlers implémentés et testés (respx) : `set_species_threshold`, `exclude_species`,
`unexclude_species`, `include_species`, `uninclude_species`, `reset_dynamic_threshold`,
`set_main_name`, `mark_detection_reviewed`.

Handlers `start_live` / `live_heartbeat` / `stop_live` : squelette conforme aux routes du contrat
(§5.3), **non testés en réel** (pas de session HLS disponible pendant ce lot) — voir node/README.md.
Un `kind` du contrat qui n'aurait toujours pas de handler (évolution future du contrat) est
journalisé en ERROR et jamais acquitté, pour qu'il reste visible et redélivré plutôt que
silencieusement perdu.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from bridge.backoff import Backoff
from bridge.config import BridgeConfig
from bridge.csrf_client import CsrfClient
from bridge.http_errors import RetryDecision, classify
from bridge.species_dictionary import SpeciesDictionary
from bridge.time_utils import parse_instant, utc_now_str

logger = logging.getLogger(__name__)

_DEDUPE_WINDOW_S = 30 * 60  # 30 min (§5.1)
_LIVE_HEARTBEAT_PERIOD_S = 20.0  # cadence du heartbeat HLS auto-maintenu par le bridge (§5.3)


class PermanentCommandError(Exception):
    """Échec permanent : la commande est acquittée `failed` avec ce message."""


class TransientCommandError(Exception):
    """Échec transitoire (nœud injoignable, timeout, 5xx) : pas d'ack, le serveur redélivrera."""


# ---------------------------------------------------------------------------------------------
# Aides communes aux handlers `species.config`
# ---------------------------------------------------------------------------------------------


def _target_names(payload: dict) -> list[str]:
    scientific_name = payload["scientific_name"]
    aliases = payload.get("aliases") or []
    return [scientific_name, *aliases]


def _lookup_common_name(dictionary: SpeciesDictionary, names: list[str]) -> str | None:
    """Le dictionnaire FR du nœud (`GET /api/v2/species/dictionary/fr`) est indexé sur le nom
    BRUT/label du nœud (ex. `Coloeus monedula`), pas forcément le nom canonique envoyé par le
    serveur (ex. `Corvus monedula`, api-contract.md §1.6). Essayer chaque nom candidat
    (scientifique canonique puis alias) plutôt que le seul nom canonique, sinon la clé « nom
    commun FR » masquante (§5.3) n'est jamais trouvée pour une espèce aliasée."""
    for name in names:
        common_name = dictionary.get(name)
        if common_name:
            return common_name
    return None


async def _get_settings_section(csrf: CsrfClient, section: str) -> dict:
    response = await csrf.request("GET", f"/api/v2/settings/{section}")
    _raise_for_node_response(response, f"GET /api/v2/settings/{section}")
    return response.json()


async def _get_full_settings(csrf: CsrfClient) -> dict:
    response = await csrf.request("GET", "/api/v2/settings")
    _raise_for_node_response(response, "GET /api/v2/settings")
    return response.json()


def _raise_for_node_response(response: httpx.Response, what: str) -> None:
    if response.status_code >= 500:
        raise TransientCommandError(f"{what} : {response.status_code} (nœud en erreur)")
    if response.status_code >= 400:
        raise PermanentCommandError(f"{what} : {response.status_code} {response.text[:500]}")


# ---------------------------------------------------------------------------------------------
# set_species_threshold
# ---------------------------------------------------------------------------------------------


async def handle_set_species_threshold(
    csrf: CsrfClient, _config: BridgeConfig, dictionary: SpeciesDictionary, payload: dict
) -> dict:
    threshold = payload.get("threshold")
    names = _target_names(payload)

    if threshold is not None:
        keys = {name.lower() for name in names}
        common_name = _lookup_common_name(dictionary, names)
        if common_name:
            current = await _get_settings_section(csrf, "species")
            existing_config = current.get("config") or {}
            if common_name.lower() in {k.lower() for k in existing_config}:
                keys.add(common_name.lower())
        config_patch = {key: {"threshold": threshold} for key in keys}
        response = await csrf.request("PATCH", "/api/v2/settings/species", json_body={"config": config_patch})
        _raise_for_node_response(response, "PATCH /api/v2/settings/species (threshold)")
        body = response.json()
        return {
            "changed": True,
            "keys": sorted(keys),
            "restart_required": bool(body.get("restart_required", False)),
        }

    # threshold == None : retirer le seuil personnalisé — PATCH ne peut pas supprimer une clé
    # (fusion, §5.3), seul PUT /api/v2/settings (objet complet) le permet.
    full = await _get_full_settings(csrf)
    species_section = full.get("realtime", {}).get("species", {})
    species_config = species_section.get("config") or {}
    match_names = {name.lower() for name in names}
    common_name = _lookup_common_name(dictionary, names)
    if common_name:
        match_names.add(common_name.lower())
    removed_keys = [key for key in list(species_config) if key.lower() in match_names]
    if not removed_keys:
        return {"changed": False, "keys": [], "restart_required": False}
    for key in removed_keys:
        del species_config[key]
    species_section["config"] = species_config
    full["realtime"]["species"] = species_section
    response = await csrf.request("PUT", "/api/v2/settings", json_body=full)
    _raise_for_node_response(response, "PUT /api/v2/settings (retrait de seuil)")
    body = response.json()
    return {
        "changed": True,
        "keys": sorted(removed_keys),
        "restart_required": bool(body.get("restart_required", False)),
    }


# ---------------------------------------------------------------------------------------------
# exclude_species / include_species
# ---------------------------------------------------------------------------------------------


async def _toggle_species_list(csrf: CsrfClient, payload: dict, *, list_name: str, add: bool) -> dict:
    names = _target_names(payload)
    current = await _get_settings_section(csrf, "species")
    existing: list[str] = list(current.get(list_name) or [])
    existing_lower = {n.lower() for n in existing}
    match_lower = {n.lower() for n in names}

    if add:
        new_list = existing + [name for name in names if name.lower() not in existing_lower]
        changed = len(new_list) != len(existing)
    else:
        new_list = [n for n in existing if n.lower() not in match_lower]
        changed = len(new_list) != len(existing)

    if not changed:
        return {"changed": False, "list": list_name, "restart_required": False}

    response = await csrf.request("PATCH", "/api/v2/settings/species", json_body={list_name: new_list})
    _raise_for_node_response(response, f"PATCH /api/v2/settings/species ({list_name})")
    body = response.json()
    return {
        "changed": True,
        "list": list_name,
        "restart_required": bool(body.get("restart_required", False)),
    }


async def handle_exclude_species(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    return await _toggle_species_list(csrf, payload, list_name="exclude", add=True)


async def handle_include_species(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    return await _toggle_species_list(csrf, payload, list_name="include", add=True)


async def handle_unexclude_species(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    return await _toggle_species_list(csrf, payload, list_name="exclude", add=False)


async def handle_uninclude_species(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    return await _toggle_species_list(csrf, payload, list_name="include", add=False)


# ---------------------------------------------------------------------------------------------
# reset_dynamic_threshold
# ---------------------------------------------------------------------------------------------


async def handle_reset_dynamic_threshold(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    names = {n.lower() for n in _target_names(payload)}
    matches: list[str] = []
    offset = 0
    limit = 250
    while True:
        response = await csrf.request(
            "GET", "/api/v2/dynamic-thresholds", params={"limit": limit, "offset": offset}
        )
        _raise_for_node_response(response, "GET /api/v2/dynamic-thresholds")
        body = response.json()
        entries = body.get("data") or []
        for entry in entries:
            if str(entry.get("scientificName", "")).lower() in names:
                matches.append(entry["speciesName"])
        offset += limit
        if offset >= int(body.get("total", 0)) or not entries:
            break

    reset_names: list[str] = []
    for species_name in matches:
        response = await csrf.request("DELETE", f"/api/v2/dynamic-thresholds/{quote(species_name, safe='')}")
        _raise_for_node_response(response, f"DELETE /api/v2/dynamic-thresholds/{species_name}")
        reset_names.append(species_name)
    return {"reset": reset_names}


# ---------------------------------------------------------------------------------------------
# set_main_name
# ---------------------------------------------------------------------------------------------


async def handle_set_main_name(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> dict:
    name = payload["name"]
    response = await csrf.request("PATCH", "/api/v2/settings/main", json_body={"name": name})
    _raise_for_node_response(response, "PATCH /api/v2/settings/main")
    verify = await csrf.request("GET", "/api/v2/settings/main")
    _raise_for_node_response(verify, "GET /api/v2/settings/main (vérification)")
    actual = verify.json().get("name")
    if actual != name:
        raise PermanentCommandError(f"main.name toujours '{actual}' après PATCH (attendu '{name}')")
    return {"name": name}


# ---------------------------------------------------------------------------------------------
# mark_detection_reviewed
# ---------------------------------------------------------------------------------------------


async def handle_mark_detection_reviewed(
    csrf: CsrfClient, _config: BridgeConfig, _dictionary: SpeciesDictionary, payload: dict
) -> None:
    node_local_id = payload["node_local_id"]
    verified = payload["verified"]
    comment = payload.get("comment")
    body: dict = {"verified": verified}
    if comment is not None:
        body["comment"] = comment
    response = await csrf.request("POST", f"/api/v2/detections/{node_local_id}/review", json_body=body)
    # 404 (détection supprimée du nœud) et 409 (détection verrouillée) sont déjà couverts par
    # `_raise_for_node_response` (>=400 → PermanentCommandError, §5.3).
    _raise_for_node_response(response, f"POST /api/v2/detections/{node_local_id}/review")
    return None


# ---------------------------------------------------------------------------------------------
# start_live / live_heartbeat / stop_live — SQUELETTE, NON TESTÉ EN RÉEL (vague 4, WP-19).
# Les noms de champs JSON de la réponse HLSStreamStatus sont une hypothèse (camelCase, cohérent
# avec le reste de l'API v2 observé) : à vérifier contre un vrai flux avant la vague 4.
# ---------------------------------------------------------------------------------------------


@dataclass
class LiveSession:
    session_id: str
    source_id: str
    stream_token: str
    heartbeat_task: asyncio.Task | None = None
    expires_at_monotonic: float = field(default_factory=lambda: time.monotonic() + 60.0)


class LiveSessionRegistry:
    """État en mémoire des sessions HLS actives maintenues par ce bridge (squelette WP-19)."""

    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}

    def get(self, session_id: str) -> LiveSession | None:
        return self._sessions.get(session_id)

    def add(self, session: LiveSession) -> None:
        self._sessions[session.session_id] = session

    def remove(self, session_id: str) -> LiveSession | None:
        return self._sessions.pop(session_id, None)

    def all_sessions(self) -> list[LiveSession]:
        return list(self._sessions.values())

    @property
    def any_active(self) -> bool:
        return bool(self._sessions)


async def _first_audio_source_id(csrf: CsrfClient) -> str:
    response = await csrf.request("GET", "/api/v2/system/audio/sources")
    _raise_for_node_response(response, "GET /api/v2/system/audio/sources")
    sources = response.json().get("sources") or []
    if not sources:
        raise PermanentCommandError("Aucune source audio disponible sur le nœud (system/audio/sources vide)")
    return sources[0]["id"]


async def _auto_stop_expired_session(
    csrf: CsrfClient, registry: LiveSessionRegistry, session: LiveSession
) -> None:
    """Contrat §5.3 : « session terminée automatiquement si aucun `live_heartbeat` n'est reçu
    pendant 60 s (→ même action que `stop_live`) ». `expires_at_monotonic` était jusqu'ici écrit
    (création + chaque `live_heartbeat`) mais jamais lu : sans ce garde-fou, une session orpheline
    (client disparu sans jamais envoyer `stop_live`) maintenait un encodage HLS actif sur le nœud
    indéfiniment."""
    logger.warning(
        "Session live %s expirée (aucun live_heartbeat reçu depuis plus de 60 s) : arrêt automatique",
        session.session_id,
    )
    registry.remove(session.session_id)
    try:
        response = await csrf.request(
            "POST",
            f"/api/v2/streams/hls/{quote(session.source_id, safe='')}/stop",
            json_body={"session_id": session.session_id},
        )
        if response.status_code >= 400:
            logger.warning(
                "Arrêt automatique de la session live %s a échoué (%s) : %s",
                session.session_id,
                response.status_code,
                response.text[:300],
            )
    except httpx.HTTPError as exc:
        logger.warning("Arrêt automatique de la session live %s : erreur réseau (%s)", session.session_id, exc)


async def _hls_heartbeat_loop(csrf: CsrfClient, registry: LiveSessionRegistry, session_id: str) -> None:
    """Maintient le flux HLS vivant (POST .../heartbeat toutes les ~20 s) tant que la session
    existe dans le registre. Annulé par `stop_live`, ou par expiration (60 s sans `live_heartbeat`,
    §5.3)."""
    try:
        while True:
            await asyncio.sleep(_LIVE_HEARTBEAT_PERIOD_S)
            session = registry.get(session_id)
            if session is None:
                return
            if time.monotonic() > session.expires_at_monotonic:
                await _auto_stop_expired_session(csrf, registry, session)
                return
            try:
                response = await csrf.request(
                    "POST",
                    "/api/v2/streams/hls/heartbeat",
                    json_body={
                        "stream_token": session.stream_token,
                        "session_id": session.session_id,
                    },
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Heartbeat HLS session=%s a échoué (%s) : %s",
                        session_id,
                        response.status_code,
                        response.text[:300],
                    )
            except httpx.HTTPError as exc:
                logger.warning("Heartbeat HLS session=%s : erreur réseau (%s)", session_id, exc)
    except asyncio.CancelledError:
        return


async def handle_start_live(
    csrf: CsrfClient,
    _config: BridgeConfig,
    _dictionary: SpeciesDictionary,
    payload: dict,
    *,
    registry: LiveSessionRegistry,
) -> dict:
    session_id = payload["session_id"]
    source_id = payload.get("source_id") or await _first_audio_source_id(csrf)
    response = await csrf.request(
        "POST",
        f"/api/v2/streams/hls/{quote(source_id, safe='')}/start",
        json_body={"session_id": session_id},
    )
    _raise_for_node_response(response, "POST /api/v2/streams/hls/:sourceID/start")
    body = response.json()
    stream_token = body.get("streamToken") or body.get("stream_token")
    if not stream_token:
        raise PermanentCommandError(f"Pas de stream_token dans la réponse HLS start : {body}")

    session = LiveSession(session_id=session_id, source_id=source_id, stream_token=stream_token)
    session.heartbeat_task = asyncio.create_task(_hls_heartbeat_loop(csrf, registry, session_id))
    registry.add(session)

    return {
        "source_id": source_id,
        "stream_token": stream_token,
        "playlist_url": body.get("playlistUrl") or body.get("playlist_url"),
        "status": body.get("status"),
        "playlist_ready": body.get("playlistReady", body.get("playlist_ready", False)),
        "stream_epoch_utc": body.get("streamEpoch") or body.get("stream_epoch_utc"),
    }


async def handle_live_heartbeat(
    _csrf: CsrfClient,
    _config: BridgeConfig,
    _dictionary: SpeciesDictionary,
    payload: dict,
    *,
    registry: LiveSessionRegistry,
) -> None:
    session_id = payload["session_id"]
    session = registry.get(session_id)
    if session is None:
        raise PermanentCommandError("unknown_session")
    session.expires_at_monotonic = time.monotonic() + 60.0
    return None


async def handle_stop_live(
    csrf: CsrfClient,
    _config: BridgeConfig,
    _dictionary: SpeciesDictionary,
    payload: dict,
    *,
    registry: LiveSessionRegistry,
) -> None:
    session_id = payload["session_id"]
    session = registry.remove(session_id)
    if session is None:
        return None  # déjà terminée : idempotent, applied
    if session.heartbeat_task is not None:
        session.heartbeat_task.cancel()
    response = await csrf.request(
        "POST",
        f"/api/v2/streams/hls/{quote(session.source_id, safe='')}/stop",
        json_body={"session_id": session_id},
    )
    _raise_for_node_response(response, "POST /api/v2/streams/hls/:sourceID/stop")
    return None


# ---------------------------------------------------------------------------------------------
# Exécuteur : dispatch, déduplication, ack
# ---------------------------------------------------------------------------------------------

_SIMPLE_HANDLERS = {
    "set_species_threshold": handle_set_species_threshold,
    "exclude_species": handle_exclude_species,
    "unexclude_species": handle_unexclude_species,
    "include_species": handle_include_species,
    "uninclude_species": handle_uninclude_species,
    "reset_dynamic_threshold": handle_reset_dynamic_threshold,
    "set_main_name": handle_set_main_name,
    "mark_detection_reviewed": handle_mark_detection_reviewed,
}
_LIVE_HANDLERS = {
    "start_live": handle_start_live,
    "live_heartbeat": handle_live_heartbeat,
    "stop_live": handle_stop_live,
}


class CommandExecutor:
    def __init__(
        self,
        csrf: CsrfClient,
        server_client: httpx.AsyncClient,
        config: BridgeConfig,
        dictionary: SpeciesDictionary,
    ) -> None:
        self._csrf = csrf
        self._server_client = server_client
        self._config = config
        self._dictionary = dictionary
        self._executed_at: dict[int, float] = {}  # command_id -> monotonic, fenêtre de dédup 30 min
        self.live_sessions = LiveSessionRegistry()

    def _seen_recently(self, command_id: int) -> bool:
        self._prune_seen()
        return command_id in self._executed_at

    def _mark_seen(self, command_id: int) -> None:
        self._executed_at[command_id] = time.monotonic()

    def _prune_seen(self) -> None:
        cutoff = time.monotonic() - _DEDUPE_WINDOW_S
        for command_id in [cid for cid, seen_at in self._executed_at.items() if seen_at < cutoff]:
            del self._executed_at[command_id]

    async def handle_batch(self, commands: list[dict]) -> None:
        """Exécute une par une, par id croissant, en ignorant les doublons déjà traités
        (poll et bonus du /sync peuvent livrer la même commande). Une commande n'est marquée
        « vue » que si elle a effectivement été acquittée (§5.1) : sinon une redélivrance légitime
        d'une commande jamais acquittée (échec transitoire, nœud injoignable) serait sautée en
        silence pendant toute la fenêtre de dédup (30 min)."""
        for command in sorted(commands, key=lambda c: c["id"]):
            if self._seen_recently(command["id"]):
                continue
            acked = await self._execute_and_ack(command)
            if acked:
                self._mark_seen(command["id"])

    async def _execute_and_ack(self, command: dict) -> bool:
        """Retourne `True` si la commande a été acquittée (applied ou failed) — seul cas où elle
        doit entrer dans la déduplication."""
        command_id = command["id"]
        kind = command["kind"]
        payload = command.get("payload") or {}

        expires_at = command.get("expires_at")
        if expires_at and parse_instant(expires_at) < parse_instant(utc_now_str()):
            await self._ack(command_id, "failed", error="expired")
            return True

        if kind == "set_species_threshold":
            # La clé « nom commun FR » masquante (§5.3) dépend du dictionnaire du nœud. Il est
            # normalement chargé par le premier `sync_once`, mais la boucle de commandes démarre
            # en premier (§4.1) et peut donc exécuter une commande déjà en file avant que ce
            # premier cycle n'ait eu lieu : le garantir ici plutôt que d'en dépendre implicitement.
            await self._dictionary.ensure_loaded()

        if kind in _LIVE_HANDLERS:
            handler = _LIVE_HANDLERS[kind]
            call = handler(self._csrf, self._config, self._dictionary, payload, registry=self.live_sessions)
        elif kind in _SIMPLE_HANDLERS:
            handler = _SIMPLE_HANDLERS[kind]
            call = handler(self._csrf, self._config, self._dictionary, payload)
        else:
            logger.error(
                "Commande id=%s kind=%s : aucun handler pour ce kind — ni exécutée ni acquittée, "
                "restera pending/redélivrée jusqu'à ce qu'un lot ultérieur l'implémente",
                command_id,
                kind,
            )
            return False

        try:
            result = await call
        except TransientCommandError as exc:
            logger.warning(
                "Commande id=%s kind=%s : échec transitoire (%s), pas d'ack, redélivrance à venir",
                command_id,
                kind,
                exc,
            )
            return False
        except PermanentCommandError as exc:
            logger.error("Commande id=%s kind=%s : échec permanent (%s)", command_id, kind, exc)
            await self._ack(command_id, "failed", error=str(exc))
            return True
        except httpx.HTTPError as exc:
            logger.warning(
                "Commande id=%s kind=%s : erreur réseau vers le nœud (%s), pas d'ack",
                command_id,
                kind,
                exc,
            )
            return False
        except Exception:
            logger.exception(
                "Commande id=%s kind=%s : erreur inattendue, pas d'ack (sera redélivrée)",
                command_id,
                kind,
            )
            return False

        await self._ack(command_id, "applied", result=result)
        return True

    async def _ack(
        self,
        command_id: int,
        status: str,
        *,
        result: object | None = None,
        error: str | None = None,
    ) -> None:
        body = {"status": status, "result": result, "error": error}
        try:
            response = await self._server_client.post(
                f"/nodes/{self._config.node_id}/commands/{command_id}/ack", json=body
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Ack de la commande id=%s impossible (erreur réseau : %s) — le serveur redélivrera",
                command_id,
                exc,
            )
            return
        decision = classify(response)
        if decision == RetryDecision.SUCCESS:
            logger.info("Commande id=%s acquittée %s", command_id, status)
            return
        if response.status_code == 409:
            logger.info("Commande id=%s déjà finalisée côté serveur (409), ignoré", command_id)
            return
        logger.error(
            "Ack de la commande id=%s a échoué (%s) : %s",
            command_id,
            response.status_code,
            response.text[:300],
        )


# ---------------------------------------------------------------------------------------------
# Boucle de poll (§4.1, §4.7) — cadence adaptative : rapide pendant une session live active ou
# dans les 120 s après réception d'une commande, lente sinon.
# ---------------------------------------------------------------------------------------------


async def _fetch_commands(server_client: httpx.AsyncClient, config: BridgeConfig) -> list[dict] | None:
    """Un cycle de `GET /nodes/{id}/commands`. Retourne `None` sur erreur (le générique de
    §4.1 s'applique alors dans l'appelant), sinon la liste `commands` (peut être vide)."""
    try:
        response = await server_client.get(f"/nodes/{config.node_id}/commands", params={"limit": 20})
    except httpx.HTTPError as exc:
        logger.warning("GET /commands : erreur réseau (%s)", exc)
        return None
    decision = classify(response)
    if decision != RetryDecision.SUCCESS:
        logger.warning("GET /commands a échoué (%s) : %s", response.status_code, response.text[:300])
        return None
    return response.json().get("commands", [])


async def run_commands_loop(
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    executor: CommandExecutor,
    stop_event: asyncio.Event,
) -> None:
    """Boucle principale de commandes (WP-11). N'est jamais lancée en mode
    `BRIDGE_NODE_READONLY=1` — voir `run_readonly_reminder_loop`."""
    backoff = Backoff()
    fast_until = 0.0
    while not stop_event.is_set():
        commands = await _fetch_commands(server_client, config)
        if commands is None:
            delay = backoff.next_delay()
        else:
            backoff.reset()
            if commands:
                fast_until = time.monotonic() + 120.0
                await executor.handle_batch(commands)
            fast = executor.live_sessions.any_active or time.monotonic() < fast_until
            delay = config.commands_fast_interval_s if fast else config.commands_interval_s
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass


async def run_readonly_reminder_loop(
    server_client: httpx.AsyncClient,
    config: BridgeConfig,
    stop_event: asyncio.Event,
    *,
    interval_s: float = 3600.0,
) -> None:
    """Mode `BRIDGE_NODE_READONLY=1` (§7.1) : la boucle de commandes n'est **jamais** lancée
    (aucune mutation contre le nœud de développement). On se contente de lire, sans exécuter ni
    acquitter, le nombre de commandes en attente côté serveur, pour qu'Armand ne les découvre pas
    à l'aveugle. Un WARNING immédiat au démarrage, puis un rappel toutes les heures."""

    async def _log_pending_count() -> None:
        commands = await _fetch_commands(server_client, config)
        count = len(commands) if commands is not None else "?"
        logger.warning(
            "BRIDGE_NODE_READONLY=1 : %s commande(s) en attente côté serveur, nœud en lecture seule, "
            "aucune mutation ne sera exécutée contre %s",
            count,
            config.node_api,
        )

    await _log_pending_count()
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        except TimeoutError:
            await _log_pending_count()
