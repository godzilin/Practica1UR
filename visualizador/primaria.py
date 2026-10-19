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

import pybullet as p

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
MODOS_ROBOT = {0: "DISCONNECTED", 1: "CONFIRM_SAFETY", 2: "BOOTING", 3: "POWER_OFF",
               4: "POWER_ON", 5: "IDLE", 6: "BACKDRIVE", 7: "RUNNING"}    # robotMode
# =====================================================================


def es_numero(v):
    """int o float finito (True/False no cuentan, aunque en Python sean int)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def cargar_robots(fichero=FICHERO_ROBOTS):
    """Lee robots.json y comprueba que cada robot tiene todo lo necesario.

    Cualquier fallo del fichero termina el programa con un mensaje claro, no con un traceback.
    """
    ruta = Path(__file__).parent / fichero                   # una ruta absoluta se usa tal cual
    try:
        robots = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError as e:
        raise SystemExit(f"No se puede leer {ruta}: {e}")
    except ValueError as e:                                 # JSON mal escrito (coma, comillas...)
        raise SystemExit(f"{fichero} no es un JSON válido: {e}")

    if not isinstance(robots, list) or not robots:
        raise SystemExit(f"{fichero}: debe ser una lista [ ... ] con al menos un robot")
    nombres = set()
    for r in robots:
        if not isinstance(r, dict):
            raise SystemExit(f"{fichero}: cada robot debe ser un objeto {{ ... }}, no {r!r}")
        for clave in ("nombre", "host", "puerto", "posicion"):
            if clave not in r:
                raise SystemExit(f"{fichero}: al robot {r} le falta '{clave}'")
        nombre = r["nombre"]
        if not isinstance(nombre, str) or not nombre or nombre in nombres:
            raise SystemExit(f"{fichero}: el nombre {nombre!r} está vacío o repetido")
        nombres.add(nombre)
        if not isinstance(r["host"], str) or not r["host"].strip():
            raise SystemExit(f"{fichero}: 'host' de {nombre} debe ser una IP entre comillas")
        if not isinstance(r["puerto"], int) or isinstance(r["puerto"], bool) \
                or not 1 <= r["puerto"] <= 65535:
            raise SystemExit(f"{fichero}: 'puerto' de {nombre} debe ser un entero (p. ej. 30001)")
        pos = r["posicion"]
        if not isinstance(pos, list) or len(pos) != 6 or not all(es_numero(v) for v in pos):
            raise SystemExit(f"{fichero}: 'posicion' de {nombre} debe ser "
                             "[x, y, z, roll, pitch, yaw] (6 números)")
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
        if tipo == SUB_MODO and tam >= 5 + 16:
            # uint64 timestamp (8 B) y 7 bool: ..., isEmergencyStopped (byte 11),
            # isProtectiveStopped (12), isProgramRunning (13), isProgramPaused (14); robotMode en el 15
            estado["parada_emergencia"] = bool(mensaje[datos + 11])
            estado["parada_proteccion"] = bool(mensaje[datos + 12])
            estado["programa_en_marcha"] = bool(mensaje[datos + 13])
            estado["modo_robot"] = mensaje[datos + 15]
        elif tipo == SUB_ARTICULACIONES:
            # 6 articulaciones de 41 B (>dddffffB). El primer double es q_actual.
            if tam != 5 + 6 * 41:
                print(f"AVISO: el subpaquete de articulaciones mide {tam} B, no 251")
                if tam < 5 + 6 * 41:
                    continue                                # no caben los 6 ángulos
            q = [struct.unpack_from(">d", mensaje, datos + 41 * j)[0] for j in range(6)]
            if all(math.isfinite(v) for v in q):            # un NaN no se dibuja ni se guarda
                estado["q"] = q
    return estado


def describir_error(mensaje):
    """Texto de un mensaje de error tipo 20, o None si no es un error.

    Subtipo 6: error del robot (p. ej. parada de protección). Lleva un código y un argumento;
    el texto puede venir vacío, así que se muestra el código como en PolyScope: C<código>A<arg>.
    Subtipo 10: excepción del programa URScript, con la línea y la columna del fallo.
    """
    if len(mensaje) < 23:                                   # demasiado corto: no es un error completo
        return None
    subtipo = mensaje[14]
    if subtipo == 6:
        codigo, argumento = struct.unpack_from(">ii", mensaje, 15)
        texto = mensaje[32:].decode(errors="replace").strip("\x00 ")
        return f"Error del robot C{codigo}A{argumento}" + (f": {texto}" if texto else "")
    if subtipo == 10:
        linea, columna = struct.unpack_from(">ii", mensaje, 15)
        return (f"Excepción en línea {linea}, columna {columna}: "
                f"{mensaje[23:].decode(errors='replace')}")
    return None


def mostrar_mensaje_robot(mensaje):
    """Mensajes tipo 20. Su subtipo está en el byte 14: versión (3), error (6), excepción (10)."""
    if len(mensaje) < 16:
        return
    subtipo = mensaje[14]
    if subtipo == 3:
        n = mensaje[15]                                     # longitud del nombre
        if len(mensaje) < 18 + n:
            return
        nombre = mensaje[16:16 + n].decode(errors="replace")
        print(f"Versión: {nombre} {mensaje[16 + n]}.{mensaje[17 + n]}")
    elif describir_error(mensaje):
        print(describir_error(mensaje))


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
