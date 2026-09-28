#!/usr/bin/env bash
# bird-frame — démarre serveur FastAPI (:8090) + bridge (nœud « pornic », lecture seule) +
# frontend Vite (:5173), tous en arrière-plan, pour la démo S1 sur ce Mac.
#
# Idempotent : relancer ce script ne redémarre pas un composant déjà en cours (pid vivant dans
# .dev/pids/). N'interfère JAMAIS avec local-test/ : ce script ne lance ni n'arrête jamais
# local-test/start.sh, n'écrit rien sous local-test/, et le bridge démarré ici tourne en mode
# BRIDGE_NODE_READONLY=1 (aucune mutation HTTP contre localhost:8080, contrat §7.1).
#
# Usage :
#   ./scripts/dev-up.sh              # nœud "pornic" par défaut
#   ./scripts/dev-up.sh --slug pornic

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="$REPO_ROOT/.dev"
LOG_DIR="$DEV_DIR/logs"
PID_DIR="$DEV_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR" "$DEV_DIR/screenshots"

SLUG="pornic"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug)
      SLUG="${2:?--slug requiert une valeur}"
      shift 2
      ;;
    *)
      echo "Argument inconnu : $1" >&2
      exit 1
      ;;
  esac
done

SERVER_URL="http://localhost:8090"
VITE_URL="http://localhost:5173"

# --- Garde-fou : jamais Railway --------------------------------------------------------------
# SERVER_URL ci-dessus est toujours du localhost, en dur : ce script n'a aucune option pour le
# faire pointer ailleurs (même garde-fou que scripts/build-app.sh). On neutralise en plus la
# variable d'environnement ambiante que register_node.py accepterait comme valeur par défaut
# (BRIDGE_SERVER_URL), et on vérifie, si deploy/production.env est déjà rempli, que l'URL locale
# ne coïncide pas avec elle.
unset BRIDGE_SERVER_URL BIRDFRAME_PUBLIC_URL 2>/dev/null || true
if [[ -f "$REPO_ROOT/deploy/production.env" ]]; then
  RAILWAY_URL="$(grep '^BIRDFRAME_PUBLIC_URL=' "$REPO_ROOT/deploy/production.env" 2>/dev/null | head -1 | cut -d= -f2-)"
  if [[ -n "$RAILWAY_URL" && "$SERVER_URL" == "$RAILWAY_URL"* ]]; then
    echo "✗ Garde-fou : SERVER_URL ($SERVER_URL) pointe vers le domaine Railway de production" >&2
    echo "  ($RAILWAY_URL). dev-up.sh est réservé au développement local — abandon." >&2
    exit 1
  fi
fi

is_running() {
  # $1 = fichier pid ; vrai si le fichier existe et le process est vivant.
  [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null
}

wait_for_http() {
  # $1 = URL, $2 = description, $3 = timeout en secondes (défaut 30).
  local url="$1" desc="$2" timeout="${3:-30}" waited=0
  until curl -fsS -o /dev/null "$url" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
    if (( waited >= timeout )); then
      echo "✗ $desc ($url) ne répond toujours pas après ${timeout}s — voir les logs sous $LOG_DIR/." >&2
      return 1
    fi
  done
  echo "✓ $desc prêt ($url)"
}

# --- 1. Serveur FastAPI (:8090) -------------------------------------------------------------
if is_running "$PID_DIR/server.pid"; then
  echo "• serveur déjà en cours (pid $(cat "$PID_DIR/server.pid"))"
else
  if [[ ! -f "$REPO_ROOT/server/.env" ]]; then
    echo "• server/.env absent : copie de .env.example avec un jeton admin généré aléatoirement."
    cp "$REPO_ROOT/server/.env.example" "$REPO_ROOT/server/.env"
    TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    # sed BSD (macOS) : -i '' pour une édition sur place sans fichier de sauvegarde.
    sed -i '' "s/^BIRDFRAME_ADMIN_TOKEN=.*/BIRDFRAME_ADMIN_TOKEN=${TOKEN}/" "$REPO_ROOT/server/.env"
  fi
  if [[ ! -x "$REPO_ROOT/server/.venv/bin/uvicorn" ]]; then
    echo "• dépendances serveur absentes : uv sync…"
    (cd "$REPO_ROOT/server" && uv sync)
  fi
  echo "• démarrage du serveur (uvicorn :8090)…"
  (
    cd "$REPO_ROOT/server"
    # PYTHONUNBUFFERED=1 : sans TTY, stdout de Python passe en bufferisation bloc — sans ça,
    # les logs n'apparaissent dans server.log qu'après coup (buffer plein ou arrêt du process),
    # ce qui rend le fichier inutilisable pour du diagnostic en direct pendant que ça tourne.
    PYTHONUNBUFFERED=1 nohup "$REPO_ROOT/server/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8090 \
      > "$LOG_DIR/server.log" 2>&1 &
    echo $! > "$PID_DIR/server.pid"
  )
  wait_for_http "$SERVER_URL/health" "serveur" 30
fi

ADMIN_TOKEN="$(grep '^BIRDFRAME_ADMIN_TOKEN=' "$REPO_ROOT/server/.env" | cut -d= -f2-)"

# --- 2. Enregistrement du nœud (une seule fois ; lecture seule, contrat §7.1) ----------------
NODE_CONFIG="$REPO_ROOT/node/config/${SLUG}.env"
if [[ -f "$NODE_CONFIG" ]]; then
  echo "• nœud « $SLUG » déjà enregistré ($NODE_CONFIG)"
else
  echo "• enregistrement du nœud « $SLUG » (--node-readonly : auto_main_name=false, jamais de set_main_name)…"
  MIC_STATUS_ARGS=()
  if [[ -x "$REPO_ROOT/local-test/tools/mic-status" ]]; then
    MIC_STATUS_ARGS=(--mic-status-tool "$REPO_ROOT/local-test/tools/mic-status")
  fi
  python3 "$REPO_ROOT/scripts/register_node.py" \
    --slug "$SLUG" --site-name "Pornic" --node-name "Mac Armand — Pornic" \
    --timezone "Europe/Paris" --lat 47.1155 --lon -2.1046 \
    --server-url "$SERVER_URL" --admin-token "$ADMIN_TOKEN" \
    --node-readonly "${MIC_STATUS_ARGS[@]}"
fi

# --- 3. Bridge (mode continu, BRIDGE_NODE_READONLY=1 dans le fichier ci-dessus) --------------
if is_running "$PID_DIR/bridge.pid"; then
  echo "• bridge déjà en cours (pid $(cat "$PID_DIR/bridge.pid"))"
else
  if [[ ! -x "$REPO_ROOT/node/.venv/bin/python" ]]; then
    echo "• dépendances bridge absentes : uv sync…"
    (cd "$REPO_ROOT/node" && uv sync)
  fi
  echo "• démarrage du bridge (boucle continue, nœud « $SLUG », lecture seule)…"
  (
    cd "$REPO_ROOT/node"
    PYTHONUNBUFFERED=1 nohup "$REPO_ROOT/node/.venv/bin/python" -m bridge --config "$NODE_CONFIG" \
      > "$LOG_DIR/bridge.log" 2>&1 &
    echo $! > "$PID_DIR/bridge.pid"
  )
  sleep 2
  if is_running "$PID_DIR/bridge.pid"; then
    echo "✓ bridge lancé (pid $(cat "$PID_DIR/bridge.pid"))"
  else
    echo "✗ le bridge s'est arrêté immédiatement — voir $LOG_DIR/bridge.log" >&2
  fi
fi

# --- 4. Frontend Vite (:5173) -----------------------------------------------------------------
if is_running "$PID_DIR/vite.pid"; then
  echo "• vite déjà en cours (pid $(cat "$PID_DIR/vite.pid"))"
else
  if [[ ! -x "$REPO_ROOT/web/node_modules/.bin/vite" ]]; then
    echo "• dépendances frontend absentes : npm install…"
    (cd "$REPO_ROOT/web" && npm install)
  fi
  echo "• démarrage de vite (:5173)…"
  (
    cd "$REPO_ROOT/web"
    nohup "$REPO_ROOT/web/node_modules/.bin/vite" --strictPort \
      > "$LOG_DIR/vite.log" 2>&1 &
    echo $! > "$PID_DIR/vite.pid"
  )
  wait_for_http "$VITE_URL/" "frontend vite" 30
fi

cat <<EOF

bird-frame tourne en arrière-plan :
  serveur    $SERVER_URL   (logs: $LOG_DIR/server.log, pid: $(cat "$PID_DIR/server.pid" 2>/dev/null))
  bridge     nœud « $SLUG », lecture seule   (logs: $LOG_DIR/bridge.log, pid: $(cat "$PID_DIR/bridge.pid" 2>/dev/null))
  frontend   $VITE_URL   (logs: $LOG_DIR/vite.log, pid: $(cat "$PID_DIR/vite.pid" 2>/dev/null))

Ouvrir $VITE_URL dans un navigateur.
Tout arrêter : ./scripts/dev-down.sh
EOF
