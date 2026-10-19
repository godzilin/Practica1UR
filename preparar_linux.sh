#!/usr/bin/env bash

set -Eeuo pipefail

BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf 'No se encuentra %s. Instala Python 3.11 o posterior y vuelve a intentarlo.\n' "$PYTHON" >&2
    exit 1
fi

if [ ! -x "$BASE/.venv/bin/python" ]; then
    "$PYTHON" -m venv "$BASE/.venv"
fi

PYTHON_VENV="$BASE/.venv/bin/python"
"$PYTHON_VENV" -m pip install --upgrade pip
"$PYTHON_VENV" -m pip install pybullet pybullet-planning numpy matplotlib python-docx
"$PYTHON_VENV" -m pip install --no-deps "$BASE/material/ur3e_rg2-0.1.0-py3-none-any.whl"
"$PYTHON_VENV" "$BASE/comprobar_dependencias.py"
printf '\nEntorno Linux preparado. Ejecuta ./lanzador.sh para abrir el panel web.\n'