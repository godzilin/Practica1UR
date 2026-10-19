"""
Visualizador UR3e por la interfaz de tiempo real (puerto 30003) · Bloque B.

El robot envía 500 veces por segundo (e-Series) un paquete de estructura fija:
sin tipos ni subpaquetes, cada campo siempre en el mismo byte. Los 6 ángulos
(q_actual) empiezan en el byte 252.

A 500 Hz no se puede dibujar cada paquete: se reciben todos, se guarda solo el
último y PyBullet se actualiza a un ritmo fijo (FPS).

Cómo usarlo: pon el robot el primero de robots.json, cambia las constantes de
CONFIGURACIÓN si hace falta y pulsa F5 (o ▶) en VS Code.
"""

import math
import socket
import struct
import time

import pybullet as p

from primaria import cargar_robots, grados, SIGNOS, OFFSETS    # el convenio se ajusta en primaria.py

# =====================================================================
# CONFIGURACIÓN · cambia aquí lo que necesites
# =====================================================================
# La IP se toma del primer robot de robots.json; este script usa su propia interfaz.
PUERTO = 30003              # interfaz de tiempo real

# Qué se muestra por consola:
#   "angulos"  -> B2/B3/B4: una vez por segundo, paquetes/s, paquetes por recv() y ángulos
#   "paquetes" -> B1: bytes de cada recv() y longitud de cada paquete
MODO = "angulos"

USAR_PYBULLET = True        # False: no abre la ventana (útil para probar solo la red)
FPS = 30                    # veces por segundo que se actualiza PyBullet

TIMEOUT = 5.0               # s sin recibir nada = robot colgado o apagado
REINTENTO = 2.0             # s de espera antes de volver a conectar
MAX_LONGITUD = 65536        # una longitud mayor significa que el buffer está desalineado

# Posiciones fijas dentro del paquete (hoja Client Interfaces, pestaña RealTime)
POS_Q_ACTUAL = 252          # 6 double: ángulos reales de las articulaciones
# =====================================================================


def cortar_paquetes(buffer):
    """Saca del buffer todos los paquetes completos y los devuelve en una lista.

    Igual que en la primaria, pero la cabecera son solo 4 bytes (la longitud):
    aquí no hay campo de tipo porque solo existe un tipo de paquete.
    La longitud depende de la versión del robot, así que se lee del propio paquete.
    """
    completos = []
    while len(buffer) >= 4:
        (longitud,) = struct.unpack_from(">i", buffer, 0)
        if longitud < POS_Q_ACTUAL + 48 or longitud > MAX_LONGITUD:
            raise ConnectionError(f"Longitud imposible ({longitud}): buffer desalineado")
        if len(buffer) < longitud:
            break                                           # aún no ha llegado entero
        completos.append(bytes(buffer[:longitud]))
        del buffer[:longitud]
    return completos


def conectar_y_visualizar(robot, host):
    """Una conexión completa con el robot. Termina con una excepción si se corta."""
    with socket.create_connection((host, PUERTO), timeout=TIMEOUT) as sock:
        print(f"Conectado a {host}:{PUERTO}")
        buffer = bytearray()
        q = None                                            # último q_actual recibido
        paquetes = 0                                        # contador para paquetes/s
        max_por_recv = 0                                    # más paquetes sacados de un recv()
        ultimo_dibujo = ultimo_print = time.monotonic()

        while True:
            # 1. Recibir lo que haya y añadirlo al buffer
            datos = sock.recv(65536)
            if not datos:
                raise ConnectionError("El robot ha cerrado la conexión")
            if MODO == "paquetes":
                print(f"recv() -> {len(datos)} B")
            buffer += datos

            # 2. Consumir TODOS los paquetes completos, quedándonos solo con el último
            nuevos = cortar_paquetes(buffer)
            for paquete in nuevos:
                if MODO == "paquetes":
                    print(f"    paquete de {len(paquete)} B")
                nuevo = list(struct.unpack_from(">6d", paquete, POS_Q_ACTUAL))
                if all(math.isfinite(v) for v in nuevo):    # un NaN no se dibuja
                    q = nuevo
            paquetes += len(nuevos)
            max_por_recv = max(max_por_recv, len(nuevos))

            # 3. Dibujar a ritmo fijo, no con cada paquete
            ahora = time.monotonic()
            if robot is not None and q is not None and ahora - ultimo_dibujo >= 1 / FPS:
                robot.move_robot(0, [s * v + o for s, v, o in zip(SIGNOS, q, OFFSETS)])
                ultimo_dibujo = ahora

            # 4. Una vez por segundo: estadísticas
            if MODO == "angulos" and q is not None and ahora - ultimo_print >= 1:
                # Si el programa va al día, cada recv() trae 1 paquete (a veces 2).
                # Si no da abasto, se acumulan en el buffer del sistema operativo y
                # cada recv() trae muchos de golpe: el robot de la pantalla iría con retraso.
                print(f"{paquetes / (ahora - ultimo_print):5.0f} paquetes/s  "
                      f"máx {max_por_recv:3d} por recv()  q_actual (°): {grados(q)}")
                paquetes = max_por_recv = 0
                ultimo_print = ahora


def main():
    config = cargar_robots()[0]                             # el primer robot de robots.json
    print(f"Robot: {config['nombre']} ({config['host']}:{PUERTO})")

    robot = None
    if USAR_PYBULLET:
        from UR3e_rg2.dynamic_ur3e import UR3eRG2
        robot = UR3eRG2()                                   # abre la ventana con el robot 0

    # Si se pierde la conexión (URSim reiniciado, cable...), se vuelve a intentar
    try:
        while True:
            try:
                conectar_y_visualizar(robot, config["host"])
            except p.error:
                raise                                       # la ventana no es la red: no reintentar
            except (OSError, ConnectionError, ValueError, struct.error) as e:
                print(f"Conexión perdida: {e}. Reintentando en {REINTENTO:.0f} s")
                time.sleep(REINTENTO)
    except KeyboardInterrupt:
        print("\nFin")
    except p.error:
        print("Ventana de PyBullet cerrada. Fin")


if __name__ == "__main__":
    main()
