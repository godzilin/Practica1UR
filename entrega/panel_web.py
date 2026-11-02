"""
Panel web para usar la práctica sin VS Code: editar robots.json y lanzar los scripts.

Solo usa la biblioteca estándar de Python y no sabe nada de robots: cada botón
lanza un script en un proceso aparte (como si se ejecutara en una terminal) y la
página muestra lo que escribe en la consola.

1. Arranca un servidor web en 127.0.0.1 (solo se puede usar desde este PC), en un
   puerto libre que elige el sistema, y abre el navegador.
2. La página es un formulario HTML normal, sin JavaScript. Cada botón manda un POST.
3. La salida de los scripts se ve en un marco que se recarga solo cada segundo,
   con lo más nuevo arriba.
4. Salir detiene los scripts en marcha y apaga el servidor.

Cómo usarlo: pulsa F5 en VS Code (o ejecuta python panel_web.py).
También se puede empaquetar en un único ejecutable de Linux con extras/compilar_linux.sh.
"""

import html
import json
import os
import runpy
import signal
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

# Empaquetado con PyInstaller, sys.executable es el propio ejecutable y no hay python.
# Los scripts y robots.json están junto al ejecutable, así que se pueden cambiar sin recompilar.
EMPAQUETADO = getattr(sys, "frozen", False)
CARPETA = Path(sys.executable).parent if EMPAQUETADO else Path(__file__).parent
ROBOTS = CARPETA / "robots.json"
SCRIPTS = ["primaria.py", "tiempo_real.py", "varios_robots.py", "ensenar_reproducir.py"]

procesos = {}                  # script -> su proceso
salida = deque(maxlen=200)     # últimas líneas de todos los scripts, con el nombre delante


def leer_salida(script, proceso):
    """Hilo: guarda cada línea que escribe el script (deque olvida las más viejas)."""
    for linea in proceso.stdout:
        salida.append(f"[{script}] {linea.rstrip()}")


def iniciar(script):
    if script in procesos and procesos[script].poll() is None:
        return f"{script} ya está en marcha"
    # -u: sin buffer, para que cada print llegue en el momento. Empaquetado, el ejecutable
    # se llama a sí mismo con el script y hace de python (ver el final del fichero)
    orden = [sys.executable, script] if EMPAQUETADO else [sys.executable, "-u", script]
    procesos[script] = subprocess.Popen(orden, cwd=CARPETA,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace",
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    threading.Thread(target=leer_salida, args=(script, procesos[script]), daemon=True).start()
    return f"{script} iniciado"


def detener(script):
    proceso = procesos.get(script)
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


def guardar_robots(texto):
    """Guarda en robots.json el texto del formulario, solo si es JSON válido."""
    try:
        json.loads(texto)
    except ValueError as e:
        return f"No se ha guardado: no es JSON válido ({e})"
    ROBOTS.write_text(texto.replace("\r\n", "\n"), encoding="utf-8")   # el navegador manda \r\n
    return "robots.json guardado. Los scripts en marcha no cambian hasta relanzarlos"


def pagina(mensaje=""):
    """La página principal: scripts, robots y salida."""
    botones = "".join(f'<p><button name="iniciar" value="{s}">Iniciar</button> '
                      f'<button name="detener" value="{s}">Detener</button> {s}</p>' for s in SCRIPTS)
    robots = ROBOTS.read_text(encoding="utf-8") if ROBOTS.exists() else "[]"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Visualizador UR3e</title></head><body>
<h1>Visualizador UR3e</h1>
<p><b>{html.escape(mensaje)}</b></p>
<h2>Scripts</h2>
<form method="post">{botones}<p><button name="salir">Salir</button></p></form>
<h2>Robots (robots.json)</h2>
<p>Los scripts de un solo robot usan el primero.</p>
<form method="post"><textarea name="robots" rows="8" cols="100">{html.escape(robots)}</textarea>
<p><button name="guardar">Guardar robots</button></p></form>
<h2>Salida (lo más nuevo, arriba)</h2>
<iframe src="/salida" width="100%" height="450"></iframe>
</body></html>"""


def pagina_salida():
    """Estado de cada script y sus líneas, de la más nueva a la más vieja. Se recarga cada segundo."""
    estados = "".join(f"<p>{s}: {'en marcha' if p.poll() is None else f'terminado (código {p.poll()})'}</p>"
                      for s, p in procesos.items())
    lineas = list(salida)          # copia de una vez: el hilo lector puede añadir mientras tanto
    return ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="1">'
            f'{estados or "<p>Aún no se ha iniciado ningún script.</p>"}'
            f'<pre>{html.escape(chr(10).join(reversed(lineas)))}</pre>')


class Manejador(BaseHTTPRequestHandler):
    """Atiende cada petición del navegador: GET para ver, POST para los botones."""

    def do_GET(self):
        self.responder(pagina_salida() if self.path == "/salida" else pagina())

    def do_POST(self):
        # El botón pulsado llega como un campo más: iniciar=primaria.py, o robots=[...]&guardar=
        # keep_blank_values: un botón sin valor (guardar=, salir=) también cuenta
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        campos = {nombre: valores[0] for nombre, valores in parse_qs(cuerpo, keep_blank_values=True).items()}
        if "salir" in campos:
            self.responder("<h1>Cerrado. Ya puedes cerrar esta pestaña.</h1>")
            for script in procesos:
                detener(script)
            # shutdown() espera a que acabe serve_forever(), así que se llama desde otro hilo
            threading.Thread(target=self.server.shutdown).start()
            return
        if "guardar" in campos:
            mensaje = guardar_robots(campos.get("robots", ""))
        elif campos.get("iniciar") in SCRIPTS:
            mensaje = iniciar(campos["iniciar"])
        elif campos.get("detener") in SCRIPTS:
            mensaje = detener(campos["detener"])
        else:
            mensaje = "Orden desconocida"
        self.responder(pagina(mensaje))

    def responder(self, texto):
        datos = texto.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass                                # sin una línea en la consola por cada recarga


if __name__ == "__main__" and EMPAQUETADO and len(sys.argv) > 1:
    # El ejecutable lanzado por iniciar() con un script: lo ejecuta como haría python
    sys.stdout.reconfigure(line_buffering=True)            # como -u: cada línea, en el momento
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
elif __name__ == "__main__":
    # Si el panel se lanzó en segundo plano, hereda Ctrl+C ignorado y se lo pasaría a los
    # scripts: Detener no podría pararlos con calma. Así Ctrl+C vuelve a funcionar.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    servidor = HTTPServer(("127.0.0.1", 0), Manejador)    # puerto 0: el sistema elige uno libre
    url = f"http://127.0.0.1:{servidor.server_port}"
    print(f"Panel en {url} (pulsa Salir en la página para cerrarlo)", flush=True)
    # El ejecutable pone sus bibliotecas en LD_LIBRARY_PATH. El navegador tiene que usar las del
    # sistema, y los scripts que lance el panel las del ejecutable: se cambia solo para abrirlo.
    if EMPAQUETADO:
        bibliotecas = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = os.environ.get("LD_LIBRARY_PATH_ORIG", "")
        webbrowser.open(url)
        os.environ["LD_LIBRARY_PATH"] = bibliotecas
    else:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        for script in procesos:
            detener(script)
