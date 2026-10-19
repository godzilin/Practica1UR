"""
Visualizador de varios UR3e a la vez · Bloque C (notable).

Cada robot se lee por la interfaz primaria (30001) en su propio hilo:
si un robot tarda o se desconecta, solo se bloquea su hilo y los demás siguen.

    hilo receptor URSim_1 ─┐
    hilo receptor URSim_2 ─┼─> ultimo_estado (protegido con lock) ─> bucle de dibujo -> PyBullet
    hilo receptor ...     ─┘

- Cada hilo tiene su socket y su buffer, y solo escribe el último q de su robot.
- Solo el bucle principal llama a PyBullet, a ritmo fijo (FPS).
- La lista de robots (nombre e IP) está en robots.json. El puerto es el de esta
    interfaz y las posiciones se generan automáticamente para separarlos.

Cómo usarlo: edita robots.json, cambia las constantes de CONFIGURACIÓN y pulsa F5 (o ▶).
"""

import socket
import struct
import threading
import time

import pybullet as p

from primaria import cargar_robots, cortar_mensajes, leer_estado, grados, SIGNOS, OFFSETS, MSG_ESTADO

# =====================================================================
# CONFIGURACIÓN · cambia aquí lo que necesites
# =====================================================================
FPS = 30                         # veces por segundo que se actualiza PyBullet
SIN_DATOS = 1.0                  # s sin estado nuevo = robot marcado como desconectado
TIMEOUT = 5.0                    # s sin recibir nada = robot colgado o apagado
REINTENTO = 2.0                  # s de espera antes de volver a conectar
ALTURA_ETIQUETA = 0.8            # m por encima de la base donde se escribe el nombre
PUERTO = 30001                   # interfaz primaria
SEPARACION = 1.0                 # m entre robots en la escena
# =====================================================================

VERDE, ROJO = [0, 0.6, 0], [0.9, 0, 0]

# Datos compartidos entre hilos: nombre -> (q, instante en que llegó)
ultimo_estado = {}
lock = threading.Lock()          # nadie lee un q a medio escribir
parar = threading.Event()        # para pedir a los hilos que terminen


def receptor(nombre, host, puerto):
    """Hilo de un robot: conecta, lee sin parar y deja el último q en ultimo_estado.

    No toca PyBullet. Si se corta la conexión, reintenta sin afectar a los demás.
    """
    while not parar.is_set():
        try:
            with socket.create_connection((host, puerto), timeout=TIMEOUT) as sock:
                print(f"[{nombre}] Conectado a {host}:{puerto}")
                buffer = bytearray()                        # cada hilo, su buffer
                while not parar.is_set():
                    datos = sock.recv(4096)
                    if not datos:
                        raise ConnectionError("el robot ha cerrado la conexión")
                    buffer += datos
                    for tipo, mensaje in cortar_mensajes(buffer):
                        if tipo != MSG_ESTADO:
                            continue
                        q = leer_estado(mensaje).get("q")
                        if q is not None:
                            with lock:                      # escribir con el candado
                                ultimo_estado[nombre] = (q, time.monotonic())
        except (OSError, ConnectionError, ValueError, struct.error) as e:
            print(f"[{nombre}] Conexión perdida: {e}. Reintentando en {REINTENTO:.0f} s")
        except Exception as e:
            # Último recurso: un fallo inesperado no debe matar el hilo (el robot quedaría
            # congelado para siempre sin que nadie lo sepa). Se avisa y se reconecta.
            print(f"[{nombre}] Error inesperado: {type(e).__name__}: {e}. Reintentando")
        parar.wait(REINTENTO)                               # como sleep, pero sale si se para


def main():
    robots = cargar_robots()
    mitad = (len(robots) - 1) / 2
    for indice, robot in enumerate(robots):
        robot["puerto"] = PUERTO
        robot["posicion"] = [(indice - mitad) * SEPARACION, 0.0, 0.0, 0.0, 0.0, 0.0]

    # 1. Escena: un único UR3eRG2 y un robot simulado por cada robot real
    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    escena = UR3eRG2()                                      # ya trae el robot 0 en el origen
    for i, r in enumerate(robots):
        pos = r["posicion"]
        if i == 0:
            # El robot 0 ya existe: solo se coloca en su sitio
            p.resetBasePositionAndOrientation(0, pos[:3], p.getQuaternionFromEuler(pos[3:]))
            r["id"] = 0
        else:
            r["id"] = escena.spawn_robot(pos)               # el id NO es consecutivo
        r["conectado"] = False                              # hasta que lleguen datos
        r["etiqueta"] = p.addUserDebugText(f"{r['nombre']} (SIN DATOS)",
                                           [pos[0], pos[1], pos[2] + ALTURA_ETIQUETA],
                                           ROJO, textSize=1.5)

    # 2. Un hilo receptor por robot
    hilos = [threading.Thread(target=receptor, args=(r["nombre"], r["host"], r["puerto"]),
                              daemon=True) for r in robots]
    for h in hilos:
        h.start()

    # 3. Bucle de dibujo: el único sitio donde se llama a PyBullet
    try:
        siguiente = time.monotonic()
        ultimo_print = 0.0
        while True:
            with lock:
                copia = dict(ultimo_estado)                 # copiar y soltar el candado ya
            ahora = time.monotonic()

            for r in robots:
                q, instante = copia.get(r["nombre"], (None, 0.0))
                conectado = q is not None and ahora - instante < SIN_DATOS
                if conectado:
                    r["q"] = q
                    robot_q = [s * v + o for s, v, o in zip(SIGNOS, q, OFFSETS)]
                    escena.move_robot(r["id"], robot_q)
                # Si no hay datos, el robot simulado se queda quieto donde estaba

                if conectado != r["conectado"]:             # solo al cambiar de estado
                    r["conectado"] = conectado
                    texto = r["nombre"] if conectado else f"{r['nombre']} (SIN DATOS)"
                    pos = r["posicion"]
                    r["etiqueta"] = p.addUserDebugText(
                        texto, [pos[0], pos[1], pos[2] + ALTURA_ETIQUETA],
                        VERDE if conectado else ROJO, textSize=1.5,
                        replaceItemUniqueId=r["etiqueta"])
                    print(f"[{r['nombre']}] {'recibiendo datos' if conectado else 'SIN DATOS: robot congelado'}")

            if ahora - ultimo_print >= 1:
                for r in robots:
                    if r["conectado"]:
                        print(f"[{r['nombre']}] q_actual (°): {grados(r['q'])}")
                ultimo_print = ahora

            siguiente += 1 / FPS                            # ritmo fijo sin acumular deriva
            time.sleep(max(0.0, siguiente - time.monotonic()))
    except KeyboardInterrupt:
        print("\nFin")
    except p.error:
        print("Ventana de PyBullet cerrada. Fin")
    finally:
        parar.set()                                         # que los hilos terminen
        for h in hilos:
            h.join(timeout=1)


if __name__ == "__main__":
    main()
