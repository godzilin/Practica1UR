"""Panel web local para lanzar los visualizadores sin depender del sistema operativo."""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
ROBOTS = BASE / "visualizador" / "robots.json"
HOST = "127.0.0.1"
PORT = 8765

PROGRAMAS = {
    "primaria": {"titulo": "Interfaz primaria", "descripcion": "Visualizador del puerto 30001", "script": "primaria.py"},
    "varios": {"titulo": "Varios robots", "descripcion": "Varios robots en una escena", "script": "varios_robots.py"},
    "tiempo-real": {"titulo": "Tiempo real", "descripcion": "Visualizador del puerto 30003", "script": "tiempo_real.py"},
    "ensenar": {"titulo": "Ensenar y reproducir", "descripcion": "Secuencias con supervision", "script": "ensenar_reproducir.py"},
    "conexion": {"titulo": "Probar conexion", "descripcion": "Comprueba estado y comunicacion", "script": "test_conexion.py"},
    "robustez": {"titulo": "Prueba de robustez", "descripcion": "Ejecuta las pruebas locales", "script": "prueba_robustez.py"},
}
PROCESOS = {}
LOCK = threading.Lock()
MAX_LINEAS_SALIDA = 5000


def leer_robots():
    return json.loads(ROBOTS.read_text(encoding="utf-8"))


def guardar_robots(robots):
    if not isinstance(robots, list) or not robots:
        raise ValueError("Debe existir al menos un robot")
    for robot in robots:
        if not isinstance(robot, dict):
            raise ValueError("Cada robot debe ser un objeto")
        for clave in ("nombre", "host", "puerto", "posicion"):
            if clave not in robot:
                raise ValueError(f"Falta el campo {clave}")
        if not isinstance(robot["nombre"], str) or not robot["nombre"].strip():
            raise ValueError("El nombre no puede estar vacio")
        if not isinstance(robot["host"], str) or not robot["host"].strip():
            raise ValueError("El host no puede estar vacio")
        if not isinstance(robot["puerto"], int) or not 1 <= robot["puerto"] <= 65535:
            raise ValueError("El puerto debe estar entre 1 y 65535")
        if not isinstance(robot["posicion"], list) or len(robot["posicion"]) != 6:
            raise ValueError("La posicion debe tener 6 numeros")
        if not all(isinstance(valor, (int, float)) and not isinstance(valor, bool) for valor in robot["posicion"]):
            raise ValueError("La posicion solo puede contener numeros")
    nombres = [robot["nombre"].strip() for robot in robots]
    if len(set(nombres)) != len(nombres):
        raise ValueError("Los nombres de los robots no pueden repetirse")
    temporal = ROBOTS.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(robots, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    os.replace(temporal, ROBOTS)


def limpiar_procesos():
    # Se conservan los procesos terminados para que su ultima salida siga visible.
    return


def recoger_salida(clave, salida, registro):
    """Lee stdout sin bloquear el servidor y conserva una ventana de diagnostico."""
    for linea in salida:
        with LOCK:
            if clave in PROCESOS:
                registro.append(linea.rstrip())
                del registro[:-MAX_LINEAS_SALIDA]
    salida.close()


def estado_procesos():
    limpiar_procesos()
    with LOCK:
        return {
            clave: {"pid": proceso.pid, "salida": proceso.poll(), "inicio": inicio,
                    "salida_texto": "\n".join(registro)}
            for clave, (proceso, inicio, registro) in PROCESOS.items()
        }


def iniciar(clave):
    if clave not in PROGRAMAS:
        raise ValueError("Programa desconocido")
    limpiar_procesos()
    with LOCK:
        if clave in PROCESOS and PROCESOS[clave][0].poll() is None:
            raise RuntimeError("Ese programa ya esta en ejecucion")
        PROCESOS.pop(clave, None)
        programa = PROGRAMAS[clave]
        registro = []
        entorno = os.environ.copy()
        ruta_visualizador = str(BASE / "visualizador")
        entorno["PYTHONPATH"] = ruta_visualizador + os.pathsep + entorno.get("PYTHONPATH", "")
        ruta_script = str(BASE / "visualizador" / programa["script"])
        proceso = subprocess.Popen(
            [sys.executable, "-u", "-c",
             "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
             "runpy.run_path(sys.argv[2], run_name='__main__')",
             ruta_visualizador, ruta_script],
            cwd=str(BASE / "visualizador"),
            env=entorno,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        PROCESOS[clave] = (proceso, time.time(), registro)
        threading.Thread(target=recoger_salida, args=(clave, proceso.stdout, registro), daemon=True).start()
    return proceso.pid


def detener(clave):
    with LOCK:
        datos = PROCESOS.get(clave)
    if not datos:
        return False
    proceso = datos[0]
    proceso.terminate()
    try:
        proceso.wait(timeout=4)
    except subprocess.TimeoutExpired:
        proceso.kill()
        proceso.wait()
    with LOCK:
        PROCESOS.pop(clave, None)
    return True


def documentos_disponibles():
    """Devuelve solo documentacion que se puede abrir desde el panel."""
    rutas = [BASE / "README.md"]
    rutas.extend((BASE / "docs").glob("*.md"))
    rutas.extend((BASE / "memoria").glob("*.pdf"))
    return [{"nombre": ruta.name, "ruta": ruta.relative_to(BASE).as_posix(),
             "url": "/documentos/" + quote(ruta.relative_to(BASE).as_posix())}
            for ruta in sorted(rutas)]


def ruta_documento(ruta):
    """Resuelve una ruta de documentacion sin permitir salir del proyecto."""
    candidato = (BASE / unquote(ruta)).resolve()
    if BASE not in candidato.parents or candidato.suffix.lower() not in {".md", ".pdf"}:
        raise FileNotFoundError("Documento no permitido")
    if not candidato.is_file():
        raise FileNotFoundError("Documento no encontrado")
    return candidato


class Handler(BaseHTTPRequestHandler):
    def log_message(self, formato, *args):
        pass

    def responder(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def recibir_json(self):
        longitud = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(longitud))

    def do_GET(self):
        ruta = urlparse(self.path).path
        try:
            if ruta == "/api/programas":
                self.responder({"programas": PROGRAMAS, "procesos": estado_procesos()})
            elif ruta == "/api/robots":
                self.responder({"robots": leer_robots()})
            elif ruta == "/api/documentos":
                self.responder({"documentos": documentos_disponibles()})
            elif ruta == "/":
                cuerpo = (WEB / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            elif ruta in ("/app.css", "/app.js"):
                extension = ruta[1:]
                cuerpo = (WEB / extension).read_bytes()
                tipo = "text/css" if extension.endswith("css") else "text/javascript"
                self.send_response(200)
                self.send_header("Content-Type", f"{tipo}; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            elif ruta.startswith("/documentos/"):
                documento = ruta_documento(ruta.removeprefix("/documentos/"))
                cuerpo = documento.read_bytes()
                tipo = "application/pdf" if documento.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Content-Disposition", "inline")
                self.end_headers()
                self.wfile.write(cuerpo)
            else:
                self.responder({"error": "Ruta no encontrada"}, 404)
        except FileNotFoundError as error:
            self.responder({"error": str(error)}, 404)
        except Exception as error:
            self.responder({"error": str(error)}, 500)

    def do_POST(self):
        ruta = urlparse(self.path).path
        try:
            datos = self.recibir_json()
            if ruta == "/api/iniciar":
                self.responder({"pid": iniciar(datos.get("programa"))})
            elif ruta == "/api/detener":
                self.responder({"detenido": detener(datos.get("programa"))})
            elif ruta == "/api/robots":
                guardar_robots(datos.get("robots"))
                self.responder({"guardado": True})
            else:
                self.responder({"error": "Ruta no encontrada"}, 404)
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            self.responder({"error": str(error)}, 400)
        except Exception as error:
            self.responder({"error": str(error)}, 500)


if __name__ == "__main__":
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Panel UR3e: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for clave in list(PROCESOS):
            detener(clave)
        servidor.server_close()
