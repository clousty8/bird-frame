"""Lecture de la configuration du bridge : `node/config/<slug>.env` (api-contract.md §7.1).

Format : `CLE=valeur`, une par ligne, pas de guillemets, `#` = commentaire, chemins absolus
obligatoires. Ce module ne fait aucune I/O réseau ni sqlite : il ne fait que parser et valider.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration manquante, mal formée ou incohérente — erreur fatale au démarrage."""


# Variables requises (§7.1) : (clé, description) pour un message d'erreur clair.
_REQUIRED = (
    "BRIDGE_SERVER_URL",
    "BRIDGE_NODE_ID",
    "BRIDGE_SECRET",
    "BRIDGE_SITE_SLUG",
    "BRIDGE_DB_PATH",
    "BRIDGE_CLIPS_DIR",
    "BRIDGE_STATE_FILE",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse un fichier `CLE=valeur` minimal (pas de guillemets, `#` = commentaire)."""
    if not path.is_file():
        raise ConfigError(f"Fichier de configuration introuvable : {path}")
    values: dict[str, str] = {}
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"{path}:{line_no} : ligne sans '=' ({raw_line!r})")
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ConfigError(f"{path}:{line_no} : clé vide ({raw_line!r})")
        values[key] = value
    return values


def _as_bool(value: str, key: str) -> bool:
    if value in ("1", "true", "True", "TRUE"):
        return True
    if value in ("0", "false", "False", "FALSE", ""):
        return False
    raise ConfigError(f"{key} : valeur booléenne invalide ({value!r}), attendu 0/1")


def _as_int(value: str, key: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{key} : entier invalide ({value!r})") from exc


def _as_float(value: str, key: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{key} : nombre invalide ({value!r})") from exc


@dataclass(frozen=True)
class BridgeConfig:
    server_url: str  # sans /api/v1 ni / final
    node_id: int
    secret: str
    site_slug: str
    db_path: str
    clips_dir: Path
    state_file: Path

    node_api: str = "http://localhost:8080"
    node_api_token: str = ""

    sync_interval_s: float = 20.0
    commands_interval_s: float = 30.0
    commands_fast_interval_s: float = 3.0
    heartbeat_interval_s: float = 60.0
    batch_size: int = 200

    birdnet_pid_file: str | None = None
    log_level: str = "INFO"
    node_readonly: bool = False

    # Amendement hors contrat (§7.1 ne prévoit pas de variable dédiée) : chemin optionnel vers
    # l'outil `local-test/tools/mic-status` (macOS 14+, cf. CLAUDE.md racine) utilisé par le
    # heartbeat pour déterminer le micro effectivement capté. Vide/absent = mic_device_name et
    # mic_healthy restent `null` dans le heartbeat (comportement conforme au contrat : « si
    # déterminable »). Voir node/README.md.
    mic_status_tool: str = ""

    # Mise à jour automatique (contrat §12.3, `bridge/updater.py`). Active seulement si
    # `auto_update` ET installation gérée (`install_root` contenant `versions/` et le lien `current`,
    # créée par `scripts/install-node.sh`). `uv_path` : chemin absolu conseillé (launchd/systemd ne
    # fournissent qu'un PATH minimal).
    auto_update: bool = False
    install_root: Path | None = None
    update_interval_s: float = 600.0
    uv_path: str = "uv"

    @property
    def api_base_url(self) -> str:
        """Base d'API du serveur, `/api/v1` inclus."""
        return f"{self.server_url}/api/v1"

    @property
    def node_command_path_prefix(self) -> str:
        return f"/nodes/{self.node_id}"


def load_config(path: str | Path) -> BridgeConfig:
    """Charge et valide `node/config/<slug>.env`. Lève `ConfigError` avec un message clair
    si une variable requise manque ou est mal formée — jamais d'échec silencieux."""
    raw = _parse_env_file(Path(path))

    missing = [key for key in _REQUIRED if not raw.get(key)]
    if missing:
        raise ConfigError(
            f"Variables requises manquantes dans {path} : {', '.join(missing)} (voir api-contract.md §7.1)"
        )

    server_url = raw["BRIDGE_SERVER_URL"].rstrip("/")
    node_api = raw.get("BRIDGE_NODE_API", "http://localhost:8080").rstrip("/")

    batch_size = _as_int(raw.get("BRIDGE_BATCH_SIZE", "200"), "BRIDGE_BATCH_SIZE")
    if not (1 <= batch_size <= 200):
        raise ConfigError(f"BRIDGE_BATCH_SIZE doit être entre 1 et 200 (reçu {batch_size})")

    install_root_raw = raw.get("BRIDGE_INSTALL_ROOT", "")
    install_root = Path(install_root_raw) if install_root_raw else None
    if install_root is not None and not install_root.is_absolute():
        raise ConfigError(f"BRIDGE_INSTALL_ROOT doit être un chemin absolu (reçu {install_root_raw!r})")
    update_interval_s = _as_float(raw.get("BRIDGE_UPDATE_INTERVAL_S", "600"), "BRIDGE_UPDATE_INTERVAL_S")
    if update_interval_s < 10:
        raise ConfigError(f"BRIDGE_UPDATE_INTERVAL_S doit être ≥ 10 s (reçu {update_interval_s})")

    config = BridgeConfig(
        server_url=server_url,
        node_id=_as_int(raw["BRIDGE_NODE_ID"], "BRIDGE_NODE_ID"),
        secret=raw["BRIDGE_SECRET"],
        site_slug=raw["BRIDGE_SITE_SLUG"],
        db_path=raw["BRIDGE_DB_PATH"],
        clips_dir=Path(raw["BRIDGE_CLIPS_DIR"]),
        state_file=Path(raw["BRIDGE_STATE_FILE"]),
        node_api=node_api,
        node_api_token=raw.get("BRIDGE_NODE_API_TOKEN", ""),
        sync_interval_s=_as_float(raw.get("BRIDGE_SYNC_INTERVAL_S", "20"), "BRIDGE_SYNC_INTERVAL_S"),
        commands_interval_s=_as_float(raw.get("BRIDGE_COMMANDS_INTERVAL_S", "30"), "BRIDGE_COMMANDS_INTERVAL_S"),
        commands_fast_interval_s=_as_float(
            raw.get("BRIDGE_COMMANDS_FAST_INTERVAL_S", "3"), "BRIDGE_COMMANDS_FAST_INTERVAL_S"
        ),
        heartbeat_interval_s=_as_float(
            raw.get("BRIDGE_HEARTBEAT_INTERVAL_S", "60"), "BRIDGE_HEARTBEAT_INTERVAL_S"
        ),
        batch_size=batch_size,
        birdnet_pid_file=raw.get("BRIDGE_BIRDNET_PID_FILE") or None,
        log_level=raw.get("BRIDGE_LOG_LEVEL", "INFO").upper(),
        node_readonly=_as_bool(raw.get("BRIDGE_NODE_READONLY", "0"), "BRIDGE_NODE_READONLY"),
        mic_status_tool=raw.get("BRIDGE_MIC_STATUS_TOOL", ""),
        auto_update=_as_bool(raw.get("BRIDGE_AUTO_UPDATE", "0"), "BRIDGE_AUTO_UPDATE"),
        install_root=install_root,
        update_interval_s=update_interval_s,
        uv_path=raw.get("BRIDGE_UV", "") or "uv",
    )
    logger.debug(
        "Configuration chargée depuis %s : node_id=%s site=%s readonly=%s",
        path,
        config.node_id,
        config.site_slug,
        config.node_readonly,
    )
    return config
