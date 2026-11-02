"""
Prueba sin robot ni red de las partes de los scripts que leen datos de fuera.

1. Mensajes rotos (truncados, con bytes al azar, basura): el parser de cada script solo
   puede fallar con OSError (ConnectionError), que es lo que su bucle captura para
   reconectar. Cualquier otro error (IndexError, struct.error...) lo dejaría colgado.
2. Un mensaje correcto se lee bien y un ángulo NaN no llega al dibujo.
3. La máquina de estados de ensenar_reproducir.py con un robot falso: confirma cada
   punto, se detiene ante un error y no se mueve si el robot no está listo.

Es el único .py que importa a los demás, porque es su prueba.
Cómo usarlo: python extras/prueba_robustez.py. Si todo va bien, termina con "TODO OK".
"""

import contextlib
import io
import math
import queue
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "entrega"))
import ensenar_reproducir   # noqa: E402  (después de añadir la carpeta entrega)
import primaria             # noqa: E402
import tiempo_real          # noqa: E402
import varios_robots        # noqa: E402

PRUEBAS = 20000


def mensaje_estado(q, en_marcha=False, proteccion=False):
    """Mensaje tipo 16 mínimo y correcto: subpaquete de modo (26 B) + articulaciones (251 B)."""
    modo = struct.pack(">iBQ7?B", 5 + 8 + 7 + 1, 0, 0,
                       True, True, True, False, proteccion, en_marcha, False, 7)
    articulaciones = struct.pack(">iB", 251, 1) + b"".join(
        struct.pack(">dddffffB", v, 0, 0, 0, 0, 0, 0, 253) for v in q)
    cuerpo = modo + articulaciones
    return struct.pack(">iB", 5 + len(cuerpo), 16) + cuerpo


def paquete_tiempo_real(q):
    """Paquete del puerto 30003 con q_actual en el byte 252 y 1220 B en total."""
    cuerpo = bytearray(1220)
    struct.pack_into(">i", cuerpo, 0, 1220)
    struct.pack_into(">6d", cuerpo, 252, *q)
    return bytes(cuerpo)


def leer_todo(m):
    """Lo que hacen los scripts con los bytes recibidos."""
    for cortar, leer in ((primaria.cortar_mensajes, primaria.leer_q),
                         (varios_robots.cortar_mensajes, varios_robots.leer_q),
                         (ensenar_reproducir.cortar_mensajes, ensenar_reproducir.leer_estado)):
        for mensaje in cortar(bytearray(m)):
            leer(mensaje)
    for mensaje in [m]:                                     # también tal cual, sin cortar
        primaria.leer_q(mensaje)
        primaria.leer_version(mensaje)
        ensenar_reproducir.leer_estado(mensaje)
        ensenar_reproducir.leer_error(mensaje)
    tiempo_real.cortar_paquetes(bytearray(m))


def prueba_parsers():
    q = [0.1, -1.2, 1.5, -0.3, 1.6, 0.0]
    bueno = mensaje_estado(q)
    assert primaria.leer_q(bueno) == q
    assert varios_robots.leer_q(bueno) == q
    estado = ensenar_reproducir.leer_estado(bueno)
    assert estado["q"] == q and estado["modo_robot"] == 7 and not estado["programa_en_marcha"]

    # Dos mensajes y medio en el buffer: salen dos y el medio se queda esperando
    buffer = bytearray(bueno * 2 + bueno[:100])
    assert len(primaria.cortar_mensajes(buffer)) == 2 and len(buffer) == 100

    # Tiempo real: q_actual en el byte 252
    buffer = bytearray(paquete_tiempo_real(q) * 3)
    paquetes = tiempo_real.cortar_paquetes(buffer)
    assert len(paquetes) == 3 and list(struct.unpack_from(">6d", paquetes[0], 252)) == q

    # Un NaN no debe llegar al dibujo ni a la secuencia
    malo = mensaje_estado([0, math.nan, 0, 0, 0, 0])
    assert primaria.leer_q(malo) is None and ensenar_reproducir.leer_estado(malo) is None

    azar = random.Random(1)
    for _ in range(PRUEBAS):
        m = bytearray(azar.choice([bueno, paquete_tiempo_real(q)]))
        caso = azar.randrange(3)
        if caso == 0:
            m = m[:azar.randrange(len(m))]                  # truncado
        elif caso == 1:
            for _ in range(azar.randrange(1, 8)):           # bytes cambiados al azar
                m[azar.randrange(len(m))] = azar.randrange(256)
        else:
            m = bytearray(azar.randbytes(azar.randrange(40)))   # basura
        try:
            with contextlib.redirect_stdout(io.StringIO()):     # sin llenar la consola de avisos
                leer_todo(bytes(m))
        except OSError:
            pass                                            # el bucle del script reconecta
    print(f"Parsers: {PRUEBAS} mensajes rotos sin errores imprevistos")


class RobotFalso:
    """Hace de Robot en ensenar_reproducir: guarda lo que se envía y no abre conexiones."""

    def __init__(self):
        self.enviado = []
        self.errores = queue.Queue()

    def enviar(self, orden):
        self.enviado.append(orden)
        return True

    def dashboard(self, orden):
        return "ok"


def prueba_maquina_estados():
    er = ensenar_reproducir
    estado = er.leer_estado(mensaje_estado([0.0] * 6))
    robot = RobotFalso()
    app = er.Aplicacion(None, None, robot)
    app.puntos = [[0.5] * 6, [0.0] * 6]
    with contextlib.redirect_stdout(io.StringIO()):
        app.ejecutar(estado)
        assert app.modo == "ENVIANDO" and robot.enviado[-1].startswith("movej([0.50000")

        # Arranca, se mueve y llega al punto 1: se envía el punto 2
        app.actualizar({**estado, "programa_en_marcha": True})
        assert app.modo == "MOVIENDO"
        app.actualizar({**estado, "q": [0.5] * 6})
        assert app.modo == "ENVIANDO" and app.paso == 1

        # Un error del robot detiene la secuencia, y Enter la reanuda en el mismo punto
        robot.errores.put("Error del robot C209A0")
        app.actualizar(estado)
        assert app.modo == "DETENIDO" and app.aviso == "Error del robot C209A0"
        app.reanudar(estado)
        app.actualizar(estado)
        assert app.modo == "ENVIANDO" and app.paso == 1

        # Termina lejos del objetivo (alguien lo ha parado): se detiene
        app.actualizar({**estado, "programa_en_marcha": True})
        app.actualizar({**estado, "q": [0.3] * 6})
        assert app.modo == "DETENIDO"

        # Esc manda stopj y vuelve a reposo
        app.tecla(er.ESC, estado)
        assert app.modo == "REPOSO" and robot.enviado[-1] == "stopj(2)"

        # Con una parada de protección no se envía nada
        n = len(robot.enviado)
        app.ejecutar({**estado, "parada_proteccion": True})
        assert app.modo == "REPOSO" and len(robot.enviado) == n

        # Un punto en grados (fuera de ±2π) nunca se envía
        app.puntos = [[90.0] * 6]
        app.ejecutar(estado)
        assert app.modo == "DETENIDO" and len(robot.enviado) == n
    print("Máquina de estados: confirmación, errores, reanudar y límites correctos")


if __name__ == "__main__":
    prueba_parsers()
    prueba_maquina_estados()
    print("TODO OK")
