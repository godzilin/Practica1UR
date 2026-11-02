"""
Visualizador de varios UR3e en la misma ventana · Bloque C (notable).

Cada robot se lee por la interfaz primaria (30001) en su propio hilo. Si un robot
tarda o se desconecta, solo se bloquea su hilo y los demás siguen moviéndose.

    hilo receptor robot 1 ─┐
    hilo receptor robot 2 ─┼─> robot["q"] (protegido con lock) ─> bucle de dibujo ─> PyBullet
    hilo receptor ...     ─┘

- Cada hilo tiene su socket y su buffer, y solo escribe el último q de su robot.
- Solo el bucle principal llama a PyBullet.
- Los robots (nombre, IP y posición en la escena) se leen de robots.json.

Cómo usarlo: edita robots.json y pulsa F5 en VS Code.
"""

import json
import math
import socket
import struct
import threading
import time
from pathlib import Path

import pybullet as p
from UR3e_rg2.dynamic_ur3e import UR3eRG2

# ===== CONFIGURACIÓN =====
PUERTO = 30001         # interfaz primaria
FPS = 30               # veces por segundo que se actualiza PyBullet
SIN_DATOS = 1.0        # s sin estado nuevo = robot marcado como desconectado
ALTURA_ETIQUETA = 0.8  # m por encima de la base donde se escribe el nombre
TIMEOUT = 5.0          # s sin recibir nada = robot apagado o cable cortado
REINTENTO = 2.0        # s de espera antes de volver a conectar
MAX_LONGITUD = 65536   # una longitud mayor significa que el buffer está desalineado
TAM_RECV = 65536       # máximo de bytes que devuelve cada recv(). No es el tamaño de un mensaje:
                       # el buffer junta o corta lo que llegue. Cabe el mensaje más largo aceptado
# =========================

MSG_ESTADO = 16        # Robot State Message
SUB_ARTICULACIONES = 1 # subpaquete Joint data

lock = threading.Lock()    # para que el dibujo nunca lea un q a medio escribir


def leer_robots():
    """Lista de robots de robots.json. Cada uno con nombre, host y posicion [x, y, z] (m)."""
    try:
        robots = json.loads(Path(__file__).with_name("robots.json").read_text(encoding="utf-8"))
        if not robots:
            raise ValueError("no hay ningún robot")
        for r in robots:
            r["nombre"], r["host"] = str(r["nombre"]), str(r["host"])
            r["posicion"] = [float(v) for v in r["posicion"]]
            if len(r["posicion"]) != 3:
                raise ValueError(f"la posición de {r['nombre']} no es [x, y, z]")
    except (OSError, ValueError, LookupError, TypeError) as e:   # no existe, mal escrito o le falta algo
        raise SystemExit(f"robots.json no válido: {e!r}")
    return robots


def cortar_mensajes(buffer):
    """Saca del buffer los mensajes completos (longitud de 4 bytes delante) en una lista."""
    completos = []
    while len(buffer) >= 5:
        (longitud,) = struct.unpack_from(">i", buffer)
        if not 5 <= longitud <= MAX_LONGITUD:
            raise ConnectionError(f"longitud imposible ({longitud}): buffer desalineado")
        if len(buffer) < longitud:
            break                                           # aún no ha llegado entero
        completos.append(bytes(buffer[:longitud]))
        del buffer[:longitud]
    return completos


def leer_q(mensaje):
    """Los 6 q_actual (rad) de un mensaje de estado, o None si no se pueden leer.

    Recorre los subpaquetes saltando cada uno con su tamaño hasta el de articulaciones:
    6 bloques de 41 B (>dddffffB) cuyo primer double es q_actual.
    """
    pos = 5                                                 # saltar la cabecera del mensaje
    while pos + 5 <= len(mensaje):
        tam, tipo = struct.unpack_from(">iB", mensaje, pos)
        if tam < 5 or pos + tam > len(mensaje):
            return None                                     # mensaje corrupto
        if tipo == SUB_ARTICULACIONES and tam == 5 + 6 * 41:
            q = [struct.unpack_from(">d", mensaje, pos + 5 + 41 * j)[0] for j in range(6)]
            return q if all(math.isfinite(v) for v in q) else None
        pos += tam
    return None


def receptor(robot):
    """Hilo de un robot: lee sus mensajes sin parar y guarda el último q en robot["q"].

    No toca PyBullet. Si se corta la conexión, reintenta sin afectar a los demás.
    """
    while True:
        try:
            with socket.create_connection((robot["host"], PUERTO), timeout=TIMEOUT) as sock:
                print(f"[{robot['nombre']}] Conectado a {robot['host']}:{PUERTO}")
                buffer = bytearray()                        # cada hilo, su buffer
                while True:
                    datos = sock.recv(TAM_RECV)
                    if not datos:
                        raise ConnectionError("el robot ha cerrado la conexión")
                    buffer += datos
                    for mensaje in cortar_mensajes(buffer):
                        q = leer_q(mensaje) if mensaje[4] == MSG_ESTADO else None
                        if q is not None:
                            with lock:
                                robot["q"], robot["instante"] = q, time.monotonic()
        except OSError as e:
            print(f"[{robot['nombre']}] Conexión perdida: {e}. Reintento en {REINTENTO:.0f} s")
            time.sleep(REINTENTO)


def etiqueta(robot, recibiendo):
    """Escribe (o reescribe) el nombre encima del robot: verde si llegan datos, rojo si no."""
    x, y, z = robot["posicion"]
    texto = robot["nombre"] if recibiendo else f"{robot['nombre']} (SIN DATOS)"
    color = [0, 0.6, 0] if recibiendo else [0.9, 0, 0]
    reemplazar = {"replaceItemUniqueId": robot["etiqueta"]} if "etiqueta" in robot else {}
    robot["etiqueta"] = p.addUserDebugText(texto, [x, y, z + ALTURA_ETIQUETA], color,
                                           textSize=1.5, **reemplazar)


def main():
    robots = leer_robots()
    escena = UR3eRG2()                  # una sola ventana; ya trae un robot (id 0) en el origen
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)     # ocultar los paneles laterales: más sitio

    for i, robot in enumerate(robots):
        if i == 0:                      # el robot 0 ya existe: solo se lleva a su posición
            p.resetBasePositionAndOrientation(0, robot["posicion"], [0, 0, 0, 1])
            robot["id"] = 0
        else:                           # [x, y, z, roll, pitch, yaw]; el id NO es consecutivo
            robot["id"] = escena.spawn_robot(robot["posicion"] + [0, 0, 0])
        robot["q"], robot["instante"], robot["recibiendo"] = None, 0.0, False
        etiqueta(robot, False)
        threading.Thread(target=receptor, args=(robot,), daemon=True).start()

    # Bucle de dibujo: el único sitio donde se llama a PyBullet
    while True:
        ahora = time.monotonic()
        for robot in robots:
            with lock:                  # copiar y soltar el candado enseguida
                q, instante = robot["q"], robot["instante"]
            recibiendo = ahora - instante < SIN_DATOS
            if recibiendo:
                escena.move_robot(robot["id"], list(q))
            # Si no llegan datos, el robot de la pantalla se queda quieto donde estaba
            if recibiendo != robot["recibiendo"]:          # solo al cambiar
                robot["recibiendo"] = recibiendo
                etiqueta(robot, recibiendo)
                print(f"[{robot['nombre']}] {'recibiendo datos' if recibiendo else 'SIN DATOS'}")
        time.sleep(1 / FPS)


if __name__ == "__main__":
    try:
        main()          # los hilos receptores son daemon: terminan con el programa
    except KeyboardInterrupt:
        print("Fin")
    except p.error:
        print("Ventana de PyBullet cerrada. Fin")
