"""
Prueba de robustez (sin robot ni red): ataca las funciones que leen datos de fuera.

1. Mensajes del robot rotos: truncados, con bytes al azar, con ángulos NaN. El parser solo
   puede fallar con ConnectionError, ValueError o struct.error, que son las que los receptores capturan para
   reconectar; cualquier otra (IndexError...) mataría un hilo receptor.
2. robots.json mal escrito: debe terminar con un mensaje claro (SystemExit), no con un traceback.

Cómo usarlo: pulsa F5 (o ▶) en VS Code. Si todo va bien, termina con "TODO OK".
"""

import contextlib
import io
import json
import math
import random
import struct
import tempfile
from pathlib import Path

from primaria import cortar_mensajes, leer_estado, describir_error, mostrar_mensaje_robot, cargar_robots

ERRORES_PREVISTOS = (ConnectionError, ValueError, struct.error)
PRUEBAS = 20000


def mensaje_estado(q):
    """Mensaje tipo 16 mínimo y correcto: subpaquete de modo (47 B) + articulaciones (251 B)."""
    modo = struct.pack(">iBQ7?B", 5 + 8 + 7 + 1, 0, 0, *[False] * 4, False, True, False, 7)
    articulaciones = struct.pack(">iB", 251, 1) + b"".join(
        struct.pack(">dddffffB", v, 0, 0, 0, 0, 0, 0, 253) for v in q)
    cuerpo = modo + articulaciones
    return struct.pack(">iB", 5 + len(cuerpo), 16) + cuerpo


def procesar(mensaje):
    """Lo que hace un receptor con cada mensaje."""
    tipo = mensaje[4] if len(mensaje) > 4 else None
    if tipo == 16:
        leer_estado(mensaje)
    describir_error(mensaje)
    mostrar_mensaje_robot(mensaje)


def prueba_parser():
    bueno = mensaje_estado([0.1, -1.2, 1.5, -0.3, 1.6, 0.0])
    estado = leer_estado(bueno)
    assert estado["q"][1] == -1.2 and estado["programa_en_marcha"] and estado["modo_robot"] == 7

    # Un NaN no debe llegar al dibujo ni a la secuencia
    assert "q" not in leer_estado(mensaje_estado([0, math.nan, 0, 0, 0, 0]))

    azar = random.Random(1)
    for _ in range(PRUEBAS):
        m = bytearray(bueno)
        caso = azar.randrange(3)
        if caso == 0:
            m = m[:azar.randrange(len(m))]                  # truncado
        elif caso == 1:
            for _ in range(azar.randrange(1, 8)):           # bytes cambiados al azar
                m[azar.randrange(len(m))] = azar.randrange(256)
        else:
            m = bytearray(azar.randbytes(azar.randrange(40)))   # basura
        try:
            with contextlib.redirect_stdout(io.StringIO()):     # sin llenar la consola de basura
                procesar(bytes(m))
            cortar_mensajes(bytearray(m))
        except ERRORES_PREVISTOS:
            pass
    print(f"Parser: {PRUEBAS} mensajes rotos sin errores imprevistos")


def prueba_robots_json():
    malos = ["", "{", "[]", "{}", "[1]", '[{"nombre": "a"}]',
             '[{"nombre": "a", "host": ""}]',
             '[{"nombre": "a", "host": "x"}, {"nombre": "a", "host": "y"}]']
    with tempfile.TemporaryDirectory() as carpeta:
        fichero = Path(carpeta) / "robots.json"
        for texto in malos:
            fichero.write_text(texto, encoding="utf-8")
            try:
                cargar_robots(fichero)
            except SystemExit:
                continue
            raise AssertionError(f"robots.json no válido aceptado: {texto}")
        try:
            cargar_robots(Path(carpeta) / "no_existe.json")
            raise AssertionError("fichero inexistente aceptado")
        except SystemExit:
            pass
        bueno = [{"nombre": "a", "host": "1.2.3.4"}]
        fichero.write_text(json.dumps(bueno), encoding="utf-8")
        assert cargar_robots(fichero) == bueno
    print(f"robots.json: {len(malos) + 1} ficheros erróneos rechazados con mensaje")


if __name__ == "__main__":
    prueba_parser()
    prueba_robots_json()
    print("TODO OK")
