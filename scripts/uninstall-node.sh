#!/bin/bash
# bird-frame — désinstalle le bridge géré installé par scripts/install-node.sh.
#
# Usage :
#   scripts/uninstall-node.sh [--root ~/.bird-frame-node] [--label fr.birdframe.bridge]
#                             [--purge] [--no-launchd]
#
# Décharge et supprime l'agent launchd (~/Library/LaunchAgents/<label>.plist), puis supprime le code
# installé (versions/, current, previous, bin/, downloads/). Garde config/ (secret du nœud), state/
# (curseur, historique des mises à jour) et logs/, sauf --purge qui supprime toute la racine.
# Ne touche jamais à local-test/ ni à BirdNET-Go.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$HOME/.bird-frame-node"
LABEL="fr.birdframe.bridge"
PURGE=0
USE_LAUNCHD=1

die() {
  echo "✗ $*" >&2
  exit 1
}
info() { echo "• $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?--root requiert un dossier}"; shift 2 ;;
    --label) LABEL="${2:?--label requiert une valeur}"; shift 2 ;;
    --purge) PURGE=1; shift ;;
    --no-launchd) USE_LAUNCHD=0; shift ;;
    -h | --help) sed -n '2,12p' "$0"; exit 0 ;;
    *) die "argument inconnu : $1 (voir --help)" ;;
  esac
done

case "$ROOT" in
  "~") ROOT="$HOME" ;;
  "~/"*) ROOT="$HOME/${ROOT#\~/}" ;;
esac
case "$ROOT" in
  /*) ;;
  *) ROOT="$(pwd)/$ROOT" ;;
esac
ROOT="${ROOT%/}"
[ -n "$ROOT" ] && [ "$ROOT" != "$HOME" ] && [ "$ROOT" != "$REPO_ROOT" ] || die "racine refusée : '$ROOT'"
case "$ROOT/" in
  "$REPO_ROOT/local-test/"*) die "racine refusée : $ROOT est dans local-test/" ;;
esac

if [ "$USE_LAUNCHD" = 1 ] && [ "$(uname -s)" = "Darwin" ]; then
  GUI_DOMAIN="gui/$(id -u)"
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "$GUI_DOMAIN/$LABEL" || die "launchctl bootout $GUI_DOMAIN/$LABEL a échoué"
    info "agent launchd $LABEL arrêté et déchargé"
  else
    info "agent launchd $LABEL non chargé"
  fi
  if [ -f "$PLIST" ]; then
    rm -f "$PLIST"
    info "supprimé : $PLIST"
  fi
fi

if [ ! -e "$ROOT" ]; then
  info "$ROOT n'existe pas : rien d'autre à supprimer"
  exit 0
fi
# Garde-fou avant tout rm -rf : la racine doit ressembler à une installation gérée.
if [ ! -d "$ROOT/versions" ] && [ ! -L "$ROOT/current" ] && [ ! -f "$ROOT/config/bridge.env" ]; then
  die "$ROOT ne ressemble pas à une installation gérée (ni versions/, ni current, ni config/bridge.env) : rien supprimé"
fi

if [ "$PURGE" = 1 ]; then
  rm -rf "$ROOT"
  info "supprimé entièrement (--purge) : $ROOT"
else
  rm -rf "$ROOT/versions" "$ROOT/bin" "$ROOT/downloads" "$ROOT/current" "$ROOT/previous"
  rm -f "$ROOT"/.current.*.tmp
  info "code du bridge supprimé ; conservés : $ROOT/config (secret du nœud), $ROOT/state, $ROOT/logs"
  info "tout supprimer : scripts/uninstall-node.sh --root $ROOT --purge"
fi
echo "✓ bridge géré désinstallé"
