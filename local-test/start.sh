#!/bin/bash
# Démarre BirdNET-Go (micro réglé dans config.yaml) et le nettoyage de l'audio hors top 10.
# Interface web : http://localhost:8080
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/bin/birdnet-go"
CFG="$HERE/config.yaml"
DATA="$HERE/data"
PIDFILE="$HERE/birdnet-go.pid"
LOG="$DATA/console.log"

# Ne garde l'audio que des 10 meilleures détections par espèce (passage toutes les 10 min).
start_retention() {
  if ! pgrep -f "$HERE/clip-retention.py" >/dev/null 2>&1; then
    nohup "$HERE/clip-retention.py" --loop 600 >>"$DATA/clip-retention.log" 2>&1 &
    echo $! > "$HERE/clip-retention.pid"
  fi
  echo "Nettoyage audio hors top 10 : actif (journal : data/clip-retention.log)"
}

# Relance BirdNET-Go si macOS l'a basculé sur un autre micro (après une déconnexion du micro).
start_watchdog() {
  if ! pgrep -f "$HERE/mic-watchdog.sh" >/dev/null 2>&1; then
    nohup "$HERE/mic-watchdog.sh" >>"$DATA/mic-watchdog.log" 2>&1 &
    echo $! > "$HERE/mic-watchdog.pid"
  fi
  echo "Surveillance du micro : active (journal : data/mic-watchdog.log)"
}

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "BirdNET-Go tourne déjà (PID $(cat "$PIDFILE")) — http://localhost:8080"
  start_retention
  start_watchdog
  exit 0
fi

if lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERREUR : le port 8080 est déjà occupé par un autre programme."
  lsof -nP -iTCP:8080 -sTCP:LISTEN
  exit 1
fi

mkdir -p "$DATA"
cd "$DATA"

# Les .dylib sont à côté du binaire : pas d'installation système.
DYLD_LIBRARY_PATH="$HERE/bin" nohup "$BIN" serve -c "$CFG" >"$LOG" 2>&1 &
echo $! > "$PIDFILE"

# Attendre que le serveur web réponde (30 s max).
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://localhost:8080/api/v2/detections?limit=1" 2>/dev/null; then
    echo "BirdNET-Go démarré (PID $(cat "$PIDFILE"))"
    # Micro réellement ouvert par le processus (demandé à macOS, pas au journal de BirdNET-Go)
    DEV=""
    for _ in $(seq 1 10); do
      DEV=$("$HERE/tools/mic-status" "$(cat "$PIDFILE")" 2>/dev/null | paste -sd ',' -)
      [ -n "$DEV" ] && break
      sleep 1
    done
    echo "Micro utilisé : ${DEV:-inconnu (voir $DATA/logs/audio.log)}"
    echo "Interface web : http://localhost:8080"
    start_retention
    start_watchdog
    exit 0
  fi
  sleep 1
done

echo "ERREUR : le serveur n'a pas répondu en 30 s. Dernières lignes du log :"
tail -20 "$LOG"
exit 1
