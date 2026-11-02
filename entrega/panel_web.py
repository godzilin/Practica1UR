"""
Panel web para usar la práctica sin VS Code: editar robots.json y lanzar los scripts.

Solo usa la biblioteca estándar de Python y no sabe nada de robots: cada botón
lanza un script en un proceso aparte (como si se ejecutara en una terminal) y la
página muestra lo que escribe en la consola.

1. Arranca un servidor web en 127.0.0.1 (solo se puede usar desde este PC), en un
   puerto libre que elige el sistema, y abre el navegador.
2. La página es un formulario HTML normal, sin JavaScript. Cada botón manda un POST.
3. La salida de los scripts se ve en un marco que se recarga solo cada segundo.
4. Salir detiene los scripts en marcha y apaga el servidor.

Cómo usarlo: pulsa F5 en VS Code (o ejecuta python panel_web.py).
"""

import html
import json
import os
import signal
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

CARPETA = Path(__file__).parent
ROBOTS = CARPETA / "robots.json"
SCRIPTS = ["primaria.py", "tiempo_real.py", "varios_robots.py", "ensenar_reproducir.py"]
LINEAS = 40                          # líneas de salida que se muestran de cada script

procesos = {}                        # script -> (proceso, últimas líneas que ha escrito)


def leer_robots():
    """Los robots de robots.json, o una lista vacía si no se puede leer."""
    try:
        return json.loads(ROBOTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def guardar_robots(campos):
    """Convierte las filas del formulario en robots.json. Devuelve el mensaje para la página.

    Cada fila trae nombre, host y posición ("x y z"). Una fila sin nombre se ignora:
    así se borra un robot (vaciando su nombre) o se añade uno (rellenando la fila vacía).
    """
    robots = []
    for nombre, host, posicion in zip(campos["nombre"], campos["host"], campos["posicion"]):
        if not nombre.strip():
            continue
        try:
            xyz = [float(v) for v in posicion.replace(",", " ").split()]
        except ValueError:
            xyz = []
        if not host.strip() or len(xyz) != 3:
            return f"No se ha guardado: {nombre} necesita una IP y una posición con 3 números"
        robots.append({"nombre": nombre.strip(), "host": host.strip(), "posicion": xyz})
    if not robots:
        return "No se ha guardado: tiene que haber al menos un robot"
    # Un robot por línea, para que el fichero se lea a simple vista
    ROBOTS.write_text("[\n" + ",\n".join("    " + json.dumps(r, ensure_ascii=False) for r in robots)
                      + "\n]\n", encoding="utf-8")
    return f"Guardados {len(robots)} robots. Los scripts en marcha no cambian hasta relanzarlos"


def leer_salida(proceso, lineas):
    """Hilo: guarda lo que escribe el script, línea a línea (deque se queda con las últimas)."""
    for linea in proceso.stdout:
        lineas.append(linea.rstrip())


def iniciar(script):
    if script in procesos and procesos[script][0].poll() is None:
        return f"{script} ya está en marcha"
    # -u: sin buffer, para que cada print llegue en el momento
    proceso = subprocess.Popen([sys.executable, "-u", script], cwd=CARPETA,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    lineas = deque(maxlen=LINEAS)
    procesos[script] = (proceso, lineas)
    threading.Thread(target=leer_salida, args=(proceso, lineas), daemon=True).start()
    return f"{script} iniciado"


def detener(script):
    proceso = procesos[script][0] if script in procesos else None
    if proceso is None or proceso.poll() is not None:
        return f"{script} no está en marcha"
    # En Linux se manda Ctrl+C (SIGINT): el script acaba igual que desde la terminal, y
    # ensenar_reproducir.py para el robot con stopj. Windows no lo permite y lo termina sin más.
    proceso.send_signal(signal.SIGINT if os.name == "posix" else signal.SIGTERM)
    try:
        proceso.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proceso.kill()
    return f"{script} detenido"


def pagina(mensaje=""):
    """La página principal: robots, scripts y salida."""
    filas = "".join(
        f'<tr><td><input name="nombre" value="{html.escape(str(r.get("nombre", "")))}"></td>'
        f'<td><input name="host" value="{html.escape(str(r.get("host", "")))}"></td>'
        f'<td><input name="posicion" value="{html.escape(" ".join(map(str, r.get("posicion", []))))}"></td></tr>'
        for r in leer_robots() + [{}])                    # + una fila vacía para añadir un robot
    botones = "".join(
        f'<p><button name="script" value="{s}" formaction="/iniciar">Iniciar</button> '
        f'<button name="script" value="{s}" formaction="/detener">Detener</button> {s}</p>'
        for s in SCRIPTS)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Visualizador UR3e</title></head><body>
<h1>Visualizador UR3e</h1>
<p><b>{html.escape(mensaje)}</b></p>
<h2>Robots</h2>
<p>Para borrar un robot, vacía su nombre. Para añadir uno, rellena la última fila.
Los scripts de un solo robot usan el primero.</p>
<form method="post" action="/robots"><table>
<tr><th>Nombre</th><th>IP</th><th>Posición x y z (m)</th></tr>{filas}
</table><p><button>Guardar robots</button></p></form>
<h2>Scripts</h2>
<form method="post">{botones}</form>
<h2>Salida</h2>
<iframe src="/salida" width="100%" height="450"></iframe>
<form method="post" action="/salir"><p><button>Salir</button></p></form>
</body></html>"""


def pagina_salida():
    """Lo que han escrito los scripts. Se recarga sola cada segundo (meta refresh)."""
    partes = []
    for script, (proceso, lineas) in procesos.items():
        codigo = proceso.poll()
        estado = f"en marcha (PID {proceso.pid})" if codigo is None else f"terminado (código {codigo})"
        partes.append(f"<h3>{script}: {estado}</h3><pre>{html.escape(chr(10).join(lineas))}</pre>")
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="1"></head><body>'
            + ("".join(partes) or "<p>Aún no se ha iniciado ningún script.</p>") + "</body></html>")


class Manejador(BaseHTTPRequestHandler):
    """Atiende cada petición del navegador: GET para ver, POST para los botones."""

    def do_GET(self):
        self.responder(pagina_salida() if self.path == "/salida" else pagina())

    def do_POST(self):
        # El navegador manda los campos como texto: script=primaria.py o nombre=...&host=...
        # keep_blank_values: una casilla vacía también cuenta, para no descolocar las filas
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        campos = parse_qs(cuerpo, keep_blank_values=True)
        script = campos.get("script", [""])[0]
        if self.path == "/salir":
            self.responder("<h1>Cerrado. Ya puedes cerrar esta pestaña.</h1>")
            for s in procesos:
                detener(s)
            # shutdown() espera a que acabe serve_forever(), así que se llama desde otro hilo
            threading.Thread(target=self.server.shutdown).start()
        elif self.path == "/robots":
            self.responder(pagina(guardar_robots(campos)))
        elif script in SCRIPTS and self.path == "/iniciar":
            self.responder(pagina(iniciar(script)))
        elif script in SCRIPTS and self.path == "/detener":
            self.responder(pagina(detener(script)))
        else:
            self.responder(pagina("Orden desconocida"))

    def responder(self, texto):
        datos = texto.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass                                # sin una línea en la consola por cada recarga


if __name__ == "__main__":
    # Si el panel se lanzó en segundo plano, hereda Ctrl+C ignorado y se lo pasaría a los
    # scripts: Detener no podría pararlos con calma. Así Ctrl+C vuelve a funcionar.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    servidor = HTTPServer(("127.0.0.1", 0), Manejador)    # puerto 0: el sistema elige uno libre
    url = f"http://127.0.0.1:{servidor.server_port}"
    print(f"Panel en {url} (pulsa Salir en la página para cerrarlo)", flush=True)
    webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        for s in procesos:
            detener(s)
