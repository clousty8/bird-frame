"""Bundle du bridge proposé aux nœuds pour leur mise à jour automatique (contrat §12).

`BIRDFRAME_NODE_BUNDLE` pointe vers `node-bundle-<version>.tar.gz`, produit par
`scripts/build_node_bundle.py` au build de l'image Docker. Au démarrage, le serveur :
- calcule le SHA-256 et la taille de l'archive (source de vérité, annoncée aux nœuds) ;
- compare au fichier voisin `<archive>.sha256` s'il existe (corruption → refus) ;
- lit le fichier `VERSION` de l'archive, qui DOIT être égal à la version du serveur : le nœud
  compare sa version à celle annoncée, et un bundle d'une autre version le ferait se mettre à
  jour en boucle (installer « 0.3.0 » qui contient en réalité 0.2.0).

Tout échec est journalisé en ERROR et rend le bundle indisponible (les routes répondent alors
503 `node_bundle_unavailable`) sans empêcher le reste du serveur (UI, ingestion) de tourner.
"""

from __future__ import annotations

import hashlib
import logging
import tarfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("bird_frame.node_bundle")

_CHUNK = 1024 * 1024


class NodeBundleError(Exception):
    """Bundle configuré mais inutilisable (absent, corrompu, mauvaise version)."""


@dataclass(frozen=True)
class NodeBundle:
    path: Path
    version: str
    sha256: str
    size: int


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _read_bundle_version(path: Path) -> str:
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = archive.getmember("VERSION")
            handle = archive.extractfile(member)
            if handle is None:
                raise NodeBundleError("l'entrée VERSION de l'archive n'est pas un fichier")
            return handle.read(64).decode("utf-8").strip()
    except KeyError as exc:
        raise NodeBundleError("fichier VERSION absent de l'archive") from exc
    except (tarfile.TarError, OSError, UnicodeDecodeError, EOFError) as exc:
        raise NodeBundleError(f"archive illisible ({exc})") from exc


def load_node_bundle(path: Path, expected_version: str) -> NodeBundle:
    """`path` : l'archive elle-même, ou un dossier contenant `node-bundle-<version du serveur>.tar.gz`
    (forme utilisée par l'image Docker, où le nom de fichier dépend de la version)."""
    if path.is_dir():
        path = path / f"node-bundle-{expected_version}.tar.gz"
    if not path.is_file():
        raise NodeBundleError(f"{path} introuvable")
    try:
        sha256, size = _sha256_and_size(path)
    except OSError as exc:
        raise NodeBundleError(f"{path} illisible ({exc})") from exc

    sidecar = path.with_name(path.name + ".sha256")
    if sidecar.exists():
        try:
            declared = sidecar.read_text(encoding="utf-8").split()[0].lower()
        except (OSError, IndexError, UnicodeDecodeError) as exc:
            raise NodeBundleError(f"{sidecar} illisible ({exc})") from exc
        if declared != sha256:
            raise NodeBundleError(
                f"SHA-256 de {path.name} ({sha256}) différent de {sidecar.name} ({declared})"
            )

    version = _read_bundle_version(path)
    if version != expected_version:
        raise NodeBundleError(
            f"{path.name} contient la version {version!r}, le serveur est en {expected_version!r} "
            "(le bundle doit être construit depuis le même commit que le serveur)"
        )
    return NodeBundle(path=path, version=version, sha256=sha256, size=size)
