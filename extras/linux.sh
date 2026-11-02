#!/bin/sh
# Prepara el entorno la primera vez (o si está roto) y abre el panel web.
# Uso: ./extras/linux.sh   (necesita python3 con venv; la primera vez, Internet)
set -e
cd "$(dirname "$0")/.."
if ! .venv/bin/python -c "import UR3e_rg2" 2>/dev/null; then
    python3 -m venv .venv
    .venv/bin/pip install material/ur3e_rg2-0.1.0-py3-none-any.whl   # instala también pybullet y numpy
fi
exec .venv/bin/python entrega/panel_web.py
