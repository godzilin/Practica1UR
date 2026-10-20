"""
Ensenar y reproducir con varios robots.

Es la version multi-robot de ensenar_reproducir.py. Usa robots.json para crear una
aplicacion independiente por robot, pero comparte una sola ventana de PyBullet.

Teclas:
    1..9  seleccionar robot
    A     ejecutar la secuencia de todos los robots
    L     activar/desactivar bucle automatico
    Las demas teclas son las de ensenar_reproducir.py para el robot seleccionado.

pasa al siguiente robot con puntos validos. Cada robot conserva su propia secuencia.
El bucle automatico se configura por robot y cada robot conserva su propia secuencia.
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
    """Adaptador de una escena compartida para una aplicacion concreta.

    ``Aplicacion`` espera recibir una escena que sepa mover un robot y leer los
    deslizadores. Como todos los robots viven en la misma escena de PyBullet,
    este adaptador redirige esas operaciones al robot real o a su fantasma.
    Asi cada aplicacion puede trabajar como si tuviera una escena propia.
    """

    def __init__(self, escena, robot_id, fantasma_id):
        self.escena = escena
        self.robot_id = robot_id
        self.fantasma_id = fantasma_id

    def move_robot(self, robot_id, q):
        """Mueve el modelo real o el fantasma asociado a esta aplicacion."""
        destino = self.fantasma_id if robot_id == self.fantasma_id else self.robot_id
        self.escena.move_robot(destino, q)

    def get_param_values(self):
        """Devuelve los valores actuales de los deslizadores de PyBullet."""
        return self.escena.get_param_values()

    def set_param_values(self, valores):
        """Coloca los deslizadores en los valores recibidos."""
        self.escena.set_param_values(valores)


class AplicacionRobot(Aplicacion):
    """Aplicacion original con un fichero de secuencia propio.

    La clase hereda toda la logica de ensenar/reproducir y solo especializa la
    persistencia: cada robot guarda sus puntos en un JSON distinto para que las
    secuencias no se mezclen.
    """

    def __init__(self, escena, fantasma, robot, nombre):
        super().__init__(escena, fantasma, robot)
        ruta = Path(FICHERO_SECUENCIA)
        self.fichero_secuencia = str(ruta.with_name(f"{ruta.stem}_{nombre}{ruta.suffix}"))

    def guardar(self):
        """Guarda de forma atomica la secuencia de este robot en su fichero JSON."""
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
        """Carga y valida la secuencia propia del robot seleccionado."""
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
    """Coordina una aplicacion de ensenar/reproducir por cada robot.

    Solo existe un bucle principal y una ventana de PyBullet, pero cada robot
    conserva su conexion, estado, secuencia y opcion de bucle automatico.
    ``aplicaciones`` y ``robots`` se mantienen en el mismo orden para poder
    relacionarlos mediante ``zip``.
    """

    def __init__(self, escena, robots):
        """Crea los robots fantasma y una aplicacion independiente por robot."""
        self.escena = escena
        self.robots = robots
        self.aplicaciones = []
        for robot in robots:
            robot["estado"] = None
            robot["conectado"] = False
            robot["automatico"] = False
            robot["conexion"] = Robot(robot)
            fantasma = escena.spawn_robot(robot["posicion"])
            escena_robot = EscenaRobot(escena, robot["id"], fantasma)
            for enlace in range(-1, p.getNumJoints(fantasma)):
                p.changeVisualShape(fantasma, enlace,
                                    rgbaColor=[0.2, 0.6, 1.0, 0.35])
            robot["fantasma"] = fantasma
            self.aplicaciones.append(AplicacionRobot(escena_robot, fantasma,
                                                     robot["conexion"], robot["nombre"]))
        self.seleccion = 0
        self.etiquetas = {}
        self.menu_id = None
        self.menu_contenido = None
        self._crear_menu()

    @property
    def actual(self):
        """Aplicacion cuyo panel y mensajes se muestran actualmente."""
        return self.aplicaciones[self.seleccion]

    @property
    def robot_actual(self):
        """Configuracion y estado del robot actualmente seleccionado."""
        return self.robots[self.seleccion]

    def _crear_menu(self):
        """Crea las etiquetas de nombre que identifican cada robot en la escena."""
        for robot in self.robots:
            posicion = robot["posicion"]
            self.etiquetas[robot["nombre"]] = p.addUserDebugText(
                robot["nombre"],
                [posicion[0], posicion[1], posicion[2] + ALTURA_ETIQUETA],
                [0.3, 0.3, 0.3], textSize=1.3)

    def seleccionar(self, indice):
        """Cambia de robot y reinicia los elementos visuales dependientes de camara."""
        if indice < 0 or indice >= len(self.robots):
            return
        if indice == self.seleccion:
            return
        anterior = self.actual
        anterior.limpiar_textos()
        self.seleccion = indice
        app = self.actual
        app.ver_deslizadores = False
        app.deslizadores = None
        app.deslizadores_listos = False
        app.camara_textos = None
        app.avisar(f"Seleccionado {self.robot_actual['nombre']} ({indice + 1}/{len(self.robots)})")
        self._actualizar_menu()

    def alternar_automatico(self):
        """Activa o desactiva el reinicio automatico de la secuencia actual."""
        robot = self.robot_actual
        robot["automatico"] = not robot["automatico"]
        estado = "activado" if robot["automatico"] else "desactivado"
        self.actual.avisar(f"Bucle automatico {estado}")

    def _actualizar_menu(self):
        """Construye la ayuda comun con los robots y sus bucles activos."""
        nombres = []
        for indice, robot in enumerate(self.robots):
            marca = ">" if indice == self.seleccion else " "
            nombres.append(f"[{indice + 1}] {marca}{robot['nombre']}")
        texto = "  ".join(nombres)
        control = (f"CAMBIAR ROBOT: pulsa [1]-[{len(self.robots)}]   "
                   f"ACTIVO: {self.robot_actual['nombre']}   "
                   f"A: ejecutar todos   L: bucle "
                   f"{'ON' if self.robot_actual['automatico'] else 'OFF'}")
        bucles = "  ".join(
            f"L{indice + 1}:{'ON' if robot['automatico'] else 'OFF'}"
            for indice, robot in enumerate(self.robots))
        texto += f"   ({bucles})"
        self.actual.ayuda_extra = [solo_ascii(control), solo_ascii(texto)]

    def tecla(self, tecla, estado):
        """Consume primero las teclas globales y delega las demas al robot activo."""
        if ord("1") <= tecla <= ord("9"):
            indice = tecla - ord("1")
            if indice < len(self.robots):
                self.seleccionar(indice)
            return
        if tecla == ord("l"):
            self.alternar_automatico()
            return
        if tecla == ord("a"):
            self.ejecutar_todos()
            return
        self.actual.tecla(tecla, estado)

    def ejecutar_todos(self):
        """Inicia la secuencia de cada robot que tenga puntos validos.

        Cada aplicacion comprueba por separado conexion, modo del robot y
        estado de seguridad, por lo que un robot no apto no impide iniciar los
        que si lo estan.
        """
        iniciados = 0
        for robot, app in zip(self.robots, self.aplicaciones):
            estado = robot.get("estado")
            if not app.puntos:
                continue
            modo_anterior = app.modo
            app.ejecutar(estado)
            if modo_anterior == "REPOSO" and app.modo == "ENVIANDO":
                iniciados += 1
        self.actual.avisar(f"Ejecutadas {iniciados}/{len(self.robots)} secuencias (A)")

    def _estado_de(self, robot):
        """Lee el ultimo estado disponible de una conexion concreta."""
        return robot["conexion"].leer()

    def actualizar_modelos(self):
        """Actualiza los modelos simulados y las etiquetas de todos los robots."""
        for robot in self.robots:
            estado = self._estado_de(robot)
            robot["estado"] = estado
            conectado = estado is not None
            robot["conectado"] = conectado
            if conectado:
                self.escena.move_robot(robot["id"], a_pybullet(estado["q"]))
            color = [0.05, 0.25, 0.55] if robot is self.robot_actual else [0.3, 0.3, 0.3]
            posicion = robot["posicion"]
            self.etiquetas[robot["nombre"]] = p.addUserDebugText(
                robot["nombre"], [posicion[0], posicion[1], posicion[2] + ALTURA_ETIQUETA],
                color, textSize=1.3,
                replaceItemUniqueId=self.etiquetas[robot["nombre"]])
        self._actualizar_menu()

    def avanzar_bucle(self, robot, app, modo_anterior):
        """Relanza una secuencia cuando termina y el bucle automatico esta activo."""
        if not robot["automatico"]:
            return
        termino = (modo_anterior in ("ENVIANDO", "MOVIENDO")
                   and app.modo == "REPOSO" and app.puntos
                   and app.paso >= len(app.puntos))
        if not termino:
            return
        estado = robot["estado"]
        app.ejecutar(estado)

    def fotograma(self):
        """Ejecuta una iteracion completa: leer, avanzar y dibujar."""
        self.actualizar_modelos()
        estado_actual = self.robot_actual["estado"]
        for robot, app in zip(self.robots, self.aplicaciones):
            estado = robot["estado"]
            app.iniciar_deslizadores(estado)
            modo_anterior = app.modo
            app.paso_maquina(estado)
            self.avanzar_bucle(robot, app, modo_anterior)
        self.actual.dibujar(estado_actual)


def main():
    """Configura la escena multi-robot y mantiene el bucle a ``FPS`` fijo."""
    robots = cargar_robots()
    if len(robots) > 9:
        raise SystemExit("Este visualizador admite como maximo 9 robots (teclas 1..9)")
    mitad = (len(robots) - 1) / 2
    for indice, robot in enumerate(robots):
        # Se distribuyen linealmente para que los modelos no se solapen en la vista.
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

    # PyBullet tiene atajos propios y paneles que compiten con nuestras teclas.
    p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(cameraDistance=2.4, cameraYaw=45,
                                 cameraPitch=-30, cameraTargetPosition=[0, 0, 0.3])

    gestor = AplicacionMultiple(escena, robots)
    try:
        siguiente = time.monotonic()
        while True:
            estado = gestor.robot_actual.get("estado")
            # KEY_WAS_TRIGGERED evita repetir una tecla durante todos los FPS
            # que permanezca pulsada. PyBullet entrega las letras en mayuscula.
            for tecla in (t + 32 if 65 <= t <= 90 else t
                          for t, est in p.getKeyboardEvents().items()
                          if est & p.KEY_WAS_TRIGGERED):
                gestor.tecla(tecla, estado)
            gestor.fotograma()
            # El reloj monotonic evita que un cambio de hora del sistema altere el ritmo.
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
