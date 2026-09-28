#!/usr/bin/env bash
# bird-frame — arrête ce que ./scripts/dev-up.sh a démarré (serveur, bridge, vite), via les pids
# écrits sous .dev/pids/. Idempotent (rien à faire si déjà arrêté). Ne touche jamais
# local-test/ (aucun pid, aucun fichier de local-test/ n'est lu ni écrit ici) : arrêter
# BirdNET-Go reste exclusivement le rôle de local-test/stop.sh.
#
# Usage : ./scripts/dev-down.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$REPO_ROOT/.dev/pids"

stop_one() {
  # $1 = nom (pour les messages), $2 = fichier pid
  local name="$1" pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "• $name : pas de fichier pid, rien à arrêter."
    return 0
  fi
  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "• $name : pid $pid déjà mort."
    rm -f "$pid_file"
    return 0
  fi
  echo "• $name : arrêt (pid $pid, SIGTERM)…"
  kill -TERM "$pid" 2>/dev/null || true
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
    if (( waited >= 10 )); then
      echo "  toujours vivant après 10s, SIGKILL."
      kill -KILL "$pid" 2>/dev/null || true
      break
    fi
  done
  rm -f "$pid_file"
  echo "  ✓ $name arrêté."
}

# Ordre d'arrêt : frontend puis bridge puis serveur (sans dépendance réelle, mais évite des
# erreurs de connexion visibles côté navigateur/bridge pendant l'arrêt).
stop_one "vite"    "$PID_DIR/vite.pid"
stop_one "bridge"  "$PID_DIR/bridge.pid"
stop_one "serveur" "$PID_DIR/server.pid"

echo
echo "Tout est arrêté (local-test/ n'a pas été touché — utiliser local-test/stop.sh séparément si besoin)."
