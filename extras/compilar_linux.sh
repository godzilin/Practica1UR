#!/bin/sh
# Compila entrega/visualizador_ur3e: un único ejecutable de Linux x86-64 con Python, PyBullet
# y el visualizador dentro. Abre el panel web, y el panel lanza los .py que tiene al lado.
# Se compila sobre Debian 11 (glibc 2.31) para que funcione en Ubuntu 20.04 o posterior.
# Debian 11 ya no tiene soporte: apt se apunta a archive.debian.org. gcc hace falta para
# recordclass (dependencia de pybullet_planning) y binutils para PyInstaller.
# libstdc++ y libgcc_s se dejan fuera: las de Debian 11 son viejas para el driver gráfico
# (Mesa) de un Linux moderno y PyBullet no podría abrir la ventana. Usa las del sistema.
# Necesita podman e Internet. Tarda unos minutos.
set -e
cd "$(dirname "$0")/.."
podman run --rm -v "$PWD":/src:Z -w /tmp docker.io/library/python:3.10-slim-bullseye sh -c "
    echo 'deb http://archive.debian.org/debian bullseye main' > /etc/apt/sources.list &&
    echo 'deb http://archive.debian.org/debian-security bullseye-security main' >> /etc/apt/sources.list &&
    rm -f /etc/apt/sources.list.d/* &&
    apt-get -qq update && apt-get -qq install -y --no-install-recommends gcc libc6-dev binutils > /dev/null &&
    pip install -q pyinstaller /src/material/ur3e_rg2-0.1.0-py3-none-any.whl &&
    pyi-makespec --onefile --name visualizador_ur3e --collect-data UR3e_rg2 \
        --hidden-import UR3e_rg2.dynamic_ur3e --hidden-import queue \
        --hidden-import unicodedata --hidden-import math /src/entrega/panel_web.py &&
    sed -i \"/^pyz = PYZ/i a.binaries = [b for b in a.binaries if not b[0].startswith(('libstdc++', 'libgcc_s'))]\" visualizador_ur3e.spec &&
    pyinstaller visualizador_ur3e.spec &&
    cp dist/visualizador_ur3e /src/entrega/"
