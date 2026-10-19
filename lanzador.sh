#!/usr/bin/env bash

set -Eeuo pipefail

BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$BASE/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    printf 'No se encuentra el entorno instalado. Ejecuta primero instalador.sh.\n' >&2
    exit 1
fi

ejecutar() {
    clear 2>/dev/null || true
    local script="$BASE/visualizador/$1"
    local comando
    printf -v comando 'printf "Ejecutando %%s...\\n\\n" %q; %q %q; estado=$?; printf "\\nEl programa ha terminado (codigo %%s). Pulsa Enter para cerrar." "$estado"; read -r' "$1" "$PYTHON" "$script"

    if command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e bash -c "$comando" >/dev/null 2>&1 &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -c "$comando" >/dev/null 2>&1 &
    elif command -v konsole >/dev/null 2>&1; then
        konsole -e bash -c "$comando" >/dev/null 2>&1 &
    elif command -v xfce4-terminal >/dev/null 2>&1; then
        xfce4-terminal --command="bash -c '$comando'" >/dev/null 2>&1 &
    elif command -v kitty >/dev/null 2>&1; then
        kitty bash -c "$comando" >/dev/null 2>&1 &
    elif command -v xterm >/dev/null 2>&1; then
        xterm -e bash -c "$comando" >/dev/null 2>&1 &
    else
        printf 'No se encontro un emulador de terminal grafico; se usara esta terminal.\n\n'
        bash -c "$comando"
    fi

    printf 'Se ha abierto una terminal nueva para %s.\n' "$1"
    printf 'Pulsa Enter para volver al menu.'
    read -r
}

while true; do
    clear 2>/dev/null || true
    printf '%s\n' \
        '========================================' \
        '       Visualizador UR3e' \
        '========================================' \
        '  1) Primaria (puerto 30001)' \
        '  2) Varios robots' \
        '  3) Tiempo real (puerto 30003)' \
        '  4) Ensenar y reproducir' \
        '  5) Probar conexion' \
        '  6) Prueba de robustez' \
        '  7) Configurar robots' \
        '  0) Salir' \
        '========================================'
    printf 'Elige una opcion: '
    read -r opcion

    case "$opcion" in
        1) ejecutar primaria.py ;;
        2) ejecutar varios_robots.py ;;
        3) ejecutar tiempo_real.py ;;
        4) ejecutar ensenar_reproducir.py ;;
        5) ejecutar test_conexion.py ;;
        6) ejecutar prueba_robustez.py ;;
        7) ejecutar configurar_robots.py ;;
        0) printf 'Hasta luego.\n'; exit 0 ;;
        *) printf '\nOpcion no valida. Pulsa Enter para continuar.'; read -r ;;
    esac
done