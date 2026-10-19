"""
Mini-aplicación «Enseñar y reproducir» · Bloque D (sobresaliente).

Enseñar una secuencia de puntos, previsualizarla con un robot fantasma y ejecutarla en el
robot punto a punto, comprobando con el estado que publica el robot que cada movimiento ha
terminado. Si el robot avisa de un error o se para, la secuencia se detiene y se muestra el motivo.

    hilo receptor ──> estado del robot (protegido con lock) + cola de errores ─┐
                                                                             v
    bucle principal (único que usa PyBullet y envía órdenes), a FPS veces por segundo:
        1. lee las teclas de la ventana   2. avanza la máquina de estados   3. dibuja

Las órdenes se dan con la ventana de PyBullet activa:
    Espacio  guardar la postura actual como punto      ← →    recorrer los puntos
    D        añadir la postura de los deslizadores     B      borrar el punto seleccionado
    P        previsualizar con el fantasma             Enter  ejecutar / reanudar
    Esc      parar el robot y cancelar                 G / C  guardar / cargar la secuencia
    E        provocar un error (parada de protección) para la demostración
    S        mostrar / ocultar los paneles de PyBullet (deslizadores)

Diseño completo y guion de la defensa: docs/ensenar_reproducir.md
Cómo usarlo: pon el robot el primero de robots.json y pulsa F5 (o ▶) en VS Code.
"""

import json
import math
import textwrap
import unicodedata
import queue
import socket
import struct
import threading
import time
from pathlib import Path

import pybullet as p

from primaria import (cargar_robots, cortar_mensajes, leer_estado, describir_error, grados,
                      es_numero, SIGNOS, OFFSETS, MSG_ESTADO, MSG_ROBOT, MODOS_ROBOT)

# =====================================================================
# CONFIGURACIÓN · cambia aquí lo que necesites
# =====================================================================
V = 0.3                     # rad/s   velocidad de los movej: MÁXIMO permitido en el robot real
A = 0.5                     # rad/s²  aceleración de los movej: MÁXIMO permitido en el robot real
TOLERANCIA = 0.01           # rad: distancia máxima al punto para darlo por alcanzado
TIEMPO_ARRANQUE = 2.0       # s: si el programa no arranca en este tiempo, la orden se ha rechazado
TIEMPO_MAX_MOVIMIENTO = 60  # s: un movimiento que dura más se considera atascado

FPS = 30                    # veces por segundo que se actualiza la ventana
ACELERAR_PREVIEW = 3.0      # la previsualización va este número de veces más rápida que el robot
FICHERO_SECUENCIA = "secuencias/secuencia.json"   # relativo a la carpeta de este script

PUERTO_DASH = 29999         # dashboard server: para desbloquear una parada de protección
TIMEOUT = 5.0               # s sin recibir nada = robot colgado o apagado
REINTENTO = 2.0             # s de espera antes de volver a conectar
SIN_DATOS = 1.0             # s sin estado nuevo = robot desconectado
COLOR_FANTASMA = [0.2, 0.6, 1.0, 0.35]            # azul semitransparente
CAMARA = dict(cameraDistance=1.4, cameraYaw=50, cameraPitch=-30,
              cameraTargetPosition=[0, 0, 0.3])   # vista inicial, centrada en el robot
# =====================================================================

# Teclas (códigos de p.getKeyboardEvents)
ESPACIO, ENTER, ESC = ord(" "), p.B3G_RETURN, 27
IZQUIERDA, DERECHA = p.B3G_LEFT_ARROW, p.B3G_RIGHT_ARROW
# Borrar con B: Supr y Retroceso no siempre llegan a la ventana de PyBullet en Linux
BORRAR = (ord("b"), p.B3G_DELETE, p.B3G_BACKSPACE)

# Ayuda de la ventana: solo las teclas que sirven en cada modo, en líneas cortas
# (en una ventana pequeña una línea larga se sale de la vista o queda tapada por los deslizadores)
AYUDA = {
    "REPOSO": ["Espacio: guardar   P: ver   Enter: ejecutar",
               "<- ->: elegir   B: borrar   D: deslizadores",
               "G: guardar   C: cargar   S: paneles"],
    "PREVISUALIZANDO": ["Esc: cancelar"],
    "ENVIANDO": ["Esc: PARAR   E: provocar error"],
    "MOVIENDO": ["Esc: PARAR   E: provocar error"],
    "REANUDANDO": ["Esc: PARAR"],
    "DETENIDO": ["Enter: reanudar   Esc: cancelar"],
}
ANCHO_LINEA = 42                # caracteres por línea antes de partir un aviso largo
LINEAS_AVISO = 3
PX_POR_TAMANO = 13              # alto aproximado en píxeles de una línea de textSize 1
MARGEN_PX = 20                  # separación del borde de la ventana
ANCHO_PANEL_PX = 260            # lo que tapa el panel izquierdo de PyBullet cuando está visible


def punto_valido(q):
    """6 números finitos entre -2π y 2π. Evita, por ejemplo, enviar grados como si fueran radianes."""
    return (isinstance(q, (list, tuple)) and len(q) == 6
            and all(es_numero(v) and abs(v) <= 2 * math.pi for v in q))


def distancia(q1, q2):
    """Mayor diferencia articular entre dos posturas (rad)."""
    return max(abs(a - b) for a, b in zip(q1, q2))


def a_pybullet(q):
    return [s * v + o for s, v, o in zip(SIGNOS, q, OFFSETS)]


def desde_pybullet(q):
    return [(v - o) / s for s, v, o in zip(SIGNOS, q, OFFSETS)]


# ---------------------------------------------------------------------
# Comunicación con el robot (hilo receptor)
# ---------------------------------------------------------------------
class Robot:
    """Conexión con el robot por la interfaz primaria.

    Un hilo recibe sin parar y deja el último estado en self.estado (con lock) y los errores
    en self.errores (una cola, para no perder ninguno). El bucle principal envía órdenes por
    el mismo socket con enviar(): un hilo lee y otro escribe, TCP es bidireccional.
    """

    def __init__(self, config):
        self.host, self.puerto = config["host"], config["puerto"]
        self.lock = threading.Lock()
        self.estado = None              # último estado: q, programa_en_marcha, parada_proteccion...
        self.instante = 0.0             # cuándo llegó
        self.sock = None                # socket actual (None si no hay conexión)
        self.errores = queue.Queue()
        threading.Thread(target=self._recibir, daemon=True).start()

    def _recibir(self):
        while True:
            try:
                with socket.create_connection((self.host, self.puerto), timeout=TIMEOUT) as sock:
                    print(f"Conectado a {self.host}:{self.puerto}")
                    with self.lock:
                        self.sock = sock
                    buffer = bytearray()
                    while True:
                        datos = sock.recv(4096)
                        if not datos:
                            raise ConnectionError("el robot ha cerrado la conexión")
                        buffer += datos
                        for tipo, mensaje in cortar_mensajes(buffer):
                            if tipo == MSG_ESTADO:
                                estado = leer_estado(mensaje)
                                if "q" in estado and "modo_robot" in estado:
                                    with self.lock:
                                        self.estado, self.instante = estado, time.monotonic()
                            elif tipo == MSG_ROBOT and describir_error(mensaje):
                                self.errores.put(describir_error(mensaje))
            except (OSError, ConnectionError, ValueError, struct.error) as e:
                print(f"Conexión perdida: {e}. Reintentando en {REINTENTO:.0f} s")
            except Exception as e:
                # Último recurso: si este hilo muriera, la aplicación se quedaría sin datos del
                # robot para siempre. Se avisa y se reconecta.
                print(f"Error inesperado en el receptor: {type(e).__name__}: {e}. Reintentando")
            with self.lock:
                self.sock = None
            time.sleep(REINTENTO)

    def conectado(self):
        """Hay conexión TCP abierta (aunque aún no haya llegado ningún estado)."""
        with self.lock:
            return self.sock is not None

    def leer(self):
        """Último estado, o None si hace más de SIN_DATOS que no llega nada."""
        with self.lock:
            if self.estado is None or time.monotonic() - self.instante > SIN_DATOS:
                return None
            return dict(self.estado)

    def enviar(self, orden):
        """Envía una orden URScript (texto terminado en salto de línea)."""
        with self.lock:
            sock = self.sock
        if sock is None:
            return False
        print(">>", orden.strip())
        try:
            sock.sendall((orden.strip() + "\n").encode())
        except OSError as e:                                # cable cortado justo al enviar
            print(f"No se pudo enviar: {e}")
            return False
        return True

    def dashboard(self, orden):
        """Orden de texto al dashboard server (29999). Devuelve su respuesta ("" si falla)."""
        try:
            with socket.create_connection((self.host, PUERTO_DASH), timeout=TIMEOUT) as d:
                d.recv(1024)                                # mensaje de bienvenida
                d.sendall((orden + "\n").encode())
                respuesta = d.recv(1024).decode(errors="replace").strip()
        except OSError as e:
            print(f"[DASH] {orden} -> sin respuesta: {e}")
            return ""
        print(f"[DASH] {orden} -> {respuesta}")
        return respuesta


# ---------------------------------------------------------------------
# La aplicación
# ---------------------------------------------------------------------
class Aplicacion:
    """Máquina de estados de la secuencia:

    REPOSO ──Enter──> ENVIANDO ──programa en marcha──> MOVIENDO ──llegó──> ENVIANDO (siguiente)
       │                  │                               │                 o REPOSO (último)
       │ P                └────────── error ──────────────┴──> DETENIDO ──Enter──> REANUDANDO ──> ENVIANDO
       v                                                          │
    PREVISUALIZANDO ──fin──> REPOSO              Esc (en cualquier momento) ──> REPOSO
    """

    def __init__(self, escena, fantasma, robot):
        self.escena, self.fantasma, self.robot = escena, fantasma, robot
        self.puntos = []                # la secuencia: listas de 6 ángulos (rad)
        self.sel = 0                    # punto seleccionado
        self.modo = "REPOSO"
        self.aviso = "Esperando datos del robot..."
        self.paso = 0                   # punto que se está ejecutando
        self.t_modo = 0.0               # cuándo se entró en el modo actual
        self.preview = None             # trayectoria de la previsualización
        self.q_fantasma = None          # postura del fantasma durante la previsualización
        self.ver_deslizadores = False   # el fantasma muestra los deslizadores
        self.deslizadores = None        # últimos valores leídos
        self.deslizadores_listos = False  # ya puestos en la postura del robot
        self.textos = {}                # ids de los textos de la ventana
        self.paneles = False            # paneles de PyBullet (deslizadores) visibles
        self.camara = None              # última cámara vista y cuándo cambió
        self.t_camara = 0.0
        self.camara_textos = None       # cámara con la que se colocaron los textos
        self.situacion = "nunca"        # None: sin datos · True/False: robot en RUNNING o no

    # ----- utilidades -----
    def cambiar_modo(self, modo, aviso=None):
        self.modo, self.t_modo = modo, time.monotonic()
        if aviso is not None:
            self.avisar(aviso)

    def avisar(self, texto):
        self.aviso = texto
        print(f"[{self.modo}] {texto}")

    def detener(self, motivo):
        self.cambiar_modo("DETENIDO", motivo)          # la ayuda ya dice Enter/Esc

    def iniciar_deslizadores(self, estado):
        """Pone los deslizadores en la postura del robot la primera vez que llegan datos.

        Si el programa arranca sin robot, los deslizadores están en 0 (brazo estirado): con D
        se guardaría esa postura sin querer. Por eso D no funciona hasta que esto se ha hecho.
        """
        if self.deslizadores_listos or estado is None:
            return
        q = a_pybullet(estado["q"])
        actuales = self.escena.get_param_values()
        self.escena.set_param_values({nombre.strip(): (q[i] if i < 6 else v)
                                      for i, (nombre, v) in enumerate(actuales.items())})
        self.deslizadores = None        # este cambio no lo ha hecho el operador
        self.deslizadores_listos = True
        if self.modo == "REPOSO":
            self.avisar("Listo. Lleva el robot a una postura y pulsa Espacio para guardarla")

    def leer_deslizadores(self):
        """Los 6 primeros deslizadores de la ventana (articulaciones del brazo)."""
        valores = self.escena.get_param_values()
        return desde_pybullet([valores[f" j{i}"] for i in range(6)])

    def enviar_punto(self):
        q = self.puntos[self.paso]
        if not punto_valido(q):                             # última comprobación antes de mover
            self.detener(f"Punto {self.paso + 1} no válido: {q}")
            return
        texto = "[" + ", ".join(f"{v:.5f}" for v in q) + "]"
        if self.robot.enviar(f"movej({texto}, a={A}, v={V})"):
            self.cambiar_modo("ENVIANDO", f"Moviendo al punto {self.paso + 1}/{len(self.puntos)}")
        else:
            self.detener("Sin conexión con el robot")

    # ----- teclas -----
    def tecla(self, t, estado):
        if t == ord("s"):
            self.paneles = not self.paneles
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, int(self.paneles))
            self.camara_textos = None                       # recolocar: cambia el sitio libre
        elif t == ESC:
            # También en DETENIDO: tras un corte de red el robot puede seguir moviéndose
            if self.modo in ("ENVIANDO", "MOVIENDO", "REANUDANDO", "DETENIDO"):
                self.robot.enviar("stopj(2)")
            self.cambiar_modo("REPOSO", "Cancelado")
        elif self.modo == "DETENIDO" and t == ENTER:
            self.reanudar(estado)
        elif self.modo in ("ENVIANDO", "MOVIENDO") and t == ord("e"):
            self.avisar("Provocando una parada de protección (demostración)")
            self.robot.enviar("protective_stop()")
        elif self.modo != "REPOSO":
            return                                          # el resto solo en reposo
        elif t == ESPACIO:
            if estado is None:
                self.avisar("Sin datos del robot: no se puede guardar")
            else:
                self.puntos.insert(self.sel + 1 if self.puntos else 0, list(estado["q"]))
                self.sel = self.sel + 1 if len(self.puntos) > 1 else 0
                self.ver_deslizadores = False
                self.avisar(f"Punto {self.sel + 1} guardado: {grados(estado['q'])}")
        elif t == ord("d"):
            q = self.leer_deslizadores()
            if not self.deslizadores_listos:
                self.avisar("Sin datos del robot: los deslizadores aún no están en su postura")
            elif punto_valido(q):
                self.puntos.insert(self.sel + 1 if self.puntos else 0, q)
                self.sel = self.sel + 1 if len(self.puntos) > 1 else 0
                self.ver_deslizadores = False
                self.avisar(f"Punto {self.sel + 1} añadido desde los deslizadores: {grados(q)}")
        elif t in (IZQUIERDA, DERECHA) and self.puntos:
            self.sel = max(0, min(len(self.puntos) - 1, self.sel + (1 if t == DERECHA else -1)))
            self.ver_deslizadores = False
            self.avisar(f"Punto {self.sel + 1}/{len(self.puntos)}: {grados(self.puntos[self.sel])}")
        elif t in BORRAR and self.puntos:
            self.puntos.pop(self.sel)
            self.sel = max(0, min(self.sel, len(self.puntos) - 1))
            self.avisar(f"Punto borrado. Quedan {len(self.puntos)}")
        elif t == ord("p"):
            self.empezar_preview(estado)
        elif t == ENTER:
            self.ejecutar(estado)
        elif t == ord("g"):
            self.guardar()
        elif t == ord("c"):
            self.cargar()

    def ejecutar(self, estado):
        if not self.puntos:
            self.avisar("No hay puntos: enseña alguno con Espacio")
        elif estado is None:
            self.avisar("Sin datos del robot")
        elif estado["modo_robot"] != 7:
            self.avisar("El robot no está en RUNNING: enciéndelo y suelta frenos en PolyScope")
        elif estado["parada_emergencia"]:
            self.avisar("Parada de emergencia: suelta la seta y rearma en PolyScope")
        elif estado["parada_proteccion"]:
            self.avisar("El robot está en parada de protección")
        else:
            self.paso = 0
            self.enviar_punto()

    def reanudar(self, estado):
        while not self.robot.errores.empty():               # descartar errores antiguos
            self.robot.errores.get()
        if estado is None:
            self.detener("Sin conexión con el robot")
            return
        if estado["parada_emergencia"]:
            # Una emergencia NO se desbloquea por red: debe hacerlo una persona en el robot
            self.detener("Parada de emergencia: suelta la seta y rearma en PolyScope")
            return
        if estado["parada_proteccion"]:
            respuesta = self.robot.dashboard("unlock protective stop")
            if "releasing" not in respuesta.lower():
                self.detener(f"No se pudo desbloquear: {respuesta or 'el dashboard no responde'}")
                return
            self.robot.dashboard("close safety popup")
        self.cambiar_modo("REANUDANDO", f"Reanudando en el punto {self.paso + 1}")

    def empezar_preview(self, estado):
        if not self.puntos:
            self.avisar("No hay puntos que previsualizar")
            return
        inicio = estado["q"] if estado else self.puntos[0]
        tramos = list(zip([inicio] + self.puntos[:-1], self.puntos))
        # Duración de cada tramo: lo que tardaría la articulación que más se mueve a velocidad V
        duraciones = [max(distancia(a, b) / V / ACELERAR_PREVIEW, 0.3) for a, b in tramos]
        self.preview = (tramos, duraciones)
        self.cambiar_modo("PREVISUALIZANDO", f"Previsualizando {len(self.puntos)} puntos")

    def guardar(self):
        ruta = Path(__file__).parent / FICHERO_SECUENCIA
        temporal = ruta.with_suffix(".tmp")
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            # Primero a un fichero temporal y luego se renombra: si algo falla a medias,
            # la secuencia guardada antes sigue intacta
            temporal.write_text(json.dumps(self.puntos, indent=4), encoding="utf-8")
            temporal.replace(ruta)
        except OSError as e:
            self.avisar(f"No se pudo guardar {FICHERO_SECUENCIA}: {e}")
            return
        self.avisar(f"{len(self.puntos)} puntos guardados en {FICHERO_SECUENCIA}")

    def cargar(self):
        ruta = Path(__file__).parent / FICHERO_SECUENCIA
        try:
            puntos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.avisar(f"No se pudo cargar {FICHERO_SECUENCIA}: {e}")
            return
        if not isinstance(puntos, list):
            self.avisar(f"{FICHERO_SECUENCIA}: debe ser una lista de puntos. No se carga")
            return
        malos = [i + 1 for i, q in enumerate(puntos) if not punto_valido(q)]
        if malos:
            self.avisar(f"{FICHERO_SECUENCIA}: puntos no válidos {malos}. No se carga")
            return
        self.puntos, self.sel = [list(q) for q in puntos], 0
        self.avisar(f"{len(self.puntos)} puntos cargados de {FICHERO_SECUENCIA}")

    # ----- un fotograma -----
    def paso_maquina(self, estado):
        """Avanza la máquina de estados. Nunca espera: mira el estado y decide."""
        ahora = time.monotonic()
        error = None if self.robot.errores.empty() else self.robot.errores.get()

        # Avisar cuando se pierde o vuelve el robot, o cambia entre encendido y apagado
        # (si no, el último aviso se queda en pantalla aunque ya no sea cierto)
        situacion = None if estado is None else estado["modo_robot"] == 7
        if situacion != self.situacion and not (situacion is None and self.situacion == "nunca"):
            primera_vez = self.situacion == "nunca"     # el aviso inicial lo da iniciar_deslizadores
            self.situacion = situacion
            if primera_vez:
                pass
            elif situacion is None:
                self.avisar("Conexión perdida con el robot: reintentando...")
            else:
                nombre = MODOS_ROBOT.get(estado["modo_robot"], estado["modo_robot"])
                aviso = ("Robot conectado y en RUNNING" if situacion else
                         f"Robot en {nombre}: enciéndelo y suelta frenos en PolyScope")
                self.avisar(aviso)

        if self.modo in ("ENVIANDO", "MOVIENDO"):
            objetivo = self.puntos[self.paso]
            if error:
                self.detener(error)
            elif estado is None:
                self.detener("Conexión perdida con el robot")
            elif estado["parada_emergencia"]:
                self.detener("Parada de emergencia")
            elif estado["parada_proteccion"]:
                self.detener("Parada de protección")
            elif estado["modo_robot"] != 7:
                self.detener("El robot ha dejado de estar en RUNNING (¿apagado? ¿frenos?)")
            elif self.modo == "ENVIANDO":
                if estado["programa_en_marcha"]:
                    self.cambiar_modo("MOVIENDO")
                elif ahora - self.t_modo > TIEMPO_ARRANQUE:
                    if distancia(estado["q"], objetivo) < TOLERANCIA:
                        self.punto_alcanzado()              # ya estaba en el punto
                    else:
                        self.detener(f"La orden no ha arrancado en {TIEMPO_ARRANQUE:.0f} s "
                                     "(¿modo remoto? ¿orden rechazada?)")
            elif not estado["programa_en_marcha"]:          # MOVIENDO y ha terminado
                d = distancia(estado["q"], objetivo)
                if d < TOLERANCIA:
                    self.punto_alcanzado()
                else:
                    self.detener(f"El programa se paró a {d:.3f} rad del punto {self.paso + 1}")
            elif ahora - self.t_modo > TIEMPO_MAX_MOVIMIENTO:
                self.robot.enviar("stopj(2)")
                self.detener(f"El movimiento dura más de {TIEMPO_MAX_MOVIMIENTO} s")

        elif self.modo == "REANUDANDO":
            if (estado is not None and not estado["parada_proteccion"]
                    and not estado["parada_emergencia"] and estado["modo_robot"] == 7):
                self.enviar_punto()                         # reenviar el punto pendiente
            elif ahora - self.t_modo > 5:
                self.detener("El robot no se recupera de la parada")

        elif error:
            self.avisar(error)                              # error fuera de una ejecución

        if self.modo == "PREVISUALIZANDO":
            tramos, duraciones = self.preview
            t = ahora - self.t_modo
            for i, ((a, b), dur) in enumerate(zip(tramos, duraciones)):
                if t <= dur:
                    f = t / dur
                    self.q_fantasma = [x + (y - x) * f for x, y in zip(a, b)]
                    self.aviso = f"Previsualizando tramo {i + 1}/{len(tramos)}"
                    break
                t -= dur
            else:
                self.cambiar_modo("REPOSO", "Previsualización terminada. Enter: ejecutar")

    def punto_alcanzado(self):
        print(f"Punto {self.paso + 1} alcanzado")
        self.paso += 1
        if self.paso < len(self.puntos):
            self.enviar_punto()
        else:
            self.cambiar_modo("REPOSO", f"Secuencia completada ({len(self.puntos)} puntos)")

    # ----- dibujo -----
    def dibujar(self, estado):
        if estado is not None:
            self.escena.move_robot(0, a_pybullet(estado["q"]))

        # Deslizadores: si el operador los mueve, el fantasma los muestra
        valores = self.leer_deslizadores()
        if self.deslizadores is not None and distancia(valores, self.deslizadores) > 1e-6:
            self.ver_deslizadores = True
        self.deslizadores = valores

        # Qué muestra el fantasma
        if self.modo == "PREVISUALIZANDO":
            q = self.q_fantasma
        elif self.modo in ("ENVIANDO", "MOVIENDO", "DETENIDO", "REANUDANDO"):
            q = self.puntos[self.paso]
        elif self.ver_deslizadores or not self.puntos:
            q = valores
        else:
            q = self.puntos[self.sel]
        self.escena.move_robot(self.fantasma, a_pybullet(q))

        # Textos de la ventana
        if estado is None:
            linea_estado = "ESPERANDO DATOS" if self.robot.conectado() else "SIN CONEXIÓN"
        elif self.modo in ("ENVIANDO", "MOVIENDO"):
            linea_estado = f"{self.modo} {self.paso + 1}/{len(self.puntos)}"
        else:
            linea_estado = self.modo
        if estado is not None and estado["modo_robot"] != 7:      # p. ej. recién arrancado URSim
            linea_estado += f" · {MODOS_ROBOT.get(estado['modo_robot'], estado['modo_robot'])}"
        puntos = (f"Puntos: {len(self.puntos)}" +
                  (f" (ves el {self.sel + 1})" if self.puntos else "") +
                  (" · fantasma = deslizadores" if self.ver_deslizadores and self.modo == "REPOSO" else ""))
        if self.modo == "DETENIDO" or estado is None:
            color = [0.8, 0, 0]                             # rojo: hay que hacer algo
        elif estado["modo_robot"] != 7:
            color = [0.9, 0.5, 0]                           # naranja: conectado, robot sin encender
        else:
            color = [0, 0, 0]
        aviso = textwrap.wrap(self.aviso, ANCHO_LINEA)[:LINEAS_AVISO]
        ayuda = AYUDA.get(self.modo, [])
        gris = [0.25, 0.25, 0.25]
        # (texto, color, tamaño): una entrada por línea, de arriba abajo
        lineas = ([(linea_estado, color, 2.2)] + [(a, color, 1.5) for a in aviso] +
                  [(puntos, [0, 0, 0], 1.5)] + [(a, gris, 1.4) for a in ayuda])
        lineas += [("", gris, 1.4)] * (1 + LINEAS_AVISO + 1 + 3 - len(lineas))   # vaciar las sobrantes
        recolocar = self.mirar_camara()
        y_px = MARGEN_PX
        for i, (texto, col, tam) in enumerate(lineas):
            y_px += PX_POR_TAMANO * tam + 4                 # bajar una línea de su altura
            self.texto(i, texto, col, tam, y_px, recolocar)

    def mirar_camara(self):
        """True si hay que recolocar los textos.

        El texto de PyBullet mide siempre lo mismo en píxeles, pero se coloca en coordenadas
        del mundo. Si se cambia el tamaño de la ventana o el zoom, las líneas se montarían unas
        sobre otras o se saldrían de la vista: entonces se recolocan, cuando la cámara lleva
        0,3 s quieta (mientras se arrastra se dejan quietas para que no parpadeen).
        """
        cam = p.getDebugVisualizerCamera()
        clave = (cam[0], cam[1], round(cam[8], 1), round(cam[9], 1), round(cam[10], 3),
                 tuple(round(v, 3) for v in cam[11]))     # ancho, alto, yaw, pitch, dist, objetivo
        ahora = time.monotonic()
        if clave != self.camara:
            self.camara, self.t_camara = clave, ahora
        if clave == self.camara_textos:
            return False
        if self.camara_textos is not None and ahora - self.t_camara < 0.3:
            return False                                    # la primera vez se colocan ya
        self.camara_textos = clave
        ancho, alto, proy = cam[0], cam[1], cam[3]
        unidad = lambda v: [c / math.sqrt(sum(x * x for x in v)) for c in v]
        derecha, arriba, dist, objetivo = unidad(cam[6]), unidad(cam[7]), cam[10], cam[11]
        m_px = 2 * dist / (proy[5] * alto)                  # metros por píxel a la distancia del objetivo
        izquierda_px = MARGEN_PX + (ANCHO_PANEL_PX if self.paneles else 0)
        # Esquina de arriba a la izquierda, en el plano que pasa por el objetivo de la cámara
        self.esquina = [o + (izquierda_px - ancho / 2) * m_px * d + alto / 2 * m_px * a
                        for o, d, a in zip(objetivo, derecha, arriba)]
        self.abajo = [-m_px * a for a in arriba]           # un píxel hacia abajo, en metros
        return True

    def texto(self, fila, texto, color, tam, y_px, recolocar):
        """Una línea del bloque de textos. Solo se redibuja si cambia (si no, parpadea)."""
        anterior = self.textos.get(fila)
        contenido = (texto, tuple(color), tam, y_px)
        if anterior and anterior[1] == contenido and not recolocar:
            return
        posicion = [e + y_px * b for e, b in zip(self.esquina, self.abajo)]
        kwargs = {"replaceItemUniqueId": anterior[0]} if anterior else {}
        id_ = p.addUserDebugText(solo_ascii(texto), posicion, color, textSize=tam, **kwargs)
        self.textos[fila] = (id_, contenido)


def solo_ascii(texto):
    """PyBullet corta el texto en la primera letra no ASCII («dónde» se vería «d»): á -> a, ñ -> n."""
    texto = texto.replace("·", "-").replace("°", "o")
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def leer_teclas():
    """Teclas pulsadas desde el último fotograma, en minúscula."""
    return [t + 32 if 65 <= t <= 90 else t
            for t, est in p.getKeyboardEvents().items() if est & p.KEY_WAS_TRIGGERED]


def main():
    config = cargar_robots()[0]
    print(f"Robot: {config['nombre']} ({config['host']}:{config['puerto']})")
    if config["puerto"] != 30001:
        raise SystemExit("Para enviar órdenes hace falta el puerto 30001 (el 30011 es de solo lectura)")
    if not (0 < V <= 0.3 and 0 < A <= 0.5):
        raise SystemExit("V y A superan los límites de la práctica (0,3 rad/s y 0,5 rad/s²)")

    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    escena = UR3eRG2()                                      # robot 0: el real
    fantasma = escena.spawn_robot([0, 0, 0, 0, 0, 0])       # en la misma base
    for enlace in range(-1, p.getNumJoints(fantasma)):
        p.changeVisualShape(fantasma, enlace, rgbaColor=COLOR_FANTASMA)
    p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)   # teclas libres para nosotros
    for panel in (p.COV_ENABLE_RGB_BUFFER_PREVIEW, p.COV_ENABLE_DEPTH_BUFFER_PREVIEW,
                  p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW):
        p.configureDebugVisualizer(panel, 0)                         # paneles vacíos: más sitio
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)                  # paneles ocultos; S los muestra
    p.resetDebugVisualizerCamera(**CAMARA)

    robot = Robot(config)
    app = Aplicacion(escena, fantasma, robot)

    try:
        siguiente = time.monotonic()
        while True:
            estado = robot.leer()
            app.iniciar_deslizadores(estado)                # en cuanto lleguen datos del robot
            for t in leer_teclas():
                app.tecla(t, estado)
            app.paso_maquina(estado)
            app.dibujar(estado)
            siguiente += 1 / FPS
            time.sleep(max(0.0, siguiente - time.monotonic()))
    except KeyboardInterrupt:
        print("\nFin")
    except p.error:
        print("Ventana de PyBullet cerrada. Fin")
    finally:
        # Salga como salga el programa (Ctrl+C, ventana cerrada o un fallo inesperado),
        # si el robot se estaba moviendo por nosotros, se para
        if app.modo in ("ENVIANDO", "MOVIENDO", "REANUDANDO"):
            robot.enviar("stopj(2)")
            print("Robot parado con stopj al salir")


if __name__ == "__main__":
    main()
