#!/bin/bash
# Vérifie chaque minute que BirdNET-Go capte bien le micro de config.yaml, et le relance sinon.
#
# Pourquoi : si ce micro disparaît un instant (débranché, coupure USB), macOS bascule la capture
# de BirdNET-Go sur l'entrée par défaut (le micro du Mac) sans que BirdNET-Go le remarque, et ne
# revient jamais en arrière. Vu le 26/09/2026 : 7 h de détections faites avec le micro du Mac.
#
# Lancé par start.sh, arrêté par stop.sh. Journal : data/mic-watchdog.log
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$HERE/birdnet-go.pid"
TOOL="$HERE/tools/mic-status"
INTERVAL=${MIC_WATCHDOG_INTERVAL:-60}   # secondes entre deux contrôles
STRIKES_BEFORE_RESTART=2   # deux contrôles ratés d'affilée : évite de réagir à un démarrage en cours

log() { echo "$(date '+%F %T') $*"; }

if [ ! -x "$TOOL" ] || [ "$TOOL.swift" -nt "$TOOL" ]; then
  swiftc -O -o "$TOOL" "$TOOL.swift" 2>/dev/null || { log "ERREUR : compilation de $TOOL.swift impossible"; exit 1; }
fi

strikes=0
absent_logged=0
while true; do
  sleep "$INTERVAL"
  PID=$(cat "$PIDFILE" 2>/dev/null) || continue
  kill -0 "$PID" 2>/dev/null || continue

  WANTED=$(sed -n 's/^ *device: "\(.*\)"$/\1/p' "$HERE/config.yaml" | head -1)
  USED_LIST=$("$TOOL" "$PID")
  USED=$(paste -sd ',' - <<< "$USED_LIST")

  if grep -qxF "$WANTED" <<< "$USED_LIST"; then
    strikes=0
    absent_logged=0
    continue
  fi

  if ! grep -qxF "$WANTED" <<< "$("$TOOL")"; then
    # Le micro n'est pas branché : rien à faire tant qu'il n'est pas revenu.
    [ "$absent_logged" = 0 ] && log "« $WANTED » débranché : BirdNET-Go capte « ${USED:-rien} » en attendant"
    absent_logged=1
    strikes=0
    continue
  fi

  strikes=$((strikes + 1))
  [ "$strikes" -lt "$STRIKES_BEFORE_RESTART" ] && continue

  log "BirdNET-Go capte « ${USED:-rien} » au lieu de « $WANTED » : redémarrage"
  kill "$PID" 2>/dev/null
  for _ in $(seq 1 15); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  kill -9 "$PID" 2>/dev/null
  rm -f "$PIDFILE"
  "$HERE/start.sh" | sed "s/^/$(date '+%F %T')   /"
  strikes=0
  absent_logged=0
done
