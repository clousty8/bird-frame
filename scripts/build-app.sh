#!/usr/bin/env bash
# bird-frame — construit l'interface web puis lance une pile LOCALE et ISOLÉE (serveur +
# nœud de test + bridge en lecture seule) pour tester visuellement une feature, sans jamais
# toucher à Railway (production) ni à local-test/ (installation BirdNET-Go de développement).
#
# Isolation : toutes les données de cette pile vivent sous .dev/build-app/<slug>/ du dépôt
# (base SQLite, clips/photos reçus, config du nœud, logs, pids) — <slug> = nom du worktree
# courant (ou "main" sur le worktree principal). Deux worktrees différents ont chacun leur
# propre arborescence .dev/, donc leurs propres ports/process/bases : zéro collision de
# données entre features. Seul le port TCP est une ressource partagée par la machine — d'où
# --port et l'erreur explicite si le port par défaut est déjà pris (par ex. par
# ./scripts/dev-up.sh, qui écoute aussi sur :8090 par défaut).
#
# Garde-fou Railway : ce script ne connaît qu'une seule URL de serveur, http://localhost:<port>,
# jamais paramétrable autrement — le nœud de test et le bridge ne peuvent donc structurellement
# pas parler à Railway. Les variables d'environnement qui pourraient faire fuiter l'URL de prod
# dans register_node.py (BRIDGE_SERVER_URL) sont explicitement neutralisées ci-dessous, et un
# garde-fou compare quand même l'URL locale à celle de deploy/production.env par sécurité.
#
# Usage :
#   ./scripts/build-app.sh              # build + lance sur :8090 (ou le port choisi)
#   ./scripts/build-app.sh --port 8091  # si :8090 est déjà pris par une autre pile
#   ./scripts/build-app.sh --stop       # arrête ce que ce script a démarré pour ce worktree
#   ./scripts/build-app.sh --help

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Slug du worktree courant : bird-frame place ses worktrees sous .claude/worktrees/<slug>/
# (cf. les autres agents qui travaillent en parallèle sur ce dépôt). Sur le worktree
# principal (pas de .claude/worktrees/ dans le chemin), on retombe sur "main".
case "$REPO_ROOT" in
  */.claude/worktrees/*) SLUG="$(basename "$REPO_ROOT")" ;;
  *) SLUG="main" ;;
esac

PORT=8090
STOP=0

print_help() {
  cat <<'EOF'
Usage: scripts/build-app.sh [--port N] [--stop] [--help]

Construit web/ (npm run build) puis lance EN LOCAL, isolé de Railway et de local-test/ :
  - le serveur FastAPI (BIRDFRAME_ENV=dev, BIRDFRAME_WEB_DIST=web/dist : sert aussi l'UI) ;
  - un nœud de test enregistré en lecture seule (scripts/register_node.py --node-readonly) ;
  - un bridge qui lit local-test/data/birdnet.db en lecture seule vers ce serveur local.

Toutes les données (base, clips, config du nœud, logs, pids) vivent sous
.dev/build-app/<slug>/ (slug = nom du worktree courant, "main" sur le worktree principal) —
rien n'est partagé avec un autre worktree ni avec la démo dev-up.sh.

Options :
  --port N   Port d'écoute du serveur (défaut : 8090). À changer si occupé.
  --stop     Arrête le serveur et le bridge démarrés par ce script pour ce worktree.
  --help     Affiche cette aide.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:?--port requiert une valeur}"
      shift 2
      ;;
    --stop)
      STOP=1
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Argument inconnu : $1 (voir --help)" >&2
      exit 1
      ;;
  esac
done

DATA_ROOT="$REPO_ROOT/.dev/build-app/$SLUG"
LOG_DIR="$DATA_ROOT/logs"
PID_DIR="$DATA_ROOT/pids"
SERVER_DATA_DIR="$DATA_ROOT/data"
NODE_CONFIG_DIR="$DATA_ROOT/node-config"
BRIDGE_STATE_DIR="$DATA_ROOT/bridge-state"
ADMIN_TOKEN_FILE="$DATA_ROOT/admin-token"
NODE_SLUG="buildapp"
NODE_CONFIG="$NODE_CONFIG_DIR/${NODE_SLUG}.env"
SERVER_URL="http://localhost:$PORT"

# --- Garde-fou : jamais Railway ---------------------------------------------------------------
# SERVER_URL ci-dessus est toujours du localhost, en dur : il n'existe aucune option pour le
# faire pointer ailleurs. On neutralise en plus les variables d'environnement ambiantes que
# register_node.py accepterait comme valeur par défaut (BRIDGE_SERVER_URL), et on vérifie,
# si deploy/production.env est déjà rempli, que l'URL locale ne coïncide pas avec elle.
unset BRIDGE_SERVER_URL BIRDFRAME_PUBLIC_URL 2>/dev/null || true
if [[ -f "$REPO_ROOT/deploy/production.env" ]]; then
  RAILWAY_URL="$(grep '^BIRDFRAME_PUBLIC_URL=' "$REPO_ROOT/deploy/production.env" 2>/dev/null | head -1 | cut -d= -f2-)"
  if [[ -n "$RAILWAY_URL" && "$SERVER_URL" == "$RAILWAY_URL"* ]]; then
    echo "✗ Garde-fou : SERVER_URL ($SERVER_URL) pointe vers le domaine Railway de production" >&2
    echo "  ($RAILWAY_URL). build-app.sh est réservé au test en local — abandon." >&2
    exit 1
  fi
fi

is_running() {
  # $1 = fichier pid ; vrai si le fichier existe et le process est vivant.
  [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null
}

port_in_use() {
  # $1 = port ; vrai si quelque chose écoute déjà dessus (nous ou un autre process).
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
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

# --- Mode arrêt ----------------------------------------------------------------------------
if [[ "$STOP" == "1" ]]; then
  echo "Arrêt de build-app pour le worktree « $SLUG »…"
  stop_one "bridge"  "$PID_DIR/bridge.pid"
  stop_one "serveur" "$PID_DIR/server.pid"
  echo
  echo "Terminé. local-test/ et web/dist n'ont pas été touchés."
  echo "Les données (.dev/build-app/$SLUG/) sont conservées — les supprimer à la main pour repartir de zéro."
  exit 0
fi

mkdir -p "$LOG_DIR" "$PID_DIR" "$SERVER_DATA_DIR" "$NODE_CONFIG_DIR" "$BRIDGE_STATE_DIR"

# --- 1. Build de l'interface (web/dist) -----------------------------------------------------
if [[ ! -x "$REPO_ROOT/web/node_modules/.bin/vite" ]]; then
  echo "• dépendances frontend absentes : npm install…"
  (cd "$REPO_ROOT/web" && npm install)
fi
echo "• build de l'interface (npm run build)…"
(cd "$REPO_ROOT/web" && npm run build)

# --- 2. Serveur FastAPI (isolé, :$PORT) -----------------------------------------------------
if is_running "$PID_DIR/server.pid"; then
  echo "• serveur déjà en cours (pid $(cat "$PID_DIR/server.pid")) sur $SERVER_URL"
else
  if port_in_use "$PORT"; then
    echo "✗ Le port $PORT est déjà utilisé par un autre process (peut-être un autre" >&2
    echo "  ./scripts/build-app.sh ou ./scripts/dev-up.sh). Relance avec --port <autre-port>." >&2
    exit 1
  fi

  if [[ ! -f "$ADMIN_TOKEN_FILE" ]]; then
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$ADMIN_TOKEN_FILE"
    chmod 600 "$ADMIN_TOKEN_FILE"
  fi
  ADMIN_TOKEN="$(cat "$ADMIN_TOKEN_FILE")"

  if [[ ! -x "$REPO_ROOT/server/.venv/bin/uvicorn" ]]; then
    echo "• dépendances serveur absentes : uv sync…"
    (cd "$REPO_ROOT/server" && uv sync)
  fi

  echo "• démarrage du serveur isolé (uvicorn :$PORT, données sous .dev/build-app/$SLUG/data)…"
  (
    cd "$REPO_ROOT/server"
    PYTHONUNBUFFERED=1 \
    BIRDFRAME_ENV=dev \
    BIRDFRAME_WEB_DIST="$REPO_ROOT/web/dist" \
    BIRDFRAME_DB_PATH="$SERVER_DATA_DIR/bird-frame.db" \
    BIRDFRAME_DATA_DIR="$SERVER_DATA_DIR" \
    BIRDFRAME_ADMIN_TOKEN="$ADMIN_TOKEN" \
    BIRDFRAME_HOST=127.0.0.1 \
    BIRDFRAME_PORT="$PORT" \
    BIRDFRAME_CORS_ORIGINS="$SERVER_URL" \
    BIRDFRAME_SPECIES_DATA_DIR="$REPO_ROOT/species-data" \
    BIRDFRAME_AUTO_MIGRATE=1 \
      nohup "$REPO_ROOT/server/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT" \
      > "$LOG_DIR/server.log" 2>&1 &
    echo $! > "$PID_DIR/server.pid"
  )
  wait_for_http "$SERVER_URL/health" "serveur" 30
fi

ADMIN_TOKEN="$(cat "$ADMIN_TOKEN_FILE")"

# --- 3. Nœud de test en lecture seule (une seule fois) --------------------------------------
BIRDNET_DB="$REPO_ROOT/local-test/data/birdnet.db"
if [[ ! -f "$BIRDNET_DB" ]]; then
  echo "• local-test/data/birdnet.db introuvable : pas de nœud de test ni de bridge (l'UI reste"
  echo "  testable, mais sans détections). Lancer local-test/start.sh au moins une fois pour en avoir une."
elif [[ -f "$NODE_CONFIG" ]]; then
  echo "• nœud de test déjà enregistré ($NODE_CONFIG)"
else
  echo "• enregistrement du nœud de test « $NODE_SLUG » (lecture seule, jamais vers Railway)…"
  MIC_STATUS_ARGS=()
  if [[ -x "$REPO_ROOT/local-test/tools/mic-status" ]]; then
    MIC_STATUS_ARGS=(--mic-status-tool "$REPO_ROOT/local-test/tools/mic-status")
  fi
  python3 "$REPO_ROOT/scripts/register_node.py" \
    --slug "$NODE_SLUG" --site-name "Build App" --node-name "Build app — $SLUG" \
    --timezone "Europe/Paris" \
    --server-url "$SERVER_URL" --admin-token "$ADMIN_TOKEN" \
    --node-readonly \
    --db-path "$BIRDNET_DB" \
    --clips-dir "$REPO_ROOT/local-test/data/clips" \
    --node-api "http://localhost:8080" \
    --birdnet-pid-file "$REPO_ROOT/local-test/birdnet-go.pid" \
    --state-file "$BRIDGE_STATE_DIR/${NODE_SLUG}.json" \
    --config-out "$NODE_CONFIG" \
    "${MIC_STATUS_ARGS[@]}"
fi

# --- 4. Bridge (lecture seule, un seul passage suffirait, mais on le laisse tourner comme
#        dev-up.sh pour que l'UI se mette à jour si de nouvelles détections arrivent) --------
if [[ -f "$NODE_CONFIG" ]]; then
  if is_running "$PID_DIR/bridge.pid"; then
    echo "• bridge déjà en cours (pid $(cat "$PID_DIR/bridge.pid"))"
  else
    if [[ ! -x "$REPO_ROOT/node/.venv/bin/python" ]]; then
      echo "• dépendances bridge absentes : uv sync…"
      (cd "$REPO_ROOT/node" && uv sync)
    fi
    echo "• démarrage du bridge (lecture seule, nœud « $NODE_SLUG »)…"
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
fi

# --- 5. Ouvrir le navigateur -----------------------------------------------------------------
open "$SERVER_URL" 2>/dev/null || true

cat <<EOF

build-app tourne en local, isolé (worktree « $SLUG », rien vers Railway, local-test/ intact) :
  interface + API   $SERVER_URL   (logs: $LOG_DIR/server.log, pid: $(cat "$PID_DIR/server.pid" 2>/dev/null))
  bridge            lecture seule (logs: $LOG_DIR/bridge.log, pid: $(cat "$PID_DIR/bridge.pid" 2>/dev/null || echo "non démarré"))
  données           $DATA_ROOT

Tout arrêter : ./scripts/build-app.sh --stop
EOF
