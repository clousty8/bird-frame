#!/usr/bin/env python3
"""Enregistre un nœud auprès du serveur bird-frame et écrit sa config bridge.

Appelle `POST /api/v1/nodes/register` (protégé par `X-Admin-Token`, contrat §3.1) et
écrit le résultat dans `node/config/<slug>.env` (format exact du contrat §7.1, permissions
600) — c'est ce fichier que lira `node/bridge/config.py`.

Aucune dépendance externe (stdlib uniquement : `urllib`), pour pouvoir tourner avec
`uv run scripts/register_node.py ...` ou simplement `python3 scripts/register_node.py ...`
sans installation préalable.

Exemples :
    uv run scripts/register_node.py --slug pornic --site-name Pornic \\
        --node-name "Mac Armand — Pornic" --lat 47.1155 --lon -2.1046 \\
        --node-readonly

    # Ensuite, dans node/config/pornic.env : BRIDGE_NODE_ID, BRIDGE_SECRET, etc.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True, help="site_slug (contrat §1.5 : minuscules, tirets)")
    parser.add_argument("--site-name", required=True, help="Nom humain du site (ex. « Pornic »)")
    parser.add_argument("--node-name", required=True, help="Libellé humain du nœud (ex. « Mac Armand — Pornic »)")
    parser.add_argument("--timezone", default="Europe/Paris", help="Fuseau IANA du site (défaut Europe/Paris)")
    parser.add_argument("--lat", type=float, default=None, help="Latitude du site (optionnelle)")
    parser.add_argument("--lon", type=float, default=None, help="Longitude du site (optionnelle)")

    parser.add_argument(
        "--server-url",
        default=os.environ.get("BRIDGE_SERVER_URL", "http://localhost:8090"),
        help="URL du serveur, sans /api/v1 (défaut http://localhost:8090)",
    )
    parser.add_argument(
        "--admin-token",
        default=os.environ.get("BIRDFRAME_ADMIN_TOKEN"),
        help="Jeton admin du serveur (sinon variable BIRDFRAME_ADMIN_TOKEN)",
    )

    parser.add_argument(
        "--node-readonly",
        action="store_true",
        help=(
            "Mode S1 « nœud en lecture seule » (contrat §7.1, BRIDGE_NODE_READONLY) : "
            "le nœud visé est une installation BirdNET-Go de développement (ex. local-test/) "
            "que le bridge ne doit jamais muter. Écrit BRIDGE_NODE_READONLY=1 et enregistre "
            "avec auto_main_name=false (aucune commande set_main_name mise en file)."
        ),
    )

    parser.add_argument("--db-path", default=None, help="Chemin de birdnet.db du nœud (défaut : local-test/data/birdnet.db)")
    parser.add_argument("--clips-dir", default=None, help="Dossier des clips du nœud (défaut : local-test/data/clips)")
    parser.add_argument("--node-api", default="http://localhost:8080", help="API BirdNET-Go locale (défaut http://localhost:8080)")
    parser.add_argument("--sync-interval", type=int, default=20, help="BRIDGE_SYNC_INTERVAL_S (défaut 20)")
    parser.add_argument("--commands-interval", type=int, default=30, help="BRIDGE_COMMANDS_INTERVAL_S (défaut 30)")
    parser.add_argument(
        "--birdnet-pid-file",
        default=None,
        help="Fichier PID de BirdNET-Go (défaut : local-test/birdnet-go.pid) ; chaîne vide pour l'omettre",
    )
    parser.add_argument("--state-file", default=None, help="Fichier d'état du bridge (défaut : node/state/<slug>.json)")
    parser.add_argument(
        "--config-out",
        default=None,
        help="Chemin du .env à écrire (défaut : node/config/<slug>.env)",
    )
    parser.add_argument(
        "--mic-status-tool",
        default=None,
        help=(
            "Chemin optionnel vers local-test/tools/mic-status (macOS 14+, cf. CLAUDE.md racine), "
            "utilisé par le heartbeat du bridge pour déterminer mic_device_name/mic_healthy "
            "(BRIDGE_MIC_STATUS_TOOL, hors contrat §7.1, voir node/README.md). Omis par défaut."
        ),
    )
    return parser


def register(server_url: str, admin_token: str, body: dict) -> dict:
    url = server_url.rstrip("/") + "/api/v1/nodes/register"
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "X-Admin-Token": admin_token},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"Erreur du serveur ({exc.code}) : {detail}", file=sys.stderr)
        raise SystemExit(1) from exc
    except urllib.error.URLError as exc:
        print(f"Impossible de joindre le serveur ({server_url}) : {exc.reason}", file=sys.stderr)
        raise SystemExit(1) from exc


def write_config(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.admin_token:
        print(
            "Jeton admin manquant : passer --admin-token ou définir BIRDFRAME_ADMIN_TOKEN.",
            file=sys.stderr,
        )
        return 1

    body = {
        "site_slug": args.slug,
        "site_name": args.site_name,
        "node_name": args.node_name,
        "timezone": args.timezone,
        "lat": args.lat,
        "lon": args.lon,
        "auto_main_name": not args.node_readonly,
    }
    result = register(args.server_url, args.admin_token, body)

    db_path = args.db_path or str(REPO_ROOT / "local-test" / "data" / "birdnet.db")
    clips_dir = args.clips_dir or str(REPO_ROOT / "local-test" / "data" / "clips")
    state_file = args.state_file or str(REPO_ROOT / "node" / "state" / f"{args.slug}.json")
    pid_file = args.birdnet_pid_file
    if pid_file is None:
        pid_file = str(REPO_ROOT / "local-test" / "birdnet-go.pid")
    config_out = Path(args.config_out) if args.config_out else REPO_ROOT / "node" / "config" / f"{args.slug}.env"

    lines = [
        "# Généré par scripts/register_node.py — ne pas committer (voir .gitignore).",
        f"BRIDGE_SERVER_URL={args.server_url.rstrip('/')}",
        f"BRIDGE_NODE_ID={result['node_id']}",
        f"BRIDGE_SECRET={result['bridge_shared_secret']}",
        f"BRIDGE_SITE_SLUG={result['site_slug']}",
        f"BRIDGE_DB_PATH={db_path}",
        f"BRIDGE_CLIPS_DIR={clips_dir}",
        f"BRIDGE_NODE_API={args.node_api}",
        f"BRIDGE_SYNC_INTERVAL_S={args.sync_interval}",
        f"BRIDGE_COMMANDS_INTERVAL_S={args.commands_interval}",
        f"BRIDGE_STATE_FILE={state_file}",
    ]
    if pid_file:
        lines.append(f"BRIDGE_BIRDNET_PID_FILE={pid_file}")
    if args.node_readonly:
        lines.append("BRIDGE_NODE_READONLY=1")
    if args.mic_status_tool:
        lines.append(f"BRIDGE_MIC_STATUS_TOOL={args.mic_status_tool}")

    write_config(config_out, lines)

    print(f"Nœud enregistré : node_id={result['node_id']} site_slug={result['site_slug']} "
          f"(site_created={result['site_created']})")
    print(f"Config bridge écrite dans {config_out} (permissions 600, secret non ré-affiché ici).")
    if args.node_readonly:
        print("Mode lecture seule : le bridge n'exécutera aucune mutation contre BRIDGE_NODE_API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
