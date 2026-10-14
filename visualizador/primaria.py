"""
Visualizador UR3e por la interfaz primaria (puerto 30001) · Bloque A.

Se conecta al robot (URSim o real), lee los mensajes binarios que envía 10 veces
por segundo, saca los 6 ángulos de las articulaciones (q_actual) y mueve con ellos
el UR3e de PyBullet.

Cómo usarlo: pon el robot el primero de robots.json, cambia las constantes de
CONFIGURACIÓN si hace falta y pulsa F5 (o ▶) en VS Code.
"""

import json
import math
import socket
import struct
import time
from pathlib import Path

# =====================================================================
# CONFIGURACIÓN · cambia aquí lo que necesites
# =====================================================================
# El robot (nombre, IP y puerto) NO se escribe aquí: se usa el primero de robots.json.
# Para cambiar de robot (otra VM, un UR3e real) se edita ese fichero, sin tocar el código.
FICHERO_ROBOTS = "robots.json"   # en la misma carpeta que este script

# Qué se muestra por consola (un hito del enunciado en cada caso):
#   "angulos"  -> A4/A5: los 6 ángulos en grados, una vez por segundo
#   "bytes"    -> A1: cuántos bytes devuelve cada recv()
#   "mensajes" -> A2/A3: longitud y tipo de cada mensaje, y sus subpaquetes
MODO = "angulos"

USAR_PYBULLET = True        # False: no abre la ventana (útil para probar solo la red)

# Convenio de ángulos robot -> PyBullet. Si en la ventana alguna articulación sale
# con el signo cambiado, pon -1 en su SIGNO; si sale girada, pon el giro (rad) en su OFFSET.
SIGNOS = [1, 1, 1, 1, 1, 1]
OFFSETS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

TIMEOUT = 5.0               # s sin recibir nada = robot colgado o apagado
REINTENTO = 2.0             # s de espera antes de volver a conectar
MAX_LONGITUD = 65536        # una longitud mayor significa que el buffer está desalineado

# Tipos del protocolo (documento Primary/Secondary Client Interface)
MSG_ESTADO = 16             # Robot State Message: llega 10 veces por segundo
MSG_ROBOT = 20              # Robot Message: versión, errores, excepciones...
SUB_MODO = 0                # subpaquete Robot mode data
SUB_ARTICULACIONES = 1      # subpaquete Joint data
# =====================================================================


def cargar_robots():
    """Lee robots.json y comprueba que cada robot tiene todo lo necesario."""
    ruta = Path(__file__).with_name(FICHERO_ROBOTS)
    robots = json.loads(ruta.read_text(encoding="utf-8"))
    for r in robots:
        for clave in ("nombre", "host", "puerto", "posicion"):
            if clave not in r:
                raise SystemExit(f"{FICHERO_ROBOTS}: al robot {r} le falta '{clave}'")
        if len(r["posicion"]) != 6:
            raise SystemExit(f"{FICHERO_ROBOTS}: 'posicion' de {r['nombre']} debe ser "
                             "[x, y, z, roll, pitch, yaw]")
    return robots


def cortar_mensajes(buffer):
    """Saca del buffer todos los mensajes completos y los devuelve como [(tipo, mensaje)].

    TCP entrega un flujo de bytes: un recv() puede traer medio mensaje, uno o varios.
    Cada mensaje empieza por su longitud (4 bytes, incluida la cabecera) y su tipo (1 byte),
    así que se puede saber dónde acaba cada uno.
    """
    completos = []
    while len(buffer) >= 5:                                 # hay al menos una cabecera
        longitud, tipo = struct.unpack_from(">iB", buffer, 0)   # '>' = big-endian
        if longitud < 5 or longitud > MAX_LONGITUD:
            raise ConnectionError(f"Longitud imposible ({longitud}): buffer desalineado")
        if len(buffer) < longitud:
            break                                           # aún no ha llegado entero
        completos.append((tipo, bytes(buffer[:longitud])))
        del buffer[:longitud]                               # quitarlo del buffer
    return completos


def subpaquetes(mensaje):
    """Recorre un mensaje de estado y devuelve [(tipo, inicio, tamaño)] de cada subpaquete.

    Cada subpaquete también empieza por su tamaño (4 bytes) y su tipo (1 byte):
    para pasar al siguiente basta con sumar el tamaño, aunque no sepamos qué contiene.
    """
    lista = []
    pos = 5                                                 # saltar la cabecera del mensaje
    while pos < len(mensaje):
        tam, tipo = struct.unpack_from(">iB", mensaje, pos)
        if tam < 5 or pos + tam > len(mensaje):
            raise ValueError(f"El subpaquete {tipo} ({tam} B) se sale del mensaje")
        lista.append((tipo, pos, tam))
        pos += tam
    return lista


def leer_estado(mensaje):
    """Extrae de un mensaje de estado (tipo 16) los ángulos y el modo del robot."""
    estado = {}
    for tipo, pos, tam in subpaquetes(mensaje):
        datos = pos + 5                                     # primer byte después de la cabecera
        if tipo == SUB_MODO:
            # uint64 timestamp (8 B) y 7 bool: ..., isProtectiveStopped (byte 12),
            # isProgramRunning (13), isProgramPaused (14); robotMode en el byte 15
            estado["parada_proteccion"] = bool(mensaje[datos + 12])
            estado["programa_en_marcha"] = bool(mensaje[datos + 13])
            estado["modo_robot"] = mensaje[datos + 15]
        elif tipo == SUB_ARTICULACIONES:
            # 6 articulaciones de 41 B (>dddffffB). El primer double es q_actual.
            if tam != 5 + 6 * 41:
                print(f"AVISO: el subpaquete de articulaciones mide {tam} B, no 251")
            estado["q"] = [struct.unpack_from(">d", mensaje, datos + 41 * j)[0] for j in range(6)]
    return estado


def mostrar_mensaje_robot(mensaje):
    """Mensajes tipo 20. Su subtipo está en el byte 14: versión (3), error (6), excepción (10)."""
    subtipo = mensaje[14]
    if subtipo == 3:
        n = mensaje[15]                                     # longitud del nombre
        nombre = mensaje[16:16 + n].decode(errors="replace")
        print(f"Versión: {nombre} {mensaje[16 + n]}.{mensaje[17 + n]}")
    elif subtipo == 6:
        print(f"ERROR del robot: {mensaje[32:].decode(errors='replace')}")
    elif subtipo == 10:
        linea, columna = struct.unpack_from(">ii", mensaje, 15)
        print(f"EXCEPCIÓN en línea {linea}, columna {columna}: "
              f"{mensaje[23:].decode(errors='replace')}")


def grados(q):
    """Lista de radianes -> texto en grados, para imprimir."""
    return "[" + ", ".join(f"{math.degrees(v):7.2f}" for v in q) + "]"


def conectar_y_visualizar(robot, host, puerto):
    """Una conexión completa con el robot. Termina con una excepción si se corta."""
    with socket.create_connection((host, puerto), timeout=TIMEOUT) as sock:
        print(f"Conectado a {host}:{puerto}")
        buffer = bytearray()
        ultimo_print = 0.0

        while True:
            # 1. Recibir lo que haya y añadirlo al buffer
            datos = sock.recv(4096)
            if not datos:
                raise ConnectionError("El robot ha cerrado la conexión")
            if MODO == "bytes":
                print(f"recv() -> {len(datos)} B")
            buffer += datos

            # 2. Procesar cada mensaje completo que haya en el buffer
            for tipo, mensaje in cortar_mensajes(buffer):
                if MODO == "mensajes":
                    imprimir_estructura(tipo, mensaje)

                if tipo == MSG_ROBOT:
                    mostrar_mensaje_robot(mensaje)
                elif tipo == MSG_ESTADO:
                    q = leer_estado(mensaje).get("q")
                    if q is None:
                        continue
                    if robot is not None:
                        q_pybullet = [s * v + o for s, v, o in zip(SIGNOS, q, OFFSETS)]
                        robot.move_robot(0, q_pybullet)
                    if MODO == "angulos" and time.monotonic() - ultimo_print >= 1:
                        print(f"q_actual (°): {grados(q)}")
                        ultimo_print = time.monotonic()
                # El resto de tipos no nos interesan: se ignoran


def imprimir_estructura(tipo, mensaje):
    """Hitos A2/A3: longitud y tipo del mensaje y, si es de estado, sus subpaquetes."""
    print(f"mensaje {len(mensaje):5d} B  tipo {tipo}")
    if tipo == MSG_ESTADO:
        subs = subpaquetes(mensaje)
        for t, _, tam in subs:
            print(f"    subpaquete tipo {t:2d}  {tam:4d} B")
        suma = sum(tam for _, _, tam in subs)
        print(f"    suma de subpaquetes = {suma} B, mensaje - 5 = {len(mensaje) - 5} B")


def main():
    config = cargar_robots()[0]                             # el primer robot de robots.json
    print(f"Robot: {config['nombre']} ({config['host']}:{config['puerto']})")

    robot = None
    if USAR_PYBULLET:
        from UR3e_rg2.dynamic_ur3e import UR3eRG2
        robot = UR3eRG2()                                   # abre la ventana con el robot 0

    # Si se pierde la conexión (URSim reiniciado, cable...), se vuelve a intentar
    try:
        while True:
            try:
                conectar_y_visualizar(robot, config["host"], config["puerto"])
            except (OSError, ConnectionError, ValueError, struct.error) as e:
                print(f"Conexión perdida: {e}. Reintentando en {REINTENTO:.0f} s")
                time.sleep(REINTENTO)
    except KeyboardInterrupt:
        print("\nFin")


if __name__ == "__main__":
    main()
