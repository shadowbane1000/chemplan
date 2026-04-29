#!/bin/sh
# Backend entrypoint: ensure AiZynthFinder data is present before serving.
# /app/data is a bind-mount from the host; on a fresh deploy it's empty.
# We run download_public_data once, then exec the actual server command.

set -e

DATA_DIR="${CHEMPLAN_DATA_DIR:-/app/data}"
CONFIG="${DATA_DIR}/config.yml"

if [ ! -f "${CONFIG}" ]; then
  echo "[entrypoint] No config.yml in ${DATA_DIR} — downloading USPTO public data (~750MB)…"
  download_public_data "${DATA_DIR}"
  echo "[entrypoint] Download complete."
else
  echo "[entrypoint] Found existing model data at ${DATA_DIR}/."
fi

# Path in config.yml is absolute and was written by download_public_data
# pointing at /app/data — perfect, no rewrite needed.

exec "$@"
