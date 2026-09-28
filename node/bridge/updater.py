"""Mise à jour automatique du bridge (docs/api-contract.md §12).

Ne fait rien du tout hors d'une **installation gérée** (créée par `scripts/install-node.sh`) :

    <BRIDGE_INSTALL_ROOT>/
      versions/<X.Y.Z>/     une version installée (code + `.venv` de `uv sync`)
      current -> versions/<X.Y.Z>   lien lancé par le superviseur (`node/deploy/run-bridge.sh`)
      previous              nom de la version précédente (retour arrière du superviseur)
      state/                updater.json (échecs), rolled-back-versions (écrit par le superviseur)
      downloads/            téléchargements en cours

Conditions d'activation : `BRIDGE_AUTO_UPDATE=1`, `BRIDGE_INSTALL_ROOT` défini avec `versions/` et
le lien `current`, ET ce process tourne depuis `versions/` (un bridge de développement lancé avec
la même config ne touche jamais au lien).

Cycle (au démarrage puis toutes les `BRIDGE_UPDATE_INTERVAL_S`, ou plus tôt si le heartbeat
annonce une version plus récente) : `GET /nodes/{id}/update` ; si `latest_version` > version
courante (comparaison X.Y.Z numérique) : téléchargement dans un fichier temporaire, vérification
taille + SHA-256, contrôle de chaque entrée de l'archive (ni chemin absolu, ni `..`, ni lien, ni
fichier spécial, taille totale bornée) puis extraction dans `versions/<v>`, vérification que
l'archive contient bien la version annoncée, `uv sync --frozen --no-dev`, essai à blanc
(`python -m bridge --help` avec le nouvel environnement), écriture de `previous`, bascule
**atomique** du lien `current` (rename(2) d'un lien temporaire), nettoyage des anciennes versions
(seules `current` et `previous` sont gardées), puis arrêt propre de toutes les boucles et sortie
avec `EXIT_CODE_UPDATE_APPLIED` : le superviseur relance aussitôt sur la nouvelle version.

Tout échec : journal ERROR, ancienne version intacte (dossier partiel supprimé, lien inchangé),
`update_status = {"state": "failed", …}` dans le heartbeat, et pas de nouvel essai de la même
version avant `RETRY_SAME_VERSION_AFTER_S` (1 h, mémorisé dans `state/updater.json`, donc
aussi après un redémarrage). Une version annulée par le superviseur (3 plantages au démarrage,
`state/rolled-back-versions`) n'est plus jamais retentée automatiquement.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx

import bridge
from bridge import __version__
from bridge.config import BridgeConfig
from bridge.http_errors import error_code

logger = logging.getLogger(__name__)

# Code de sortie « mise à jour appliquée, relancez-moi » (EX_TEMPFAIL de sysexits.h), attendu par
# node/deploy/run-bridge.sh, qui relance alors immédiatement la version pointée par `current`.
EXIT_CODE_UPDATE_APPLIED = 75

RETRY_SAME_VERSION_AFTER_S = 3600.0
MAX_BUNDLE_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 5000
UV_SYNC_TIMEOUT_S = 900.0
SMOKE_TEST_TIMEOUT_S = 60.0
MAX_ERROR_CHARS = 1000

_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INIT_VERSION_RE = re.compile(r'^__version__ = "([^"]*)"$', re.MULTILINE)
_REQUIRED_FILES = ("VERSION", "pyproject.toml", "uv.lock", "bridge/__init__.py", "bridge/__main__.py")


class UpdateError(Exception):
    """Échec d'une tentative de mise à jour (message destiné au journal et au heartbeat)."""


class _CheckFailed(Exception):
    """Impossible de savoir s'il existe une mise à jour (serveur injoignable, pas de bundle…)."""


def parse_version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _SEMVER_RE.match(value)
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    """`candidate` > `current` en comparaison X.Y.Z numérique (1.10.0 > 1.9.0). Une version
    illisible n'est jamais « plus récente »."""
    cand, cur = parse_version(candidate), parse_version(current)
    if cand is None or cur is None:
        return False
    return cand > cur


def validate_archive_members(members: list[tarfile.TarInfo]) -> None:
    """Refuse toute archive qui pourrait écrire hors du dossier cible ou l'inonder : chemin absolu,
    composant `..`, lien symbolique ou physique, fichier spécial, nombre ou taille excessifs.
    (Vérifié AVANT toute extraction ; l'extraction utilise en plus le filtre « data » de tarfile.)"""
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise UpdateError(f"archive refusée : {len(members)} entrées (maximum {MAX_ARCHIVE_MEMBERS})")
    total = 0
    for member in members:
        name = member.name
        if not name or name.startswith("/") or "\\" in name or re.match(r"^[A-Za-z]:", name):
            raise UpdateError(f"archive refusée : chemin absolu ou invalide {name!r}")
        if ".." in PurePosixPath(name).parts:
            raise UpdateError(f"archive refusée : chemin sortant du dossier cible {name!r}")
        if member.issym() or member.islnk():
            raise UpdateError(f"archive refusée : lien {name!r} -> {member.linkname!r}")
        if not (member.isfile() or member.isdir()):
            raise UpdateError(f"archive refusée : type de fichier non autorisé pour {name!r}")
        total += member.size if member.isfile() else 0
        if total > MAX_EXTRACTED_BYTES:
            raise UpdateError(f"archive refusée : plus de {MAX_EXTRACTED_BYTES} octets une fois extraite")


def _truncate(message: str) -> str:
    return message if len(message) <= MAX_ERROR_CHARS else message[: MAX_ERROR_CHARS - 1] + "…"


@dataclass(frozen=True)
class ManagedInstall:
    root: Path

    @property
    def versions_dir(self) -> Path:
        return self.root / "versions"

    @property
    def current_link(self) -> Path:
        return self.root / "current"

    @property
    def previous_file(self) -> Path:
        return self.root / "previous"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def downloads_dir(self) -> Path:
        return self.root / "downloads"

    @property
    def rolled_back_file(self) -> Path:
        return self.state_dir / "rolled-back-versions"

    @property
    def updater_state_file(self) -> Path:
        return self.state_dir / "updater.json"

    def current_version_name(self) -> str | None:
        try:
            return Path(os.readlink(self.current_link)).name
        except OSError:
            return None


def detect_managed_install(config: BridgeConfig, package_dir: Path) -> tuple[ManagedInstall | None, str | None]:
    """(installation, None) si la mise à jour automatique est possible, sinon (None, raison)."""
    if not config.auto_update:
        return None, "BRIDGE_AUTO_UPDATE n'est pas à 1"
    root = config.install_root
    if root is None:
        return None, "BRIDGE_INSTALL_ROOT n'est pas défini"
    install = ManagedInstall(root)
    if not install.versions_dir.is_dir() or not install.current_link.is_symlink():
        return None, f"{root} n'est pas une installation gérée (versions/ ou lien current absent)"
    try:
        package_dir.resolve().relative_to(install.versions_dir.resolve())
    except ValueError:
        return None, (
            f"ce bridge tourne depuis {package_dir}, hors de {install.versions_dir} "
            "(process de développement ?) : le lien current n'est jamais touché depuis ce process"
        )
    return install, None


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def switch_symlink_atomically(link: Path, target: str) -> None:
    """Fait pointer `link` vers `target` (chemin relatif) sans instant où le lien n'existe pas."""
    tmp = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    os.symlink(target, tmp)
    try:
        os.replace(tmp, link)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class Updater:
    def __init__(
        self,
        config: BridgeConfig,
        server_client: httpx.AsyncClient,
        *,
        current_version: str = __version__,
        package_dir: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._config = config
        self._client = server_client
        self._current_version = current_version
        self._clock = clock
        self._wake = asyncio.Event()
        self.exit_code: int | None = None
        self.install, self.disabled_reason = detect_managed_install(
            config, package_dir or Path(bridge.__file__).resolve().parent
        )
        self.status: dict[str, str | None] = {
            "state": "pending" if self.install else "disabled",
            "target_version": None,
            "error": None,
        }

    @property
    def enabled(self) -> bool:
        return self.install is not None

    def status_payload(self) -> dict[str, str | None]:
        """`update_status` du heartbeat (contrat §12.4)."""
        return dict(self.status)

    # --- État persistant (échecs, versions annulées par le superviseur) -----------------------

    def _load_failures(self) -> dict[str, dict]:
        assert self.install is not None
        path = self.install.updater_state_file
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.warning("État de mise à jour illisible (%s), ignoré : %s", path, exc)
            return {}
        failures = data.get("failures") if isinstance(data, dict) else None
        return failures if isinstance(failures, dict) else {}

    def _record_failure(self, version: str, error: str) -> None:
        assert self.install is not None
        failures = self._load_failures()
        failures[version] = {"at": self._clock(), "error": error}
        try:
            _write_text_atomic(
                self.install.updater_state_file, json.dumps({"failures": failures}, ensure_ascii=False, indent=2)
            )
        except OSError as exc:
            logger.error(
                "Impossible d'enregistrer l'échec de mise à jour dans %s : %s", self.install.state_dir, exc
            )

    def _recent_failure(self, version: str) -> dict | None:
        failure = self._load_failures().get(version)
        if not isinstance(failure, dict):
            return None
        at = failure.get("at")
        if not isinstance(at, int | float) or self._clock() - at >= RETRY_SAME_VERSION_AFTER_S:
            return None
        return failure

    def _rolled_back_versions(self) -> set[str]:
        assert self.install is not None
        try:
            lines = self.install.rolled_back_file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return set()
        except OSError as exc:
            logger.warning("%s illisible : %s", self.install.rolled_back_file, exc)
            return set()
        return {line.strip() for line in lines if line.strip()}

    def _blocked(self, version: str) -> bool:
        return version in self._rolled_back_versions() or self._recent_failure(version) is not None

    def _set_status(self, state: str, target: str | None, error: str | None, level: int) -> None:
        new = {"state": state, "target_version": target, "error": _truncate(error) if error else None}
        if new != self.status:
            detail = f" : {new['error']}" if new["error"] else ""
            logger.log(level, "Mise à jour du bridge — état %s (cible %s)%s", state, target or "—", detail)
        self.status = new

    # --- Déclenchement --------------------------------------------------------------------

    def notify_latest_version(self, latest: object) -> None:
        """Appelé par le heartbeat avec `latest_node_version` : réveille la boucle tout de suite si
        une version plus récente, non bloquée, est publiée (au lieu d'attendre l'intervalle)."""
        if not self.enabled or not isinstance(latest, str):
            return
        if is_newer(latest, self._current_version) and not self._blocked(latest):
            self._wake.set()

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.enabled:
            logger.info("Mise à jour automatique du bridge désactivée : %s", self.disabled_reason)
            return
        logger.info(
            "Mise à jour automatique active (installation %s, version %s, vérification toutes les %.0f s)",
            self._config.install_root,
            self._current_version,
            self._config.update_interval_s,
        )
        while not stop_event.is_set():
            self._wake.clear()
            restart = await self._check_unless_stopped(stop_event)
            if restart is None:
                return
            if restart:
                logger.warning(
                    "Version %s installée : arrêt du bridge (code %s) pour relance par le superviseur",
                    self.status["target_version"],
                    EXIT_CODE_UPDATE_APPLIED,
                )
                stop_event.set()
                return
            await self._sleep(stop_event)

    async def _check_unless_stopped(self, stop_event: asyncio.Event) -> bool | None:
        """`check_once()`, annulé si l'arrêt du bridge est demandé pendant qu'il tourne (SIGTERM :
        launchd/systemd n'attendent pas la fin d'un `uv sync`). L'annulation laisse la version
        courante intacte (dossier partiel supprimé, sous-process tué). `None` = annulé."""
        check = asyncio.create_task(self.check_once())
        stopper = asyncio.create_task(stop_event.wait())
        try:
            await asyncio.wait({check, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stopper
            if not check.done():
                check.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await check
        if check.cancelled():
            logger.warning("Arrêt demandé pendant une vérification/installation de mise à jour : abandonnée")
            return None
        try:
            return check.result()
        except Exception as exc:  # filet : jamais d'arrêt silencieux de la boucle
            logger.error("Mise à jour du bridge : erreur inattendue", exc_info=exc)
            self._set_status("check_failed", None, f"erreur inattendue : {exc!r}", logging.ERROR)
            return False

    async def _sleep(self, stop_event: asyncio.Event) -> None:
        waiters = [asyncio.create_task(stop_event.wait()), asyncio.create_task(self._wake.wait())]
        try:
            await asyncio.wait(
                waiters, timeout=self._config.update_interval_s, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for waiter in waiters:
                waiter.cancel()
            for waiter in waiters:
                with contextlib.suppress(asyncio.CancelledError):
                    await waiter

    async def check_once(self) -> bool:
        """Un cycle complet. Renvoie True si une nouvelle version est installée et que le process
        doit s'arrêter (avec `self.exit_code`) pour être relancé dessus."""
        if not self.enabled:
            return False
        try:
            info = await self._fetch_update_info()
        except _CheckFailed as exc:
            self._set_status("check_failed", None, str(exc), logging.WARNING)
            return False

        latest = info["latest_version"]
        if not is_newer(latest, self._current_version):
            self._set_status("up_to_date", latest, None, logging.INFO)
            return False
        if latest in self._rolled_back_versions():
            self._set_status(
                "failed",
                latest,
                f"version {latest} annulée par le superviseur après des plantages au démarrage "
                f"({self.install.rolled_back_file}) : plus retentée automatiquement — publier une version "
                "plus récente, ou retirer la ligne de ce fichier pour réessayer",
                logging.ERROR,
            )
            return False
        recent = self._recent_failure(latest)
        if recent is not None:
            self._set_status("failed", latest, str(recent.get("error") or "échec précédent"), logging.ERROR)
            logger.debug("Version %s en échec il y a moins d'une heure : pas de nouvel essai", latest)
            return False

        self._set_status("updating", latest, None, logging.INFO)
        try:
            await self._install(info)
        except UpdateError as exc:
            message = str(exc)
            self._record_failure(latest, message)
            self._set_status("failed", latest, message, logging.ERROR)
            logger.error(
                "Mise à jour %s → %s abandonnée, la version %s reste en place (nouvel essai dans 1 h au plus tôt)",
                self._current_version,
                latest,
                self._current_version,
            )
            return False
        self.exit_code = EXIT_CODE_UPDATE_APPLIED
        return True

    # --- Étapes ---------------------------------------------------------------------------

    async def _fetch_update_info(self) -> dict:
        path = f"/nodes/{self._config.node_id}/update"
        try:
            response = await self._client.get(path, timeout=15)
        except httpx.HTTPError as exc:
            raise _CheckFailed(f"serveur injoignable pour GET {path} ({exc!r})") from exc
        if response.status_code == 404 and error_code(response) == "node_bundle_not_configured":
            raise _CheckFailed("le serveur ne publie pas de bundle de mise à jour (BIRDFRAME_NODE_BUNDLE vide)")
        if response.status_code != 200:
            raise _CheckFailed(f"GET {path} a répondu {response.status_code} : {response.text[:300]}")
        try:
            info = response.json()
        except ValueError as exc:
            raise _CheckFailed(f"GET {path} : réponse non JSON ({exc})") from exc
        if not isinstance(info, dict):
            raise _CheckFailed(f"GET {path} : réponse inattendue {info!r}"[:300])
        problems = []
        if parse_version(info.get("latest_version")) is None:
            problems.append(f"latest_version={info.get('latest_version')!r}")
        if not isinstance(info.get("bundle_sha256"), str) or not _SHA256_RE.match(info["bundle_sha256"]):
            problems.append("bundle_sha256 invalide")
        size = info.get("bundle_size")
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_BUNDLE_BYTES:
            problems.append(f"bundle_size={size!r}")
        if not isinstance(info.get("bundle_url"), str) or not info["bundle_url"]:
            problems.append("bundle_url absent")
        if problems:
            raise _CheckFailed(f"GET {path} : réponse invalide ({', '.join(problems)})")
        return info

    def _bundle_url(self, bundle_url: str) -> str:
        """URL absolue du bundle, obligatoirement sur la même origine que le serveur (le secret du
        nœud part dans l'en-tête Authorization : jamais vers un autre hôte)."""
        server = httpx.URL(self._config.server_url)
        url = server.join(bundle_url)
        if (url.scheme, url.host, url.port) != (server.scheme, server.host, server.port):
            raise UpdateError(f"bundle_url {bundle_url!r} hors de l'origine du serveur {self._config.server_url}")
        return str(url)

    async def _download(self, info: dict, destination: Path) -> None:
        url = self._bundle_url(info["bundle_url"])
        expected_size: int = info["bundle_size"]
        digest = hashlib.sha256()
        received = 0
        try:
            async with self._client.stream("GET", url, timeout=httpx.Timeout(60.0, connect=15.0)) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise UpdateError(
                        f"téléchargement du bundle : HTTP {response.status_code} {response.text[:200]}"
                    )
                with destination.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        if received > expected_size:
                            raise UpdateError(f"bundle plus gros qu'annoncé ({expected_size} octets) : refusé")
                        digest.update(chunk)
                        handle.write(chunk)
        except httpx.HTTPError as exc:
            raise UpdateError(f"téléchargement du bundle interrompu ({exc!r})") from exc
        if received != expected_size:
            raise UpdateError(f"bundle tronqué : {received} octets reçus, {expected_size} annoncés")
        actual = digest.hexdigest()
        if actual != info["bundle_sha256"]:
            raise UpdateError(f"SHA-256 du bundle invalide : attendu {info['bundle_sha256']}, obtenu {actual}")

    @staticmethod
    def _extract(archive_path: Path, target_dir: Path, version: str) -> None:
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                validate_archive_members(members)
                names = {PurePosixPath(m.name).as_posix() for m in members if m.isfile()}
                missing = [name for name in _REQUIRED_FILES if name not in names]
                if missing:
                    raise UpdateError(f"archive incomplète : {', '.join(missing)} absent(s)")
                target_dir.mkdir(parents=True)
                archive.extractall(target_dir, members=members, filter="data")
        except (tarfile.TarError, OSError, EOFError) as exc:
            raise UpdateError(f"extraction du bundle impossible ({exc})") from exc
        declared = (target_dir / "VERSION").read_text(encoding="utf-8").strip()
        code_versions = _INIT_VERSION_RE.findall(
            (target_dir / "bridge" / "__init__.py").read_text(encoding="utf-8")
        )
        if declared != version or code_versions != [version]:
            raise UpdateError(
                f"le bundle annoncé en {version} contient VERSION={declared!r}, __version__={code_versions!r}"
            )

    async def _run(self, argv: list[str], cwd: Path, timeout: float, what: str) -> None:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONHOME")
        }
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise UpdateError(f"{what} : impossible de lancer {argv[0]!r} ({exc})") from exc
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as exc:
            await self._kill(proc)
            raise UpdateError(f"{what} : délai de {timeout:.0f} s dépassé") from exc
        except asyncio.CancelledError:
            await self._kill(proc)
            raise
        if proc.returncode != 0:
            output = (stderr or stdout).decode("utf-8", errors="replace").strip()
            raise UpdateError(f"{what} a échoué (code {proc.returncode}) : {output[-600:]}")

    @staticmethod
    async def _kill(proc: asyncio.subprocess.Process) -> None:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()

    @staticmethod
    def _discard(target_dir: Path) -> None:
        shutil.rmtree(target_dir, ignore_errors=True)
        if target_dir.exists():
            logger.error("Dossier partiel %s impossible à supprimer (sera retenté au prochain essai)", target_dir)

    def _prune_old_versions(self, keep: set[str]) -> None:
        assert self.install is not None
        for entry in self.install.versions_dir.iterdir():
            if entry.name in keep or not entry.is_dir() or parse_version(entry.name) is None:
                continue
            try:
                shutil.rmtree(entry)
                logger.info("Ancienne version du bridge supprimée : %s", entry)
            except OSError as exc:
                logger.warning("Impossible de supprimer l'ancienne version %s : %s", entry, exc)

    async def _install(self, info: dict) -> None:
        assert self.install is not None
        install = self.install
        version: str = info["latest_version"]
        target_dir = install.versions_dir / version
        running = install.current_version_name()
        if running == version:
            raise UpdateError(
                f"current pointe déjà sur {version} alors que ce process est en {self._current_version}"
            )

        install.downloads_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f"node-bundle-{version}.", suffix=".part", dir=install.downloads_dir
        )
        os.close(fd)
        archive_path = Path(tmp_name)
        extracted = False
        try:
            await self._download(info, archive_path)
            if target_dir.exists():
                logger.warning("Reste d'une tentative précédente supprimé avant réinstallation : %s", target_dir)
                shutil.rmtree(target_dir)
            extracted = True
            self._extract(archive_path, target_dir, version)
            await self._run(
                [self._config.uv_path, "sync", "--frozen", "--no-dev"], target_dir, UV_SYNC_TIMEOUT_S, "uv sync"
            )
            python = target_dir / ".venv" / "bin" / "python"
            await self._run(
                [str(python), "-m", "bridge", "--help"], target_dir, SMOKE_TEST_TIMEOUT_S, "essai à blanc"
            )
            if running:
                _write_text_atomic(install.previous_file, f"{running}\n")
            switch_symlink_atomically(install.current_link, f"versions/{version}")
        except (UpdateError, asyncio.CancelledError):
            if extracted:
                self._discard(target_dir)
            raise
        except OSError as exc:
            if extracted:
                self._discard(target_dir)
            raise UpdateError(f"erreur disque pendant l'installation ({exc})") from exc
        except Exception as exc:
            if extracted:
                self._discard(target_dir)
            raise UpdateError(f"erreur inattendue pendant l'installation ({exc!r})") from exc
        finally:
            archive_path.unlink(missing_ok=True)

        logger.info("Lien current basculé : %s → %s (previous = %s)", running, version, running)
        self._prune_old_versions({version, running} if running else {version})
