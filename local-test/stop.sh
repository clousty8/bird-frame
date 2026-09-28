#!/bin/bash
# Arrête BirdNET-Go.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$HERE/birdnet-go.pid"

stopped=0

# La surveillance du micro d'abord, pour qu'elle ne relance pas BirdNET-Go pendant l'arrêt.
if [ -f "$HERE/mic-watchdog.pid" ]; then
  kill "$(cat "$HERE/mic-watchdog.pid")" 2>/dev/null || true
  rm -f "$HERE/mic-watchdog.pid"
fi
pkill -f "$HERE/mic-watchdog.sh" 2>/dev/null || true

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    for _ in $(seq 1 10); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$PID" 2>/dev/null || true
    echo "BirdNET-Go arrêté (PID $PID)"
    stopped=1
  fi
  rm -f "$PIDFILE"
fi

if [ -f "$HERE/clip-retention.pid" ]; then
  kill "$(cat "$HERE/clip-retention.pid")" 2>/dev/null || true
  rm -f "$HERE/clip-retention.pid"
fi
pkill -f "$HERE/clip-retention.py" 2>/dev/null || true

# Filet de sécurité : tout processus birdnet-go lancé depuis ce dossier.
if pgrep -f "$HERE/bin/birdnet-go serve" >/dev/null 2>&1; then
  pkill -f "$HERE/bin/birdnet-go serve" 2>/dev/null || true
  echo "Processus birdnet-go résiduels arrêtés."
  stopped=1
fi

[ "$stopped" -eq 0 ] && echo "BirdNET-Go ne tournait pas."
exit 0
