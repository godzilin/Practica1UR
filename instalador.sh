#!/usr/bin/env bash

set -Eeuo pipefail

# Instalador para Linux/macOS. Puede ejecutarse desde cualquier directorio.
REPOSITORIO="https://github.com/godzilin/Practica1UR.git"
NOMBRE_PROYECTO="Practica1UR"
DESTINO="${PRACTICA1UR_DIR:-$HOME/$NOMBRE_PROYECTO}"

error() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

comando_requerido() {
    command -v "$1" >/dev/null 2>&1 || error "No se encuentra '$1'. Instálalo y vuelve a ejecutar este script."
}

instalar_uv() {
    if command -v uv >/dev/null 2>&1; then
        return
    fi

    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        error "No se encuentra Python ni curl/wget para instalarlo automáticamente."
    fi

    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || error "uv se instaló, pero no aparece en el PATH. Abre otra terminal y repite el instalador."
}

printf 'Instalando %s en %s\n' "$NOMBRE_PROYECTO" "$DESTINO"

comando_requerido git

if [ -e "$DESTINO" ] && [ ! -d "$DESTINO/.git" ]; then
    error "El destino '$DESTINO' ya existe y no es un clon de Practica1UR. Usa PRACTICA1UR_DIR para elegir otra carpeta."
fi

if [ -d "$DESTINO/.git" ]; then
    printf 'Repositorio ya existente; se conservan tus cambios locales.\n'
else
    git clone "$REPOSITORIO" "$DESTINO"
fi

cd "$DESTINO"

if [ ! -d .venv ]; then
    if command -v python3 >/dev/null 2>&1; then
        if ! python3 -m venv .venv 2>/dev/null; then
            instalar_uv
            uv venv --python 3.12 .venv
        fi
    else
        instalar_uv
        uv venv --python 3.12 .venv
    fi
fi

PYTHON="$(pwd)/.venv/bin/python"
[ -x "$PYTHON" ] || error "El entorno virtual no se creó correctamente."

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install \
    pybullet \
    numpy \
    matplotlib \
    python-docx \
    material/ur3e_rg2-0.1.0-py3-none-any.whl

"$PYTHON" - <<'PY'
import pybullet
import numpy
from docx import Document
print("Dependencias Python comprobadas correctamente.")
PY

printf '\nInstalación terminada.\n'
printf 'Para activar el entorno: source %s/.venv/bin/activate\n' "$DESTINO"
printf 'Para probar la conexión: %s visualizador/test_conexion.py\n' "$PYTHON"
printf 'Para abrir el visualizador: %s visualizador/ensenar_reproducir.py\n' "$PYTHON"