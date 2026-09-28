#!/bin/bash
# bird-frame — superviseur du bridge dans une installation gérée (docs/api-contract.md §12).
#
# Lancé par launchd (macOS, fr.birdframe.bridge.plist) ou systemd (Raspberry Pi,
# bird-frame-bridge.service), qui le relancent à chaque sortie (KeepAlive / Restart=always).
#
#   run-bridge.sh <racine>        # ou : BRIDGE_INSTALL_ROOT=<racine> run-bridge.sh
#
# À chaque lancement :
# 1. lit la version pointée par <racine>/current (lien vers versions/<X.Y.Z>) ;
# 2. lance <racine>/versions/<X.Y.Z>/.venv/bin/python -m bridge --config <racine>/config/bridge.env
#    depuis ce dossier, et relaie SIGTERM/SIGINT/SIGHUP au bridge (arrêt propre) ;
# 3. à la sortie du bridge :
#    - code 0 (arrêt normal) ou arrêt demandé par signal : sort en 0 ;
#    - code 75 (nouvelle version installée par bridge/updater.py, `current` déjà basculé) :
#      se relance immédiatement (exec) sur la nouvelle version, sans attendre launchd/systemd ;
#    - sinon, si le bridge a tourné moins de BRIDGE_SUPERVISOR_STARTUP_WINDOW_S (60 s) et que le
#      code n'est pas 2 (configuration ou birdnet.db inaccessibles : la faute à l'environnement, pas
#      à la version) : compte un « plantage au démarrage » de cette version (state/supervisor-crashes).
#      Au 3e (BRIDGE_SUPERVISOR_MAX_CRASHES) en 5 min (BRIDGE_SUPERVISOR_CRASH_WINDOW_S), rebascule
#      `current` sur la version du fichier `previous`, ajoute la version fautive à
#      state/rolled-back-versions (l'updater ne la retentera plus) et supprime `previous` ;
#    - sort avec le code du bridge (launchd/systemd relancent après leur délai de throttling).
#
# Compatible bash 3.2 (celui de macOS). Ne touche jamais qu'à <racine>.

set -u

ROOT="${1:-${BRIDGE_INSTALL_ROOT:-}}"
if [ -z "$ROOT" ]; then
  echo "usage : run-bridge.sh <racine de l'installation gérée>" >&2
  exit 64
fi
ROOT="${ROOT%/}"
CONFIG="${BRIDGE_CONFIG_FILE:-$ROOT/config/bridge.env}"
STATE_DIR="$ROOT/state"
CRASH_LOG="$STATE_DIR/supervisor-crashes"
ROLLED_BACK="$STATE_DIR/rolled-back-versions"
STARTUP_WINDOW_S="${BRIDGE_SUPERVISOR_STARTUP_WINDOW_S:-60}"
CRASH_WINDOW_S="${BRIDGE_SUPERVISOR_CRASH_WINDOW_S:-300}"
MAX_CRASHES="${BRIDGE_SUPERVISOR_MAX_CRASHES:-3}"
MAX_IMMEDIATE_RELAUNCHES=5
EXIT_UPDATE_APPLIED=75
EXIT_ENVIRONMENT=2

log() {
  printf '%s run-bridge[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" "$*" >&2
}

current_version() {
  local target
  target="$(readlink "$ROOT/current" 2>/dev/null)" || return 1
  [ -n "$target" ] || return 1
  basename "$target"
}

# Fait pointer current sur versions/$1 sans instant où le lien n'existe pas (rename(2)).
switch_current() {
  local tmp="$ROOT/.current.$$.tmp"
  rm -f "$tmp"
  ln -s "versions/$1" "$tmp" || return 1
  case "$(uname -s)" in
    Darwin) mv -fh "$tmp" "$ROOT/current" ;;
    *) mv -fT "$tmp" "$ROOT/current" ;;
  esac
}

record_crash() {
  mkdir -p "$STATE_DIR"
  echo "$2 $1" >>"$CRASH_LOG"
  # Ne garde que les 50 dernières lignes (le fichier ne doit pas grossir indéfiniment).
  if [ "$(wc -l <"$CRASH_LOG")" -gt 50 ]; then
    tail -n 50 "$CRASH_LOG" >"$CRASH_LOG.tmp" && mv -f "$CRASH_LOG.tmp" "$CRASH_LOG"
  fi
}

recent_crashes() {
  [ -f "$CRASH_LOG" ] || { echo 0; return; }
  awk -v v="$1" -v now="$2" -v w="$CRASH_WINDOW_S" \
    '$2 == v && now - $1 < w { n++ } END { print n + 0 }' "$CRASH_LOG"
}

rollback() {
  local bad="$1" count="$2" prev=""
  if [ -f "$ROOT/previous" ]; then
    prev="$(tr -d '[:space:]' <"$ROOT/previous")"
  fi
  if [ -z "$prev" ] || [ "$prev" = "$bad" ] || [ ! -x "$ROOT/versions/$prev/.venv/bin/python" ]; then
    log "ERREUR : la version $bad a planté $count fois au démarrage en ${CRASH_WINDOW_S}s, mais aucune" \
      "version précédente utilisable (previous='${prev}') : pas de retour arrière possible."
    return 1
  fi
  if ! switch_current "$prev"; then
    log "ERREUR : retour arrière de $bad vers $prev impossible (bascule du lien current échouée)."
    return 1
  fi
  mkdir -p "$STATE_DIR"
  echo "$bad" >>"$ROLLED_BACK"
  rm -f "$ROOT/previous"
  : >"$CRASH_LOG"
  log "RETOUR ARRIÈRE : la version $bad a planté $count fois au démarrage en ${CRASH_WINDOW_S}s ;" \
    "current rebasculé sur $prev. $bad est ajoutée à $ROLLED_BACK (plus retentée automatiquement)."
  return 0
}

VERSION_NAME="$(current_version)" || {
  log "ERREUR : lien $ROOT/current absent ou illisible — installation gérée incomplète" \
    "(relancer scripts/install-node.sh)."
  exit 78
}
VERSION_DIR="$ROOT/versions/$VERSION_NAME"
PYTHON="$VERSION_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ] || ! cd "$VERSION_DIR"; then
  log "ERREUR : $PYTHON introuvable : la version $VERSION_NAME est inutilisable."
  now="$(date +%s)"
  record_crash "$VERSION_NAME" "$now"
  count="$(recent_crashes "$VERSION_NAME" "$now")"
  if [ "$count" -ge "$MAX_CRASHES" ]; then rollback "$VERSION_NAME" "$count"; fi
  exit 1
fi

log "démarrage du bridge $VERSION_NAME ($PYTHON -m bridge --config $CONFIG)"
started="$(date +%s)"
"$PYTHON" -m bridge --config "$CONFIG" &
child=$!
stopping=0
trap 'stopping=1; kill -TERM "$child" 2>/dev/null' TERM INT HUP
wait "$child"
rc=$?
if [ "$stopping" = 1 ] && [ "$rc" -gt 128 ]; then
  # `wait` interrompu par le signal : attendre la vraie fin du bridge (arrêt propre).
  wait "$child"
  rc=$?
fi
trap - TERM INT HUP
elapsed=$(($(date +%s) - started))

if [ "$stopping" = 1 ]; then
  log "arrêt demandé : bridge $VERSION_NAME terminé (code $rc) après ${elapsed}s."
  exit 0
fi

case "$rc" in
  0)
    log "bridge $VERSION_NAME arrêté normalement après ${elapsed}s."
    exit 0
    ;;
  "$EXIT_UPDATE_APPLIED")
    relaunches="${RUN_BRIDGE_IMMEDIATE_RELAUNCHES:-0}"
    if [ "$elapsed" -ge "$STARTUP_WINDOW_S" ]; then relaunches=0; fi
    if [ "$relaunches" -ge "$MAX_IMMEDIATE_RELAUNCHES" ]; then
      log "ERREUR : $relaunches relances immédiates de suite après mise à jour : on laisse" \
        "launchd/systemd relancer avec leur délai."
      exit 0
    fi
    log "mise à jour appliquée par le bridge $VERSION_NAME : relance immédiate sur" \
      "$(current_version || echo '?')."
    export RUN_BRIDGE_IMMEDIATE_RELAUNCHES=$((relaunches + 1))
    exec "${BASH:-/bin/bash}" "$0" "$ROOT"
    ;;
esac

if [ "$elapsed" -lt "$STARTUP_WINDOW_S" ] && [ "$rc" != "$EXIT_ENVIRONMENT" ]; then
  now="$(date +%s)"
  record_crash "$VERSION_NAME" "$now"
  count="$(recent_crashes "$VERSION_NAME" "$now")"
  log "ERREUR : le bridge $VERSION_NAME est sorti en code $rc après ${elapsed}s" \
    "(plantage au démarrage n°$count en ${CRASH_WINDOW_S}s, retour arrière à $MAX_CRASHES)."
  if [ "$count" -ge "$MAX_CRASHES" ]; then rollback "$VERSION_NAME" "$count"; fi
elif [ "$rc" = "$EXIT_ENVIRONMENT" ]; then
  log "ERREUR : le bridge $VERSION_NAME est sorti en code 2 (configuration $CONFIG invalide ou" \
    "birdnet.db inaccessible) : pas compté comme plantage de version, voir les lignes précédentes."
else
  log "ERREUR : le bridge $VERSION_NAME est sorti en code $rc après ${elapsed}s."
fi
exit "$rc"
