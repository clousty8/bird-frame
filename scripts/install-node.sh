#!/bin/bash
# bird-frame — installe le bridge de CE dépôt comme « installation gérée » mise à jour
# automatiquement par le serveur (docs/api-contract.md §12), et son agent launchd (macOS).
#
# Usage :
#   scripts/install-node.sh --config node/config/pornic.env [--root ~/.bird-frame-node]
#                           [--label fr.birdframe.bridge] [--uv /chemin/vers/uv] [--no-launchd]
#
# Crée (ou remet à neuf, idempotent) :
#   <racine>/versions/<X.Y.Z>/   code du bridge (node/bridge, pyproject.toml, uv.lock, VERSION) + .venv
#   <racine>/current             lien vers versions/<X.Y.Z> (bascule atomique)
#   <racine>/previous            version précédemment installée (retour arrière du superviseur)
#   <racine>/config/bridge.env   copie de --config (chmod 600) où sont FORCÉS BRIDGE_INSTALL_ROOT,
#                                BRIDGE_AUTO_UPDATE=1, BRIDGE_UV et BRIDGE_STATE_FILE (<racine>/state/)
#   <racine>/bin/run-bridge.sh   superviseur (node/deploy/run-bridge.sh)
#   <racine>/state/ logs/ downloads/
#   ~/Library/LaunchAgents/<label>.plist, chargé (sauf --no-launchd ; Linux : voir
#   node/deploy/bird-frame-bridge.service.template, non installé automatiquement).
#
# Ne touche JAMAIS à local-test/ (refuse une racine qui s'y trouve) ; ne lance ni n'arrête
# BirdNET-Go. Réinstaller : relancer la même commande. Désinstaller : scripts/uninstall-node.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$HOME/.bird-frame-node"
LABEL="fr.birdframe.bridge"
CONFIG_SRC=""
UV_BIN=""
USE_LAUNCHD=1

die() {
  echo "✗ $*" >&2
  exit 1
}
info() { echo "• $*"; }
warn() { echo "⚠ $*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONFIG_SRC="${2:?--config requiert un fichier}"; shift 2 ;;
    --root) ROOT="${2:?--root requiert un dossier}"; shift 2 ;;
    --label) LABEL="${2:?--label requiert une valeur}"; shift 2 ;;
    --uv) UV_BIN="${2:?--uv requiert un chemin}"; shift 2 ;;
    --no-launchd) USE_LAUNCHD=0; shift ;;
    -h | --help) sed -n '2,23p' "$0"; exit 0 ;;
    *) die "argument inconnu : $1 (voir --help)" ;;
  esac
done

# --- Vérifications ---------------------------------------------------------------------------
[ -n "$CONFIG_SRC" ] || die "--config <fichier .env du nœud> est obligatoire (voir scripts/register_node.py)"
[ -f "$CONFIG_SRC" ] || die "configuration introuvable : $CONFIG_SRC"
CONFIG_SRC="$(cd "$(dirname "$CONFIG_SRC")" && pwd)/$(basename "$CONFIG_SRC")"

case "$ROOT" in
  "~") ROOT="$HOME" ;;
  "~/"*) ROOT="$HOME/${ROOT#\~/}" ;;
esac
case "$ROOT" in
  /*) ;;
  *) ROOT="$(pwd)/$ROOT" ;;
esac
ROOT="${ROOT%/}"
[ -n "$ROOT" ] && [ "$ROOT" != "$HOME" ] || die "racine refusée : '$ROOT' (choisir un dossier dédié)"
case "$ROOT/" in
  "$REPO_ROOT/local-test/"*) die "racine refusée : $ROOT est dans local-test/, qui ne doit jamais être modifié" ;;
esac
if [ "$ROOT" = "$REPO_ROOT" ]; then die "racine refusée : c'est le dépôt lui-même"; fi

VERSION="$(tr -d '[:space:]' <"$REPO_ROOT/VERSION")"
CODE_VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$REPO_ROOT/node/bridge/__init__.py")"
[ "$VERSION" = "$CODE_VERSION" ] ||
  die "VERSION ($VERSION) ≠ node/bridge/__init__.py ($CODE_VERSION) : lancer python3 scripts/bump.py --check"

if [ -z "$UV_BIN" ]; then UV_BIN="$(command -v uv || true)"; fi
[ -n "$UV_BIN" ] || die "uv introuvable (https://docs.astral.sh/uv/) — ou préciser --uv /chemin/vers/uv"
case "$UV_BIN" in
  /*) ;;
  *) UV_BIN="$(cd "$(dirname "$UV_BIN")" && pwd)/$(basename "$UV_BIN")" ;;
esac
[ -x "$UV_BIN" ] || die "uv non exécutable : $UV_BIN"

config_value() {
  sed -n "s/^[[:space:]]*$1=\(.*\)$/\1/p" "$CONFIG_SRC" | tail -n 1 | sed 's/[[:space:]]*$//'
}
SLUG="$(config_value BRIDGE_SITE_SLUG)"
[ -n "$SLUG" ] || die "BRIDGE_SITE_SLUG absent de $CONFIG_SRC"
case "$SLUG" in
  *[!A-Za-z0-9_-]*) die "BRIDGE_SITE_SLUG invalide pour un nom de fichier : '$SLUG'" ;;
esac
OLD_STATE_FILE="$(config_value BRIDGE_STATE_FILE)"

OS="$(uname -s)"
if [ "$USE_LAUNCHD" = 1 ] && [ "$OS" != "Darwin" ]; then
  warn "$OS : pas de launchd. Installation des fichiers seulement ; service systemd : voir" \
    "node/deploy/bird-frame-bridge.service.template."
  USE_LAUNCHD=0
fi
GUI_DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# --- 1. Arrêt de l'agent existant (réinstallation) --------------------------------------------
if [ "$USE_LAUNCHD" = 1 ] && launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
  info "arrêt de l'agent launchd $LABEL en cours…"
  launchctl bootout "$GUI_DOMAIN/$LABEL" || warn "launchctl bootout a échoué (on continue)"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1 || break
    sleep 1
  done
fi

# --- 2. Arborescence ----------------------------------------------------------------------------
mkdir -p "$ROOT/versions" "$ROOT/config" "$ROOT/state" "$ROOT/logs" "$ROOT/bin" "$ROOT/downloads"
chmod 700 "$ROOT/config" "$ROOT/state"

# --- 3. Version du dépôt dans versions/<X.Y.Z> ------------------------------------------------
TARGET="$ROOT/versions/$VERSION"
BACKUP=""
if [ -e "$TARGET" ]; then
  BACKUP="$ROOT/versions/.$VERSION.avant-reinstallation.$$"
  mv "$TARGET" "$BACKUP"
fi
INSTALL_DONE=0
restore_on_failure() {
  if [ "$INSTALL_DONE" = 1 ]; then return; fi
  rm -rf "$TARGET"
  if [ -n "$BACKUP" ] && [ -e "$BACKUP" ]; then
    mv "$BACKUP" "$TARGET"
    echo "✗ installation interrompue : $TARGET restauré dans son état précédent" >&2
  else
    echo "✗ installation interrompue : $TARGET supprimé, current inchangé" >&2
  fi
}
trap restore_on_failure EXIT

info "copie du bridge $VERSION dans $TARGET"
mkdir -p "$TARGET"
(cd "$REPO_ROOT/node" && tar -cf - --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
  --exclude='tests' bridge pyproject.toml uv.lock) | (cd "$TARGET" && tar -xf -)
printf '%s\n' "$VERSION" >"$TARGET/VERSION"

info "uv sync --frozen --no-dev ($UV_BIN)"
(cd "$TARGET" && env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT "$UV_BIN" sync --frozen --no-dev)
PYTHON="$TARGET/.venv/bin/python"
(cd "$TARGET" && "$PYTHON" -m bridge --help >/dev/null) || die "le bridge installé ne démarre pas (python -m bridge --help)"

# --- 4. Configuration ----------------------------------------------------------------------------
DEST_CONFIG="$ROOT/config/bridge.env"
TMP_CONFIG="$(mktemp "$ROOT/config/.bridge.env.XXXXXX")"
chmod 600 "$TMP_CONFIG"
{
  echo "# Copié par scripts/install-node.sh depuis $CONFIG_SRC — relancer ce script après toute"
  echo "# modification de l'original (les modifications faites ici seraient écrasées)."
  grep -v -E '^[[:space:]]*(BRIDGE_INSTALL_ROOT|BRIDGE_AUTO_UPDATE|BRIDGE_UV|BRIDGE_STATE_FILE)=' \
    "$CONFIG_SRC" | grep -v -E '^# (Copié par scripts/install-node.sh|modification de l.original|--- Forcé par)' || true
  echo "# --- Forcé par install-node.sh (installation gérée, docs/api-contract.md §12) ---"
  echo "BRIDGE_INSTALL_ROOT=$ROOT"
  echo "BRIDGE_AUTO_UPDATE=1"
  echo "BRIDGE_UV=$UV_BIN"
  echo "BRIDGE_STATE_FILE=$ROOT/state/$SLUG.json"
} >"$TMP_CONFIG"
(cd "$TARGET" && "$PYTHON" -c 'import sys; from bridge.config import load_config; load_config(sys.argv[1])' \
  "$TMP_CONFIG") || {
  rm -f "$TMP_CONFIG"
  die "configuration refusée par le bridge (voir le message ci-dessus)"
}
mv -f "$TMP_CONFIG" "$DEST_CONFIG"
if [ ! -f "$ROOT/state/$SLUG.json" ] && [ -n "$OLD_STATE_FILE" ] && [ -f "$OLD_STATE_FILE" ]; then
  cp "$OLD_STATE_FILE" "$ROOT/state/$SLUG.json"
  info "curseur local repris de $OLD_STATE_FILE (optimisation ; le curseur du serveur fait foi)"
fi

# --- 5. Superviseur, bascule de current -----------------------------------------------------
install -m 755 "$REPO_ROOT/node/deploy/run-bridge.sh" "$ROOT/bin/run-bridge.sh"

OLD_VERSION=""
if [ -L "$ROOT/current" ]; then OLD_VERSION="$(basename "$(readlink "$ROOT/current")")"; fi
if [ -n "$OLD_VERSION" ] && [ "$OLD_VERSION" != "$VERSION" ] && [ -d "$ROOT/versions/$OLD_VERSION" ]; then
  printf '%s\n' "$OLD_VERSION" >"$ROOT/previous"
fi
TMP_LINK="$ROOT/.current.$$.tmp"
rm -f "$TMP_LINK"
ln -s "versions/$VERSION" "$TMP_LINK"
if [ "$OS" = "Darwin" ]; then mv -fh "$TMP_LINK" "$ROOT/current"; else mv -fT "$TMP_LINK" "$ROOT/current"; fi
: >"$ROOT/state/supervisor-crashes"
INSTALL_DONE=1
trap - EXIT
if [ -n "$BACKUP" ]; then rm -rf "$BACKUP"; fi
info "current → versions/$VERSION${OLD_VERSION:+ (précédente : $OLD_VERSION)}"

# --- 6. Agent launchd ----------------------------------------------------------------------------
if [ "$USE_LAUNCHD" = 1 ]; then
  mkdir -p "$(dirname "$PLIST")"
  ROOT_XML="$ROOT"
  ROOT_XML="${ROOT_XML//&/&amp;}"
  ROOT_XML="${ROOT_XML//</&lt;}"
  ROOT_XML="${ROOT_XML//>/&gt;}"
  TEMPLATE="$(cat "$REPO_ROOT/node/deploy/fr.birdframe.bridge.plist.template")"
  TEMPLATE="${TEMPLATE//__ROOT__/$ROOT_XML}"
  TEMPLATE="${TEMPLATE//__LABEL__/$LABEL}"
  printf '%s\n' "$TEMPLATE" >"$PLIST"
  plutil -lint "$PLIST" >/dev/null || die "plist invalide : $PLIST"
  launchctl bootstrap "$GUI_DOMAIN" "$PLIST" || die "launchctl bootstrap $GUI_DOMAIN $PLIST a échoué"
  info "agent launchd $LABEL chargé ($PLIST)"
else
  info "agent launchd non installé (--no-launchd). Lancement manuel : $ROOT/bin/run-bridge.sh $ROOT"
fi

# --- 7. Avertissements ---------------------------------------------------------------------------
for key in BRIDGE_DB_PATH BRIDGE_CLIPS_DIR BRIDGE_MIC_STATUS_TOOL BRIDGE_BIRDNET_PID_FILE; do
  value="$(config_value "$key")"
  case "$value" in
    "$HOME/Documents/"* | "$HOME/Desktop/"* | "$HOME/Downloads/"*)
      if [ "$OS" = "Darwin" ] && [ "$USE_LAUNCHD" = 1 ]; then
        warn "$key=$value est dans un dossier protégé par macOS (Documents/Bureau/Téléchargements) :" \
          "un agent launchd peut s'y voir refuser l'accès (« Operation not permitted » dans" \
          "$ROOT/logs/bridge.log). Si c'est le cas : Réglages Système → Confidentialité et sécurité →" \
          "Accès complet au disque → ajouter $(cd "$TARGET" && "$PYTHON" -c 'import os, sys; print(os.path.realpath(sys.executable))')" \
          "(et /bin/bash)."
      fi
      ;;
  esac
done
if [ -f "$REPO_ROOT/.dev/pids/bridge.pid" ] && kill -0 "$(cat "$REPO_ROOT/.dev/pids/bridge.pid")" 2>/dev/null; then
  warn "un bridge de développement tourne aussi (scripts/dev-up.sh, pid $(cat "$REPO_ROOT/.dev/pids/bridge.pid"))" \
    "pour le même nœud : n'en garder qu'un (scripts/dev-down.sh arrête celui de dev)."
fi

echo
echo "✓ bridge $VERSION installé dans $ROOT"
echo "  Journaux :        tail -f $ROOT/logs/bridge.log"
if [ "$USE_LAUNCHD" = 1 ]; then
  echo "  État de l'agent : launchctl print $GUI_DOMAIN/$LABEL | grep -E 'state|pid|last exit'"
  echo "  Redémarrer :      launchctl kickstart -k $GUI_DOMAIN/$LABEL"
fi
echo "  Mise à jour :     automatique (BRIDGE_AUTO_UPDATE=1), état dans le heartbeat (update_status)"
echo "  Désinstaller :    scripts/uninstall-node.sh --root $ROOT"
