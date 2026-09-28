#!/bin/sh
# bird-frame — point d'entrée de l'image Docker.
#
# Lancé en root : prépare le dossier de données (volume Railway monté en root, cf.
# https://docs.railway.com/volumes#permissions) en le donnant à l'utilisateur `birdframe`, puis se
# ré-exécute sous cet utilisateur via setpriv (sans nouveaux privilèges). Lancé directement en
# non-root (`docker run --user …`) : exécute la commande telle quelle.
set -eu

APP_USER=birdframe
DATA_DIR="${BIRDFRAME_DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  if [ "$(stat -c %u "$DATA_DIR")" != "$(id -u "$APP_USER")" ]; then
    echo "entrypoint: $DATA_DIR appartient à l'uid $(stat -c %u "$DATA_DIR"), attribution à $APP_USER" >&2
    chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
  fi
  exec setpriv --reuid="$APP_USER" --regid="$APP_USER" --init-groups --no-new-privs "$0" "$@"
fi

exec "$@"
