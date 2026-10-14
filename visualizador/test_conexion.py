"""
Test de conexión con el robot por la interfaz primaria (30001).

Lee la versión, el modo y los ángulos del robot. Si MOVER = True, además gira la base
GIRO_BASE grados con un movej, comprueba que ha llegado y la devuelve a su sitio.

El robot es el primero de robots.json.

Cómo usarlo: cambia las constantes de CONFIGURACIÓN y pulsa F5 (o ▶) en VS Code.
"""

import math
import socket
import struct
import time

from primaria import cargar_robots, cortar_mensajes, leer_estado, mostrar_mensaje_robot, grados

# =====================================================================
# CONFIGURACIÓN · cambia aquí lo que necesites
# =====================================================================
MOVER = False               # True: gira la base y vuelve (¡robot real solo con el profesor!)
GIRO_BASE = 10.0            # grados que gira la base (se limita a ±30)
PREPARAR = False            # True: antes enciende el robot y suelta frenos (dashboard)

V, A = 0.3, 0.5             # rad/s y rad/s²: límites obligatorios en el robot real
TOLERANCIA = 0.01           # rad: error máximo para dar el movimiento por bueno
PUERTO = 30001              # interfaz primaria (acepta órdenes URScript; la 30011 no)
PUERTO_DASH = 29999         # dashboard server
# =====================================================================

MODOS_ROBOT = {0: "DISCONNECTED", 1: "CONFIRM_SAFETY", 2: "BOOTING", 3: "POWER_OFF",
               4: "POWER_ON", 5: "IDLE", 6: "BACKDRIVE", 7: "RUNNING"}


def mensajes(sock):
    """Recibe del socket y va entregando los mensajes completos, uno a uno."""
    buffer = bytearray()
    while True:
        datos = sock.recv(4096)
        if not datos:
            raise ConnectionError("El robot ha cerrado la conexión")
        buffer += datos
        yield from cortar_mensajes(buffer)


def siguiente_estado(lector):
    """Espera al próximo mensaje de estado. Por el camino muestra los errores del robot."""
    for tipo, mensaje in lector:
        if tipo == 20:
            mostrar_mensaje_robot(mensaje)
        elif tipo == 16:
            estado = leer_estado(mensaje)
            if "q" in estado and "modo_robot" in estado:
                return estado


def preparar(host):
    """Enciende el robot y suelta los frenos con comandos de texto al dashboard."""
    with socket.create_connection((host, PUERTO_DASH), timeout=5) as d:
        print("[DASH]", d.recv(1024).decode(errors="replace").strip())   # mensaje de bienvenida
        for orden in ("power on", "brake release"):
            d.sendall((orden + "\n").encode())
            print(f"[DASH] {orden} ->", d.recv(1024).decode(errors="replace").strip())
            time.sleep(2)
    time.sleep(3)                                           # tarda en soltar frenos


def mover(sock, lector, objetivo, timeout=15):
    """Envía un movej y confirma que se ha cumplido mirando el estado del robot.

    El robot no responde a las órdenes: hay que deducirlo de lo que publica.
    1) isProgramRunning pasa a True (ha aceptado la orden)
    2) vuelve a False (ha terminado)
    3) q_actual está cerca del objetivo
    """
    # No con assert: python -O se salta los assert, y esto protege al robot
    if not all(math.isfinite(v) and abs(v) <= 2 * math.pi for v in objetivo):
        raise ValueError(f"Ángulo fuera de rango: {objetivo}")
    orden = f"movej([{', '.join(f'{v:.5f}' for v in objetivo)}], a={A}, v={V})\n"
    print(">>", orden.strip())
    sock.sendall(orden.encode())                            # el '\n' final es obligatorio

    inicio = time.monotonic()
    while not siguiente_estado(lector)["programa_en_marcha"]:
        if time.monotonic() - inicio > 2:
            print("La orden no ha arrancado en 2 s: ¿modo remoto? ¿robot en RUNNING?")
            return False

    while True:
        estado = siguiente_estado(lector)
        if estado["parada_proteccion"]:
            print("Parada de protección")
            return False
        if not estado["programa_en_marcha"]:
            break
        if time.monotonic() - inicio > timeout:
            print("Timeout esperando el fin del movimiento")
            return False

    error = max(abs(a - b) for a, b in zip(estado["q"], objetivo))
    print(f"Fin. q = {grados(estado['q'])}  error máx {error:.4f} rad")
    return error < TOLERANCIA


def main():
    config = cargar_robots()[0]                             # el primer robot de robots.json
    host = config["host"]
    print(f"Robot: {config['nombre']}")

    if PREPARAR:
        preparar(host)

    with socket.create_connection((host, PUERTO), timeout=5) as sock:
        print(f"Conectado a {host}:{PUERTO}")
        lector = mensajes(sock)

        # Contar cuántos estados llegan en 1 s (debe salir unos 10)
        t0, n = time.monotonic(), 0
        while time.monotonic() - t0 < 1:
            estado = siguiente_estado(lector)
            n += 1
        print(f"{n} estados en 1 s")
        print(f"Modo: {MODOS_ROBOT.get(estado['modo_robot'], estado['modo_robot'])}  "
              f"programa: {estado['programa_en_marcha']}  "
              f"parada protección: {estado['parada_proteccion']}")
        print(f"q_actual (°): {grados(estado['q'])}")

        if not MOVER:
            return
        if estado["modo_robot"] != 7:
            print("El robot no está en RUNNING: enciéndelo en PolyScope o pon PREPARAR = True")
            return

        if estado["parada_proteccion"] or estado["parada_emergencia"]:
            print("El robot está parado por seguridad: desbloquéalo en PolyScope")
            return

        inicio = list(estado["q"])
        destino = inicio.copy()
        destino[0] += math.radians(max(-30.0, min(30.0, GIRO_BASE)))
        try:
            ok = mover(sock, lector, destino) and mover(sock, lector, inicio)
        except KeyboardInterrupt:
            sock.sendall(b"stopj(2)\n")                     # no dejar el robot moviéndose
            print("\nInterrumpido: robot parado con stopj")
            return
        print("MOVIMIENTO OK" if ok else "MOVIMIENTO FALLIDO")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFin")
    except (OSError, ConnectionError, ValueError, struct.error) as e:
        print(f"Error de comunicación: {e}")
        print("¿Robot encendido? ¿IP de robots.json correcta? ¿Misma red que el robot?")
