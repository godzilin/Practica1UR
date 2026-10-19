"""
Túnel UR_A -> UR_B (sin RTDE): el robot 2 imita al robot 1.

Hilos:
  - hilo LECTOR : lee las articulaciones del robot 1 (127.0.0.1:30001)
                  y guarda la última lectura en 'source'.
  - hilo ESCRITOR: a 10 Hz toma esa lectura y se la manda al robot 2
                   (127.0.0.1:30011) como comando URScript.
  - hilo principal: lanza los hilos, espera Ctrl+C y los detiene.
"""

import socket
import struct
import threading
import time

# Ejemplo histórico de productor-consumidor: el lector produce q_actual y el
# escritor la transforma en URScript para el segundo robot.
# ---------------------------------------------------------------
# 1. CONFIGURACIÓN
# ---------------------------------------------------------------
SRC_HOST, SRC_PORT = "127.0.0.1", 30001      # robot 1 (origen), primaria
DST_HOST, DST_PORT = "10.172.18.9", 30011      # robot 2 (destino), primaria
DST_DASH_PORT = 29998                        # dashboard del robot 2

PERIODO = 0.05            # 10 Hz-500Hz
MAX_SALTO = 0.5          # rad. Si la diferencia es mayor, hacemos movej lento
PREPARAR_DESTINO = True  # encender y soltar frenos del robot 2 automáticamente

MSG_ROBOT_STATE = 16
SUB_JOINT_DATA = 1

# ---------------------------------------------------------------
# 2. DATOS COMPARTIDOS
# ---------------------------------------------------------------
source = {"joints": None, "t": 0.0}   # última lectura del robot 1
lock = threading.Lock()               # protege 'source'
stop_event = threading.Event()        # para parar los hilos


# ---------------------------------------------------------------
# 3. LECTURA DEL PROTOCOLO (igual que antes)
# ---------------------------------------------------------------
def recv_exact(sock, n):
    """Lee exactamente n bytes del socket."""
    # TCP puede fragmentar incluso una cabecera, así que se acumula hasta n.
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Conexión cerrada")
        data.extend(chunk)
    return bytes(data)


def read_message(sock):
    """Lee un mensaje completo: (tipo, contenido)."""
    # length cuenta también los 5 bytes de la cabecera primaria.
    length, = struct.unpack("!I", recv_exact(sock, 4))
    msg_type, = struct.unpack("!B", recv_exact(sock, 1))
    return msg_type, recv_exact(sock, length - 5)


def parse_joints(payload):
    """Busca el subpaquete de articulaciones y devuelve 6 ángulos (rad)."""
    # Se devuelve el primer subpaquete de articulaciones y se ignoran los demás.
    offset = 0
    while offset < len(payload):
        size, sub_type = struct.unpack_from("!IB", payload, offset)
        if sub_type == SUB_JOINT_DATA:
            body = payload[offset + 5: offset + size]
            # 41 bytes por articulación; el primer double es q_actual
            return [struct.unpack_from("!d", body, i * 41)[0] for i in range(6)]
        offset += size
    return None


# ---------------------------------------------------------------
# 4. HILO LECTOR: robot 1
# ---------------------------------------------------------------
def reader_worker():
    """Lee sin parar el robot 1 y actualiza 'source'."""
    # Solo este hilo escribe source; el Lock coordina la lectura del escritor.
    while not stop_event.is_set():
        try:
            print(f"[LECTOR] Conectando a robot 1 ({SRC_HOST}:{SRC_PORT})")
            with socket.create_connection((SRC_HOST, SRC_PORT), timeout=5) as s:
                s.settimeout(5)
                while not stop_event.is_set():
                    msg_type, payload = read_message(s)
                    if msg_type != MSG_ROBOT_STATE:
                        continue
                    joints = parse_joints(payload)
                    if joints:
                        with lock:
                            source["joints"] = joints
                            source["t"] = time.time()
        except (OSError, ConnectionError, struct.error) as e:
            print(f"[LECTOR] Error: {e}. Reintentando en 2 s")
            time.sleep(2)


# ---------------------------------------------------------------
# 5. PREPARAR EL ROBOT 2 (opcional, vía Dashboard)
# ---------------------------------------------------------------
def preparar_destino():
    """Enciende el robot 2 y suelta los frenos para que pueda moverse."""
    # Dashboard usa comandos de texto independientes del flujo de estado.
    try:
        with socket.create_connection((DST_HOST, DST_DASH_PORT), timeout=5) as d:
            d.settimeout(5)
            print("[DASH]", d.recv(1024).decode().strip())   # mensaje de bienvenida
            for cmd in ("power on", "brake release"):
                d.sendall((cmd + "\n").encode())
                print(f"[DASH] {cmd} ->", d.recv(1024).decode().strip())
                time.sleep(1)
        time.sleep(5)   # el simulador tarda unos segundos en liberar frenos
    except OSError as e:
        print(f"[DASH] No se pudo preparar el robot 2: {e}")


# ---------------------------------------------------------------
# 6. COMANDOS URSCRIPT
# ---------------------------------------------------------------
def fmt(q):
    """Convierte la lista de ángulos a texto URScript: [0.1,0.2,...]"""
    return "[" + ",".join(f"{v:.5f}" for v in q) + "]"


def cmd_servoj(q):
    # servoj(q, a, v, t, lookahead_time, gain): seguimiento suave de un punto
    return f"servoj({fmt(q)}, 0, 0, {PERIODO}, 0.1, 300)\n"


def cmd_movej(q):
    # movej(q, a, v): movimiento normal, para saltos grandes (más lento y seguro)
    return f"movej({fmt(q)}, a=0.5, v=0.3)\n"


# ---------------------------------------------------------------
# 7. HILO ESCRITOR: robot 2
# ---------------------------------------------------------------
def writer_worker():
    """A 10 Hz manda al robot 2 la última posición del robot 1."""
    # El escritor copia la lectura bajo lock y libera el lock antes de enviar.
    ultimo_enviado = None
    while not stop_event.is_set():
        try:
            print(f"[ESCRITOR] Conectando a robot 2 ({DST_HOST}:{DST_PORT})")
            with socket.create_connection((DST_HOST, DST_PORT), timeout=5) as s:
                print("[ESCRITOR] Conectado")
                next_tick = time.monotonic()

                while not stop_event.is_set():
                    # Copiar la última lectura del robot 1
                    with lock:
                        q = source["joints"]

                    if q is not None:
                        # ¿Cuánto se tiene que mover el robot 2?
                        if ultimo_enviado is None:
                            salto = float("inf")        # primer envío
                        else:
                            salto = max(abs(a - b) for a, b in zip(q, ultimo_enviado))

                        if salto > MAX_SALTO:
                            # Salto grande: movimiento completo y esperar un poco
                            s.sendall(cmd_movej(q).encode())
                            print("[ESCRITOR] Salto grande -> movej")
                            time.sleep(3)
                        else:
                            s.sendall(cmd_servoj(q).encode())
                        ultimo_enviado = q

                    # Mantener 10 Hz estables
                    next_tick += PERIODO
                    time.sleep(max(0, next_tick - time.monotonic()))

        except (OSError, ConnectionError) as e:
            print(f"[ESCRITOR] Error: {e}. Reintentando en 2 s")
            time.sleep(2)


# ---------------------------------------------------------------
# 8. PROGRAMA PRINCIPAL
# ---------------------------------------------------------------
def main():
    # El principal no trabaja con sockets: coordina apagado y ciclo de vida.
    if PREPARAR_DESTINO:
        preparar_destino()

    hilos = [
        threading.Thread(target=reader_worker, daemon=True),
        threading.Thread(target=writer_worker, daemon=True),
    ]
    for h in hilos:
        h.start()

    try:
        while True:                      # el principal solo vigila
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo túnel...")
        stop_event.set()
        for h in hilos:
            h.join(timeout=1)


if __name__ == "__main__":
    main()