"""
Lectura simultánea de dos robots UR (simuladores) sin RTDE.
Usa la interfaz primaria (~10 Hz), con un hilo por robot.

Estructura:
  - Hilo UR_A  -> lee 127.0.0.1:30001 -> guarda en latest["UR_A"]
  - Hilo UR_B  -> lee 127.0.0.1:30011 -> guarda en latest["UR_B"]
  - Hilo principal -> cada 0.1 s imprime lo último de cada robot
"""

import socket
import struct
import threading
import time

# ---------------------------------------------------------------
# 1. CONFIGURACIÓN
# ---------------------------------------------------------------
# Nombre del robot -> (IP, puerto de la interfaz primaria)
# La VM 1 usa 30001; la VM 2 reenvía su 30001 al puerto 30011 del host
ROBOTS = {
    "UR_A": ("127.0.0.1", 30001),
    "UR_B": ("127.0.0.1", 30011),
}

PERIODO = 0.1  # 10 Hz para la impresión

# Tipos de mensaje/subpaquete del protocolo de UR
MSG_ROBOT_STATE = 16   # mensaje con el estado del robot
SUB_JOINT_DATA = 1     # subpaquete: articulaciones
SUB_CARTESIAN = 4      # subpaquete: posición cartesiana del TCP

# ---------------------------------------------------------------
# 2. DATOS COMPARTIDOS ENTRE HILOS
# ---------------------------------------------------------------
# Aquí cada hilo deja su última lectura
latest = {name: None for name in ROBOTS}

# El Lock garantiza que solo un hilo a la vez lea/escriba el diccionario
lock = threading.Lock()

# Evento para pedir a los hilos que terminen (Ctrl+C)
stop_event = threading.Event()


# ---------------------------------------------------------------
# 3. FUNCIONES PARA LEER EL PROTOCOLO
# ---------------------------------------------------------------
def recv_exact(sock, n):
    """Lee exactamente n bytes (TCP puede entregarlos por trozos)."""
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("El robot cerró la conexión")
        data.extend(chunk)
    return bytes(data)


def read_message(sock):
    """Lee un mensaje completo: devuelve (tipo, contenido)."""
    # Cabecera: 4 bytes de longitud total + 1 byte de tipo
    length, = struct.unpack("!I", recv_exact(sock, 4))
    msg_type, = struct.unpack("!B", recv_exact(sock, 1))
    # El resto del mensaje (la longitud incluye los 5 bytes de cabecera)
    payload = recv_exact(sock, length - 5)
    return msg_type, payload


def parse_robot_state(payload):
    """Recorre los subpaquetes y extrae articulaciones y pose del TCP."""
    joints, tcp = None, None
    offset = 0
    while offset < len(payload):
        # Cada subpaquete: 4 bytes de tamaño + 1 byte de tipo + datos
        size, sub_type = struct.unpack_from("!IB", payload, offset)
        body = payload[offset + 5: offset + size]

        if sub_type == SUB_JOINT_DATA:
            joints = []
            for i in range(6):                 # 6 articulaciones
                # Cada una ocupa 41 bytes; los 3 primeros doubles son
                # q_actual, q_target y qd_actual. Solo usamos q_actual.
                q_actual, _, _ = struct.unpack_from("!ddd", body, i * 41)
                joints.append(q_actual)

        elif sub_type == SUB_CARTESIAN:
            # X, Y, Z (m) y Rx, Ry, Rz (rad, vector de rotación)
            tcp = struct.unpack_from("!6d", body, 0)

        offset += size                          # saltar al siguiente subpaquete
    return joints, tcp


# ---------------------------------------------------------------
# 4. FUNCIÓN QUE EJECUTA CADA HILO
# ---------------------------------------------------------------
def robot_worker(name, host, port):
    """Se conecta a un robot y actualiza latest[name] sin parar.
    Si se pierde la conexión, reintenta cada 2 s."""
    while not stop_event.is_set():
        try:
            print(f"[{name}] Conectando a {host}:{port} ...")
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(5)
                print(f"[{name}] Conectado")

                while not stop_event.is_set():
                    msg_type, payload = read_message(sock)

                    # Ignoramos todo lo que no sea estado del robot
                    if msg_type != MSG_ROBOT_STATE:
                        continue

                    joints, tcp = parse_robot_state(payload)
                    if joints and tcp:
                        # 'with lock' bloquea el acceso mientras escribimos
                        with lock:
                            latest[name] = {
                                "t": time.time(),
                                "joints": joints,
                                "tcp": tcp,
                            }

        except (OSError, ConnectionError, struct.error) as e:
            print(f"[{name}] Error: {e}. Reintentando en 2 s")
            time.sleep(2)


# ---------------------------------------------------------------
# 5. PROGRAMA PRINCIPAL
# ---------------------------------------------------------------
def main():
    # Crear y lanzar un hilo por robot
    threads = []
    for name, (host, port) in ROBOTS.items():
        t = threading.Thread(
            target=robot_worker,
            args=(name, host, port),
            daemon=True,       # el hilo muere si termina el programa
        )
        t.start()
        threads.append(t)

    # Bucle principal: imprime a 10 Hz lo último que dejó cada hilo
    try:
        next_tick = time.monotonic()
        while True:
            with lock:
                # Copiamos para soltar el lock cuanto antes
                snapshot = dict(latest)

            for name, data in snapshot.items():
                if data is None:
                    print(f"{name}: sin datos todavía")
                else:
                    tcp = [round(v, 4) for v in data["tcp"]]
                    q = [round(v, 4) for v in data["joints"]]
                    print(f"{name} | TCP={tcp} | q={q}")
            print("-" * 60)

            # Dormir lo justo para mantener 10 Hz estables
            next_tick += PERIODO
            time.sleep(max(0, next_tick - time.monotonic()))

    except KeyboardInterrupt:
        print("\nDeteniendo...")
        stop_event.set()
        for t in threads:
            t.join(timeout=1)


if __name__ == "__main__":
    main()