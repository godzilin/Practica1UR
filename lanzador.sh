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
    printf 'Ejecutando %s...\n\n' "$1"
    "$PYTHON" "$BASE/visualizador/$1"
    printf '\nEl programa ha terminado. Pulsa Enter para volver al menu.'
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
        0) printf 'Hasta luego.\n'; exit 0 ;;
        *) printf '\nOpcion no valida. Pulsa Enter para continuar.'; read -r ;;
    esac
done