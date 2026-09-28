#!/bin/bash
# Compile l'interface modifiée (fork ../birdnet-go-ui, branche bird-frame) et la fait servir
# par BirdNET-Go à la place de celle embarquée dans le binaire.
#
# BirdNET-Go sert frontend/dist depuis son dossier de travail (data/) quand ce dossier existe
# (« Frontend dev mode » dans data/logs/api.log). Détecté au démarrage uniquement : après le
# tout premier déploiement, relancer avec ./stop.sh && ./start.sh ; ensuite c'est immédiat.
#
# Revenir à l'interface officielle : supprimer data/frontend puis ./stop.sh && ./start.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI="$(cd "$HERE/../birdnet-go-ui" && pwd)"
DEST="$HERE/data/frontend/dist"

# Le code de l'interface doit correspondre à la version du binaire (même API).
BIN_VERSION=$(grep -o 'BirdNET-Go starting version=[0-9]*' "$HERE/data/console.log" 2>/dev/null \
  | tail -1 | cut -d= -f2)
UI_BASE=$(git -C "$UI" describe --tags --abbrev=0 2>/dev/null || echo "?")
if [ -n "$BIN_VERSION" ] && [ "$BIN_VERSION" != "$UI_BASE" ]; then
  echo "ATTENTION : binaire en version $BIN_VERSION, interface basée sur $UI_BASE."
  echo "Rebaser la branche bird-frame sur le tag $BIN_VERSION avant de déployer."
  exit 1
fi

(cd "$UI/frontend" && npm run build >/dev/null)
mkdir -p "$DEST"
rsync -a --delete "$UI/frontend/dist/" "$DEST/"
echo "Interface déployée dans data/frontend/dist (base $UI_BASE)."

MODE=$(grep -h 'Frontend dev mode enabled\|Frontend production mode' "$HERE/data/logs/api.log" 2>/dev/null | tail -1)
if [[ "$MODE" != *"dev mode enabled"* ]]; then
  echo "BirdNET-Go sert encore l'interface d'origine : ./stop.sh && ./start.sh pour prendre la nouvelle."
fi
