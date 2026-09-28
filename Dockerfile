# syntax=docker/dockerfile:1.7
# bird-frame — image unique du serveur (API FastAPI + interface web + bundle du bridge), pour Railway.
#
#   docker build -t bird-frame .
#   docker run -p 8090:8090 -v bird-frame-data:/data -e BIRDFRAME_ADMIN_TOKEN=… bird-frame
#
# Étapes : (1) build de l'interface Svelte ; (2) bundle du bridge pour la mise à jour des nœuds ;
# (3) dépendances Python du serveur (uv, lock figé) ; (4) image finale python:3.13-slim + sox,
# utilisateur non-root. Données persistantes (SQLite, clips, photos) : volume monté sur /data.

ARG PYTHON_IMAGE=python:3.13-slim
ARG NODE_IMAGE=node:24-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11

# --- 1. Interface web ------------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. Bundle du bridge (node-bundle-<version>.tar.gz + .sha256) -------------------------------
FROM ${PYTHON_IMAGE} AS bundle
WORKDIR /src
COPY VERSION ./
COPY scripts/build_node_bundle.py scripts/
COPY node/pyproject.toml node/uv.lock node/
COPY node/bridge node/bridge
RUN python scripts/build_node_bundle.py --out /out

# --- 3. Dépendances du serveur ---------------------------------------------------------------------
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS server-deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/server/.venv
WORKDIR /app/server
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- 4. Image finale -----------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# sox : spectrogrammes des clips reçus des nœuds (BIRDFRAME_SOX_PATH=sox). setpriv (util-linux, déjà
# présent dans l'image de base) sert à docker/entrypoint.sh pour abandonner les droits root.
RUN apt-get update \
    && apt-get install -y --no-install-recommends sox \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 birdframe \
    && useradd --system --uid 10001 --gid birdframe --home-dir /app --no-create-home \
       --shell /usr/sbin/nologin birdframe \
    && mkdir -p /data \
    && chown birdframe:birdframe /data

WORKDIR /app/server
COPY --from=server-deps /app/server/.venv /app/server/.venv
COPY server/alembic.ini ./
COPY server/migrations ./migrations
COPY server/app ./app
COPY species-data/species_universe_fr.json species-data/aliases.json /app/species-data/
COPY species-data/base /app/species-data/base
COPY species-data/sheets /app/species-data/sheets
COPY --from=web /src/web/dist /app/web/dist
COPY --from=bundle /out/ /app/node-bundle/
COPY VERSION /app/VERSION
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN python -m compileall -q /app/server/app /app/server/migrations

ENV PATH="/app/server/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIRDFRAME_ENV=production \
    BIRDFRAME_HOST=0.0.0.0 \
    BIRDFRAME_DATA_DIR=/data \
    BIRDFRAME_DB_PATH=/data/bird-frame.db \
    BIRDFRAME_SPECIES_DATA_DIR=/app/species-data \
    BIRDFRAME_WEB_DIST=/app/web/dist \
    BIRDFRAME_NODE_BUNDLE=/app/node-bundle \
    BIRDFRAME_AUTO_MIGRATE=1

# Pas d'instruction VOLUME : le volume persistant est attaché par la plateforme (Railway : volume
# monté sur /data) ou par `docker run -v …:/data` ; sans volume, les données sont éphémères.
EXPOSE 8090

# L'entrypoint démarre en root uniquement pour rendre /data (volume Railway, monté en root) à
# l'utilisateur `birdframe`, puis se ré-exécute sous cet utilisateur (setpriv) : uvicorn ne tourne
# jamais en root. Migrations Alembic appliquées par l'application au démarrage
# (BIRDFRAME_AUTO_MIGRATE=1). PORT est fourni par Railway.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8090}\" --proxy-headers --forwarded-allow-ips='*'"]
