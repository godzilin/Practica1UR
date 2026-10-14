import socket
import struct
import time

HOST = "127.0.0.1"
PORT = 30001          # interfaz primaria (~10 Hz)
PERIOD = 0.05          # 10 Hz

MSG_ROBOT_STATE = 16
SUB_JOINT_DATA = 1
SUB_CARTESIAN = 4


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexión cerrada por el robot")
        buf.extend(chunk)
    return bytes(buf)


def read_message(sock):
    """Devuelve (tipo, payload) de un mensaje de la interfaz primaria."""
    length, = struct.unpack("!I", recv_exact(sock, 4))
    mtype, = struct.unpack("!B", recv_exact(sock, 1))
    payload = recv_exact(sock, length - 5)
    return mtype, payload


def parse_robot_state(payload):
    """Extrae joints (rad) y TCP pose de los subpaquetes."""
    joints, tcp = None, None
    off = 0
    while off < len(payload):
        size, stype = struct.unpack_from("!IB", payload, off)
        body = payload[off + 5: off + size]
        if stype == SUB_JOINT_DATA:
            joints = []
            for i in range(6):
                q_act, q_tgt, qd_act = struct.unpack_from("!ddd", body, i * 41)
                joints.append(q_act)
        elif stype == SUB_CARTESIAN:
            tcp = struct.unpack_from("!6d", body, 0)  # X,Y,Z,Rx,Ry,Rz
        off += size
    return joints, tcp


def main():
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.settimeout(5)
        last = None          # último estado recibido
        next_tick = time.monotonic()
        s.setblocking(False)
        buf_sock = s
        s.setblocking(True)

        while True:
            # Lee mensajes hasta obtener un Robot State
            while True:
                mtype, payload = read_message(s)
                if mtype == MSG_ROBOT_STATE:
                    j, t = parse_robot_state(payload)
                    if j and t:
                        last = (j, t)
                    break

            # Con 10 Hz nativos, cada Robot State ya llega a ~10 Hz
            if last:
                joints, tcp = last
                print(f"{time.time():.3f} | "
                      f"q[rad]={[round(x, 4) for x in joints]} | "
                      f"TCP[m,rad]={[round(x, 4) for x in tcp]}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass