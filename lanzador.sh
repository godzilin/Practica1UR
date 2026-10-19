#!/usr/bin/env bash

set -Eeuo pipefail

BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${UR_PYTHON:-$BASE/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
    printf 'No se encuentra el entorno instalado. Ejecuta primero instalador.sh.\n' >&2
    exit 1
fi

exec "$PYTHON" "$BASE/web_dashboard.py"