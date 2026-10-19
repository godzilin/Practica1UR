"""
Ensenar y reproducir con varios robots.

Es la version multi-robot de ensenar_reproducir.py. Usa robots.json para crear una
aplicacion independiente por robot, pero comparte una sola ventana de PyBullet.

Teclas:
    1..9  seleccionar robot
    L     activar/desactivar bucle automatico
    Las demas teclas son las de ensenar_reproducir.py para el robot seleccionado.

pasa al siguiente robot con puntos validos. Cada robot conserva su propia secuencia.
El bucle automatico repite la secuencia del robot seleccionado. Cada robot conserva
su propia secuencia.
"""

import json
import math
import threading
import time
from pathlib import Path

import pybullet as p

from ensenar_reproducir import (Aplicacion, FICHERO_SECUENCIA, Robot, a_pybullet,
                                cargar_robots, punto_valido, solo_ascii)
from primaria import MODOS_ROBOT, SIGNOS, OFFSETS

FPS = 30
SIN_DATOS = 1.0
ALTURA_ETIQUETA = 0.8
ALTURA_MENU = 1.25
PUERTO = 30001
SEPARACION = 1.0


class EscenaRobot:
    """Vista de la escena limitada a un robot real y su panel de deslizadores."""

    def __init__(self, escena, robot_id):
        self.escena = escena
        self.robot_id = robot_id

    def move_robot(self, _, q):
        self.escena.move_robot(self.robot_id, q)

    def get_param_values(self):
        return self.escena.get_param_values()

    def set_param_values(self, valores):
        self.escena.set_param_values(valores)


class AplicacionRobot(Aplicacion):
    """Aplicacion original con un fichero de secuencia propio."""

    def __init__(self, escena, fantasma, robot, nombre):
        super().__init__(escena, fantasma, robot)
        ruta = Path(FICHERO_SECUENCIA)
        self.fichero_secuencia = str(ruta.with_name(f"{ruta.stem}_{nombre}{ruta.suffix}"))

    def guardar(self):
        ruta = Path(__file__).parent / self.fichero_secuencia
        temporal = ruta.with_suffix(".tmp")
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal.write_text(json.dumps(self.puntos, indent=4), encoding="utf-8")
            temporal.replace(ruta)
        except OSError as error:
            self.avisar(f"No se pudo guardar {self.fichero_secuencia}: {error}")
            return
        self.avisar(f"{len(self.puntos)} puntos guardados en {self.fichero_secuencia}")

    def cargar(self):
        ruta = Path(__file__).parent / self.fichero_secuencia
        try:
            puntos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            self.avisar(f"No se pudo cargar {self.fichero_secuencia}: {error}")
            return
        if not isinstance(puntos, list):
            self.avisar(f"{self.fichero_secuencia}: debe ser una lista de puntos")
            return
        malos = [indice + 1 for indice, punto in enumerate(puntos)
                 if not punto_valido(punto)]
        if malos:
            self.avisar(f"{self.fichero_secuencia}: puntos no validos {malos}")
            return
        self.puntos, self.sel = [list(punto) for punto in puntos], 0
        self.avisar(f"{len(self.puntos)} puntos cargados de {self.fichero_secuencia}")


class AplicacionMultiple:
    """Coordina una aplicacion de ensenar/reproducir por cada robot."""

    def __init__(self, escena, robots):
        self.escena = escena
        self.robots = robots
        self.aplicaciones = []
        for robot in robots:
            robot["conexion"] = Robot(robot)
            escena_robot = EscenaRobot(escena, robot["id"])
            fantasma = escena.spawn_robot(robot["posicion"])
            for enlace in range(-1, p.getNumJoints(fantasma)):
                p.changeVisualShape(fantasma, enlace,
                                    rgbaColor=[0.2, 0.6, 1.0, 0.35])
            robot["fantasma"] = fantasma
            self.aplicaciones.append(AplicacionRobot(escena_robot, fantasma,
                                                     robot["conexion"], robot["nombre"]))
        self.seleccion = 0
        self.automatico = False
        self.etiquetas = {}
        self.menu_id = None
        self.menu_contenido = None
        self._crear_menu()

    @property
    def actual(self):
        return self.aplicaciones[self.seleccion]

    @property
    def robot_actual(self):
        return self.robots[self.seleccion]

    def _crear_menu(self):
        for robot in self.robots:
            posicion = robot["posicion"]
            self.etiquetas[robot["nombre"]] = p.addUserDebugText(
                robot["nombre"],
                [posicion[0], posicion[1], posicion[2] + ALTURA_ETIQUETA],
                [0.3, 0.3, 0.3], textSize=1.3)

    def seleccionar(self, indice):
        if indice < 0 or indice >= len(self.robots):
            return
        anterior = self.actual
        if anterior.modo in ("ENVIANDO", "MOVIENDO", "REANUDANDO"):
            anterior.robot.enviar("stopj(2)")
            anterior.cambiar_modo("REPOSO", "Movimiento cancelado al cambiar de robot")
        self.seleccion = indice
        app = self.actual
        app.ver_deslizadores = False
        app.deslizadores = None
        app.deslizadores_listos = False
        app.camara_textos = None
        app.avisar(f"Seleccionado {self.robot_actual['nombre']} ({indice + 1}/{len(self.robots)})")
        self._actualizar_menu()

    def alternar_automatico(self):
        self.automatico = not self.automatico
        estado = "activado" if self.automatico else "desactivado"
        self.actual.avisar(f"Bucle automatico {estado}")

    def _actualizar_menu(self):
        nombres = []
        for indice, robot in enumerate(self.robots):
            marca = "*" if indice == self.seleccion else " "
            nombres.append(f"{indice + 1}:{marca}{robot['nombre']}")
        texto = " | ".join(nombres) + f"   L: bucle {'ON' if self.automatico else 'OFF'}"
        posicion = [-0.9, -0.7, 1.65]
        if self.menu_id is None:
            self.menu_id = p.addUserDebugText(solo_ascii(texto), posicion,
                                              [0.1, 0.1, 0.1], textSize=1.4)
        elif texto != self.menu_contenido:
            self.menu_id = p.addUserDebugText(solo_ascii(texto), posicion,
                                              [0.1, 0.1, 0.1], textSize=1.4,
                                              replaceItemUniqueId=self.menu_id)
        self.menu_contenido = texto

    def tecla(self, tecla, estado):
        if ord("1") <= tecla <= ord("9"):
            indice = tecla - ord("1")
            if indice < len(self.robots):
                self.seleccionar(indice)
            return
        if tecla == ord("l"):
            self.alternar_automatico()
            return
        self.actual.tecla(tecla, estado)

    def _estado_de(self, robot):
        return robot["conexion"].leer()

    def actualizar_modelos(self):
        for robot in self.robots:
            estado = self._estado_de(robot)
            robot["estado"] = estado
            conectado = estado is not None
            robot["conectado"] = conectado
            if conectado:
                self.escena.move_robot(robot["id"], a_pybullet(estado["q"]))
                color = [0, 0.6, 0]
            else:
                color = [0.9, 0, 0]
            texto = robot["nombre"] if conectado else f"{robot['nombre']} (SIN DATOS)"
            posicion = robot["posicion"]
            self.etiquetas[robot["nombre"]] = p.addUserDebugText(
                texto, [posicion[0], posicion[1], posicion[2] + ALTURA_ETIQUETA],
                color, textSize=1.3,
                replaceItemUniqueId=self.etiquetas[robot["nombre"]])
        self._actualizar_menu()

    def avanzar_bucle(self, modo_anterior):
        if not self.automatico:
            return
        app = self.actual
        termino = (modo_anterior in ("ENVIANDO", "MOVIENDO")
                   and app.modo == "REPOSO" and app.puntos
                   and app.paso >= len(app.puntos))
        if not termino:
            return
        estado = self.robot_actual["estado"]
        app.ejecutar(estado)

    def fotograma(self):
        self.actualizar_modelos()
        estado = self.robot_actual["estado"]
        self.actual.iniciar_deslizadores(estado)
        modo_anterior = self.actual.modo
        self.actual.paso_maquina(estado)
        self.avanzar_bucle(modo_anterior)
        self.actual.dibujar(estado)


def main():
    robots = cargar_robots()
    if len(robots) > 9:
        raise SystemExit("Este visualizador admite como maximo 9 robots (teclas 1..9)")
    mitad = (len(robots) - 1) / 2
    for indice, robot in enumerate(robots):
        robot["puerto"] = PUERTO
        robot["posicion"] = [(indice - mitad) * SEPARACION, 0.0, 0.0, 0.0, 0.0, 0.0]

    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    escena = UR3eRG2()
    for indice, robot in enumerate(robots):
        posicion = robot["posicion"]
        if indice == 0:
            p.resetBasePositionAndOrientation(0, posicion[:3],
                                              p.getQuaternionFromEuler(posicion[3:]))
            robot["id"] = 0
        else:
            robot["id"] = escena.spawn_robot(posicion)

    p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(cameraDistance=2.4, cameraYaw=45,
                                 cameraPitch=-30, cameraTargetPosition=[0, 0, 0.3])

    gestor = AplicacionMultiple(escena, robots)
    try:
        siguiente = time.monotonic()
        while True:
            estado = gestor.robot_actual["estado"]
            for tecla in (t + 32 if 65 <= t <= 90 else t
                          for t, est in p.getKeyboardEvents().items()
                          if est & p.KEY_WAS_TRIGGERED):
                gestor.tecla(tecla, estado)
            gestor.fotograma()
            siguiente += 1 / FPS
            time.sleep(max(0.0, siguiente - time.monotonic()))
    except KeyboardInterrupt:
        print("\nFin")
    except p.error:
        print("Ventana de PyBullet cerrada. Fin")
    finally:
        for app in gestor.aplicaciones:
            if app.modo in ("ENVIANDO", "MOVIENDO", "REANUDANDO"):
                app.robot.enviar("stopj(2)")


if __name__ == "__main__":
    main()
